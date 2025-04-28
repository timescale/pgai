import logging
from dataclasses import dataclass

import psycopg
from jinja2 import Template
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage, UsageLimits

from pgai.semantic_catalog import loader, render, search, templates
from pgai.semantic_catalog.models import Fact, Procedure, SQLExample, Table, View
from pgai.semantic_catalog.vectorizer import EmbeddingConfig, vectorizer

logger = logging.getLogger(__name__)

_template_system_prompt: Template = templates.env.get_template(
    "prompt_gen_sql_system.j2"
)
_template_user_prompt: Template = templates.env.get_template("prompt_gen_sql_user.j2")


async def get_database_version(target_con: psycopg.AsyncConnection) -> int | None:
    async with target_con.cursor() as cur:
        await cur.execute("select current_setting('server_version_num', true)")
        row = await cur.fetchone()
        return int(row[0]) // 10000 if row else None


@dataclass
class DatabaseContext:
    objects: dict[int, Table | View | Procedure]
    sql_examples: dict[int, SQLExample]
    facts: dict[int, Fact]
    rendered_objects: dict[int, str]
    rendered_sql_examples: dict[int, str]
    rendered_facts: dict[int, str]


def render_database_context(ctx: DatabaseContext) -> str:
    output = ""
    if ctx.rendered_objects:
        output += "\n\n".join(ctx.rendered_objects.values())
    if ctx.rendered_sql_examples:
        output += "\n\n"
        output += "\n\n".join(ctx.rendered_sql_examples.values())
    if ctx.rendered_facts:
        output += "\n\n"
        output += "\n\n".join(ctx.rendered_facts.values())
    return output.strip()


async def fetch_database_context(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    embedding_config: EmbeddingConfig,
    prompt: str,
    ctx: DatabaseContext | None = None,
    sample_size: int = 3,
) -> DatabaseContext:
    ctx = (
        ctx
        if ctx
        else DatabaseContext(
            objects={},
            sql_examples={},
            facts={},
            rendered_objects={},
            rendered_sql_examples={},
            rendered_facts={},
        )
    )

    emb_prompt = await vectorizer.vectorize_query(embedding_config, prompt)

    # objects
    object_descs = {
        x.id: x
        for x in await search.search_objects(
            catalog_con,
            catalog_id,
            embedding_name,
            embedding_config,
            emb_prompt,
        )
    }
    missing_object_ids = object_descs.keys() - ctx.objects.keys()
    if missing_object_ids:
        objects = await loader.load_objects(
            target_con, [object_descs[id] for id in missing_object_ids], sample_size
        )
        ctx.objects.update({x.id: x for x in objects})
        ctx.rendered_objects.update({x.id: render.render_object(x) for x in objects})

    # sql examples
    for x in await search.search_sql_examples(
        catalog_con,
        catalog_id,
        embedding_name,
        embedding_config,
        emb_prompt,
    ):
        if x.id in ctx.sql_examples:
            continue
        ctx.sql_examples[x.id] = x
        ctx.rendered_sql_examples[x.id] = render.render_sql_example(x)

    # facts
    for x in await search.search_facts(
        catalog_con,
        catalog_id,
        embedding_name,
        embedding_config,
        emb_prompt,
    ):
        if x.id in ctx.facts:
            continue
        ctx.facts[x.id] = x
        ctx.rendered_facts[x.id] = render.render_fact(x)

    return ctx


async def validate_sql_statement(
    target_con: psycopg.AsyncConnection,
    sql_statement: str,
) -> str | None:
    async with (
        target_con.cursor() as cur,
        target_con.transaction(force_rollback=True) as _,
    ):
        try:
            await cur.execute(f"explain {sql_statement}")  # pyright: ignore [reportArgumentType]
        except psycopg.Error as e:
            logger.info(f"sql statement is invalid {e.diag.message_primary or str(e)}")
            return e.diag.message_primary or str(e)
        else:
            logger.info("sql statement is valid")
            return None


@dataclass
class GenerateSQLResponse:
    sql_statement: str
    context: DatabaseContext
    messages: list[ModelMessage]
    usage: Usage


async def generate_sql(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    model: KnownModelName | Model,
    catalog_id: int,
    embedding_name: str,
    embedding_config: EmbeddingConfig,
    prompt: str,
    usage_limits: UsageLimits,
    model_settings: ModelSettings,
    sample_size: int = 3,
) -> GenerateSQLResponse:
    prior_prompts: list[str] = [prompt]

    ctx: DatabaseContext = await fetch_database_context(
        catalog_con,
        target_con,
        catalog_id,
        embedding_name,
        embedding_config,
        prompt,
        ctx=None,
        sample_size=sample_size,
    )

    answer: str | None = None

    pgversion: int | None = await get_database_version(target_con)
    system_prompt: str = _template_system_prompt.render(pgversion=pgversion)

    agent = Agent(
        model=model,
        model_settings=model_settings,
        name="sql-author",
        system_prompt=system_prompt,
    )

    @agent.tool_plain
    async def search_for_context(search_prompts: list[str]) -> None:  # pyright: ignore [reportUnusedFunction]
        """Search for database objects, example SQL statements, and facts that are
        relevant to the prompts

        :param search_prompts: one or more natural language prompts for a semantic
            search query
        :return: None
        """
        nonlocal ctx
        for prompt in search_prompts:
            prior_prompts.append(prompt)
            logger.info(f"{agent.name}: semantic search for '{prompt}'")
            ctx = await fetch_database_context(
                catalog_con,
                target_con,
                catalog_id,
                embedding_name,
                embedding_config,
                prompt,
                ctx,
                sample_size=sample_size,
            )

    @agent.tool_plain
    def record_sql_statement(  # pyright: ignore [reportUnusedFunction]
        sql_statement: str,
        relevant_object_ids: list[int],
        relevant_sql_example_ids: list[int],
        relevant_fact_ids: list[int],
    ) -> None:
        """Records a valid SQL statement to address the users' prompt and context that
        was relevant to the problem

        :param sql_statement: a valid SQL statement that accurately addresses the
            user's prompt
        :param relevant_object_ids: the ids of the database objects that were relevant
            to answering the user's prompt
        :param relevant_sql_example_ids: the ids of the SQL examples that were relevant
            to answering the user's prompt
        :param relevant_fact_ids: the ids of the facts that were relevant to answering
            the user's prompt
        :return: None
        """
        logger.info(f"{agent.name}: answered.")
        nonlocal answer
        answer = sql_statement
        nonlocal ctx
        for irrelevant_id in ctx.objects.keys() - relevant_object_ids:
            ctx.objects.pop(irrelevant_id)
            ctx.rendered_objects.pop(irrelevant_id)
        for irrelevant_id in ctx.sql_examples.keys() - relevant_sql_example_ids:
            ctx.sql_examples.pop(irrelevant_id)
            ctx.rendered_sql_examples.pop(irrelevant_id)
        for irrelevant_id in ctx.facts.keys() - relevant_fact_ids:
            ctx.facts.pop(irrelevant_id)
            ctx.rendered_facts.pop(irrelevant_id)

    messages: list[ModelMessage] = []
    usage: Usage = Usage()
    user_prompt: str | None = None
    while True:
        usage_limits.check_before_request(usage)
        if user_prompt is None:
            user_prompt = _template_user_prompt.render(
                ctx=ctx, prompt=prompt, prior_prompts=prior_prompts
            )
        result: AgentRunResult = await agent.run(user_prompt, usage_limits=usage_limits)
        messages.extend(result.new_messages())
        usage = usage + result.usage()
        if answer:
            error = await validate_sql_statement(target_con, answer)
            if error:
                logger.info(f"asking {agent.name} to fix the invalid sql statement")
                user_prompt = _template_user_prompt.render(
                    ctx=ctx,
                    prompt=prompt,
                    prior_prompts=prior_prompts,
                    error=error,
                )
            else:
                break  # we have a valid answer
        else:
            user_prompt = None
    return GenerateSQLResponse(
        sql_statement=answer,
        context=ctx,
        messages=messages,
        usage=usage,
    )

import logging
from dataclasses import dataclass
from typing import Any, Literal

import psycopg
from jinja2 import Template
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage, UsageLimits

from pgai.semantic_catalog import loader, render, search, templates
from pgai.semantic_catalog.models import (
    Fact,
    ObjectDescription,
    Procedure,
    SQLExample,
    Table,
    View,
)
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


async def fetch_database_context_alt(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    obj_ids: list[int] | None = None,
    sql_ids: list[int] | None = None,
    fact_ids: list[int] | None = None,
    sample_size: int = 3,
) -> DatabaseContext:
    ctx = DatabaseContext(
        objects={},
        sql_examples={},
        facts={},
        rendered_objects={},
        rendered_sql_examples={},
        rendered_facts={},
    )
    async with catalog_con.cursor(row_factory=dict_row) as cur:
        # objects
        sql = SQL("""\
            select x.*
            from ai.{table} x
            {}
        """).format(
            Identifier(f"semantic_catalog_obj_{catalog_id}"),
            SQL("where x.id = any(%s)") if obj_ids else SQL(""),
        )
        await cur.execute(sql)
        objects: list[ObjectDescription] = []
        for row in await cur.fetchall():
            objects.append(ObjectDescription(**row))
        ctx.objects = {
            x.id: x for x in await loader.load_objects(target_con, objects, sample_size)
        }
        ctx.rendered_objects = {
            x.id: render.render_object(x) for x in ctx.objects.values()
        }

        # sql examples
        sql = SQL("""\
            select x.*
            from ai.{table} x
            {}
        """).format(
            Identifier(f"semantic_catalog_sql_{catalog_id}"),
            SQL("where x.id = any(%s)") if sql_ids else SQL(""),
        )
        await cur.execute(sql)
        sql_examples: list[SQLExample] = []
        for row in await cur.fetchall():
            sql_examples.append(SQLExample(**row))
        ctx.sql_examples = {x.id: x for x in sql_examples}
        ctx.rendered_objects = {
            x.id: render.render_sql_example(x) for x in sql_examples
        }

        # facts
        sql = SQL("""\
            select x.*
            from ai.{table} x
            {}
        """).format(
            Identifier(f"semantic_catalog_fact_{catalog_id}"),
            SQL("where x.id = any(%s)") if fact_ids else SQL(""),
        )
        await cur.execute(sql)
        facts: list[Fact] = []
        for row in await cur.fetchall():
            facts.append(Fact(**row))
        ctx.facts = {x.id: x for x in facts}
        ctx.rendered_facts = {x.id: render.render_fact(x) for x in facts}

    return ctx


async def validate_sql_statement(
    target_con: psycopg.AsyncConnection,
    sql_statement: str,
) -> tuple[dict[str, Any] | None, str | None]:
    async with (
        target_con.cursor(row_factory=dict_row) as cur,
        target_con.transaction(force_rollback=True) as _,
    ):
        try:
            await cur.execute(f"explain (format json) {sql_statement}")  # pyright: ignore [reportArgumentType]
            plan = await cur.fetchone()
            assert plan is not None, "explain did not return a query plan"
            logger.info("sql statement is valid")
            return plan, None
        except psycopg.Error as e:
            logger.info(f"sql statement is invalid {e.diag.message_primary or str(e)}")
            return None, e.diag.message_primary or str(e)


@dataclass
class GenerateSQLResponse:
    sql_statement: str
    context: DatabaseContext
    query_plan: dict[str, Any]
    final_prompt: str
    messages: list[ModelMessage]
    usage: Usage


ContextMode = Literal["semantic_search", "entire_catalog", "specific_ids"]


async def initialize_database_context(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    embedding_config: EmbeddingConfig,
    prompt: str,
    sample_size: int = 3,
    context_mode: ContextMode = "semantic_search",
    obj_ids: list[int] | None = None,
    sql_ids: list[int] | None = None,
    fact_ids: list[int] | None = None,
) -> DatabaseContext:
    assert context_mode in {"semantic_search", "entire_catalog", "specific_ids"}
    match context_mode:
        case "semantic_search":
            return await fetch_database_context(
                catalog_con,
                target_con,
                catalog_id,
                embedding_name,
                embedding_config,
                prompt,
                ctx=None,
                sample_size=sample_size,
            )
        case "entire_catalog":
            obj_ids = None
            sql_ids = None
            fact_ids = None
            return await fetch_database_context_alt(
                catalog_con,
                target_con,
                catalog_id,
                sample_size=sample_size,
                obj_ids=obj_ids,
                sql_ids=sql_ids,
                fact_ids=fact_ids,
            )
        case "specific_ids":
            obj_ids = obj_ids or []
            sql_ids = sql_ids or []
            fact_ids = fact_ids or []
            return await fetch_database_context_alt(
                catalog_con,
                target_con,
                catalog_id,
                sample_size=sample_size,
                obj_ids=obj_ids,
                sql_ids=sql_ids,
                fact_ids=fact_ids,
            )


async def generate_sql(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    model: KnownModelName | Model,
    catalog_id: int,
    embedding_name: str,
    embedding_config: EmbeddingConfig,
    prompt: str,
    usage: Usage | None = None,
    usage_limits: UsageLimits | None = None,
    model_settings: ModelSettings | None = None,
    sample_size: int = 3,
    context_mode: ContextMode = "semantic_search",
    obj_ids: list[int] | None = None,
    sql_ids: list[int] | None = None,
    fact_ids: list[int] | None = None,
) -> GenerateSQLResponse:
    usage = usage or Usage()
    usage_limits = usage_limits or UsageLimits(request_limit=None)
    model_settings = model_settings or ModelSettings()

    ctx = await initialize_database_context(
        catalog_con,
        target_con,
        catalog_id,
        embedding_name,
        embedding_config,
        prompt,
        sample_size=sample_size,
        obj_ids=obj_ids,
        sql_ids=sql_ids,
        fact_ids=fact_ids,
    )

    prior_prompts: list[str] = [prompt]
    answer: str | None = None

    pgversion: int | None = await get_database_version(target_con)
    system_prompt: str = _template_system_prompt.render(
        pgversion=pgversion, context_mode=context_mode
    )

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
        for p in search_prompts:
            prior_prompts.append(p)
            logger.info(f"{agent.name}: semantic search for '{p}'")
            nonlocal ctx
            ctx = await fetch_database_context(
                catalog_con,
                target_con,
                catalog_id,
                embedding_name,
                embedding_config,
                p,
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
    user_prompt: str | None = None
    query_plan: dict[str, Any] | None = None
    while True:
        if user_prompt is None:
            user_prompt = _template_user_prompt.render(
                ctx=ctx, prompt=prompt, prior_prompts=prior_prompts
            )
        result: AgentRunResult = await agent.run(
            user_prompt, usage_limits=usage_limits, usage=usage
        )
        usage = result.usage()
        messages.extend(result.new_messages())
        if answer:
            logger.info("validating the sql statement")
            query_plan, error = await validate_sql_statement(target_con, answer)
            if error:
                answer = None
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
        query_plan=query_plan,
        final_prompt=user_prompt,
        messages=messages,
        usage=usage,
    )

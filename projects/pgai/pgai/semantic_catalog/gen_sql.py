from dataclasses import dataclass
from textwrap import dedent
from typing import Union, TypeAlias

import psycopg
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.messages import ModelMessage
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage

from pgai.semantic_catalog import loader, render, search
from pgai.semantic_catalog.models import Fact, Procedure, SQLExample, Table, View
from pgai.semantic_catalog.vectorizer import EmbeddingConfig


@dataclass
class DatabaseContext:
    objects: dict[int, Table | View | Procedure]
    sql_examples: dict[int, SQLExample]
    facts: dict[int, Fact]
    rendered_objects: dict[int, str]
    rendered_sql_examples: dict[int, str]
    rendered_facts: dict[int, str]


@dataclass
class _Context:
    catalog_con: psycopg.AsyncConnection
    target_con: psycopg.AsyncConnection
    catalog_id: int
    embedding_name: str
    embedding_config: EmbeddingConfig
    question: str


@dataclass
class GeneratedSQL:
    sql: str


async def fetch_database_context(
    ctx: _Context,
    dbctx: DatabaseContext | None = None,
) -> DatabaseContext:
    if dbctx is None:
        dbctx = DatabaseContext(
            objects={},
            sql_examples={},
            facts={},
            rendered_objects={},
            rendered_sql_examples={},
            rendered_facts={},
        )

    # objects
    object_descs = {
        x.id: x
        for x in await search.search_objects(
            ctx.catalog_con,
            ctx.catalog_id,
            ctx.embedding_name,
            ctx.embedding_config,
            ctx.question,
        )
    }
    missing_object_ids = object_descs.keys() - dbctx.objects.keys()
    if missing_object_ids:
        objects = await loader.load_objects(
            ctx.target_con, [object_descs[id] for id in missing_object_ids]
        )
        dbctx.objects.update({x.id: x for x in objects})
        dbctx.rendered_objects.update({x.id: render.render_object(x) for x in objects})

    # sql examples
    for x in await search.search_sql_examples(
        ctx.catalog_con,
        ctx.catalog_id,
        ctx.embedding_name,
        ctx.embedding_config,
        ctx.question,
    ):
        if x.id in dbctx.sql_examples:
            continue
        dbctx.sql_examples[x.id] = x
        dbctx.rendered_sql_examples[x.id] = render.render_sql_example(x)

    # facts
    for x in await search.search_facts(
        ctx.catalog_con,
        ctx.catalog_id,
        ctx.embedding_name,
        ctx.embedding_config,
        ctx.question,
    ):
        if x.id in dbctx.facts:
            continue
        dbctx.facts[x.id] = x
        dbctx.rendered_facts[x.id] = render.render_fact(x)

    return dbctx


class _InsufficientContext(BaseModel):
    new_prompts: list[str]


class _SufficientContext(BaseModel):
    relevant_object_ids: list[int]
    relevant_sql_example_ids: list[int]
    relevant_facts_ids: list[int]


ContextResponse: TypeAlias = Union[_SufficientContext, _InsufficientContext]

_agent_context_builder = Agent(
    name="context-builder",
    deps_type=tuple[_Context, DatabaseContext],
    output_type=ContextResponse,
    system_prompt=(
        "You are a SQL expert. "
        "You will be given a user's question that can be answered with a PostgreSQL database. "
        "At your disposal is a semantic catalog. "
        "The semantic catalog contains database object definitions with natural language descriptions. "
        "It also contains example SQL statements with descriptions, and general facts regarding the database domain. "
        "Included below is a context created by searching the semantic catalog with the user's question and zero or more additional prompts. "
        "Your task is to judge whether or not the context is sufficent to accurately answer the question. "
        "If the context is insufficient, respond with a list of new prompts to query the semantic catalog to expand the context. "
        "If the context is sufficient, respond with the ids of the objects, sql examples, and facts that are relevant to answering the question."
    ),
)


async def build_context(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    model: KnownModelName | Model,
    model_settings: ModelSettings,
    catalog_id: int,
    embedding_name: str,
    embedding_config: EmbeddingConfig,
    question: str,
) -> tuple[DatabaseContext, list[ModelMessage], Usage]:
    ctx = _Context(
        catalog_con=catalog_con,
        target_con=target_con,
        catalog_id=catalog_id,
        embedding_name=embedding_name,
        embedding_config=embedding_config,
        question=question,
    )

    prior_prompts: list[str] = []
    dbctx = await fetch_database_context(ctx)
    messages: list[ModelMessage] = []
    usage: Usage = Usage()
    while True:
        user_prompt = (
            "Judge whether the context below is sufficient to accurately answer the following question by authoring a SQL statement. "
            f"Q: {question} "
        )
        if len(dbctx.rendered_objects) > 0:
            user_prompt += "\n\n"
            user_prompt += "\n\n".join(dbctx.rendered_objects.values())
        if len(dbctx.rendered_sql_examples) > 0:
            user_prompt += "\n\n"
            user_prompt += "\n\n".join(dbctx.rendered_sql_examples.values())
        if len(dbctx.rendered_facts) > 0:
            user_prompt += "\n\n"
            user_prompt += "\n\n".join(dbctx.rendered_facts.values())

        result: AgentRunResult = await _agent_context_builder.run(
            user_prompt, model, model_settings, usage=usage
        )
        messages.extend(result.new_messages())
        usage = usage + result.usage()
        match result.data:
            case _InsufficientContext():
                insuff: _InsufficientContext = result.output
                for prompt in insuff.new_prompts:
                    prior_prompts.append(prompt)
                    dbctx = await fetch_database_context(ctx, dbctx)
            case _SufficientContext():
                suff: _SufficientContext = result.output
                # prune the context. remove irrelevant items
                irrelevant_object_ids: set[int] = set(dbctx.objects.keys()) - set(
                    suff.relevant_object_ids
                )
                for object_id in irrelevant_object_ids:
                    dbctx.objects.pop(object_id)
                irrelevant_sql_example_ids: set[int] = set(
                    dbctx.sql_examples.keys()
                ) - set(suff.relevant_sql_example_ids)
                for sql_example_id in irrelevant_sql_example_ids:
                    dbctx.sql_examples.pop(sql_example_id)
                irrelevant_fact_ids: set[int] = set(dbctx.facts.keys()) - set(
                    suff.relevant_facts_ids
                )
                for fact_id in irrelevant_fact_ids:
                    dbctx.facts.pop(fact_id)
                return dbctx, messages, usage
            case _:
                raise RuntimeError(f"Unexpected result {result.data}")


class _AgentSQLAuthorOutput(BaseModel):
    sql_statement: str


_agent_sql_author = Agent(
    name="sql-author",
    deps_type=tuple[_Context, DatabaseContext],
    output_type=_AgentSQLAuthorOutput,
    system_prompt=(
        "You are a SQL expert with particular expertise in PostgreSQL. "
        "You will be given a user's question regarding a PostgreSQL database. "
        "Your task is to author a SQL statement to accurately address the user's question. "
        "Respond only with a valid SQL statement without any commentary."
    ),
)


@_agent_sql_author.output_validator
async def _validate_sql_statement(
    rctx: RunContext[tuple[_Context, DatabaseContext]], output: _AgentSQLAuthorOutput
) -> _AgentSQLAuthorOutput:
    ctx: _Context = rctx.deps[0]
    try:
        async with ctx.target_con.cursor() as cur:
            await cur.execute(f"explain {output.sql_statement}")
    except psycopg.Error as e:
        raise ModelRetry(f"The SQL statement is invalid: {e}") from e
    else:
        return output


async def generate_sql(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    model: KnownModelName | Model,
    catalog_id: int,
    embedding_name: str,
    embedding_config: EmbeddingConfig,
    question: str,
    model_settings: ModelSettings | None = None,
) -> tuple[str, DatabaseContext, list[ModelMessage], Usage]:
    dbctx, messages, usage = await build_context(
        catalog_con,
        target_con,
        model,
        model_settings,
        catalog_id,
        embedding_name,
        embedding_config,
        question,
    )

    user_prompt = dedent(f"""\
    Author a SQL statement to accurately address the question below. '
    Q: {question}
    """)

    if len(dbctx.rendered_objects) > 0:
        user_prompt += "\n\n"
        user_prompt += "\n\n".join(dbctx.rendered_objects.values())
    if len(dbctx.rendered_sql_examples) > 0:
        user_prompt += "\n\n"
        user_prompt += "\n\n".join(dbctx.rendered_sql_examples.values())
    if len(dbctx.rendered_facts) > 0:
        user_prompt += "\n\n"
        user_prompt += "\n\n".join(dbctx.rendered_facts.values())

    result: AgentRunResult = await _agent_sql_author.run(
        user_prompt, model, model_settings, usage=usage
    )
    gensql: GeneratedSQL = result.data
    return gensql.sql, dbctx, messages, usage

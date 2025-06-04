"""Module for generating SQL statements using AI and semantic catalog context.

This module provides functionality to generate valid SQL statements based on natural
language prompts and database context from the semantic catalog. It uses semantic search
to find relevant database objects, SQL examples, and facts, and employs an AI model to
generate SQL that fulfills the user's request. The generated SQL is validated against
the target database to ensure correctness.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal, cast

import psycopg
from jinja2 import Template
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from pydantic_ai.direct import model_request
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models import KnownModelName, Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
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


async def _get_database_version(target_con: psycopg.AsyncConnection) -> int | None:
    """Get the major version number of the PostgreSQL database.

    Queries the database to retrieve its version number, which is used to ensure
    that generated SQL is compatible with the specific PostgreSQL version in use.

    Args:
        target_con: Asynchronous connection to the target database.

    Returns:
        The major version number (e.g., 15 for PostgreSQL 15.x) or None if unavailable.
    """
    async with target_con.cursor() as cur:
        await cur.execute("select current_setting('server_version_num', true)")
        row = await cur.fetchone()
        return int(row[0]) // 10000 if row else None


@dataclass
class DatabaseContext:
    """Container for database objects, SQL examples, facts, and their rendered representations.

    This class stores references to database objects (tables, views, procedures),
    SQL examples, and facts that are relevant to a user query, along with their
    rendered text representations for use in prompt construction.

    Attributes:
        objects: Dictionary mapping object IDs to database objects (Tables, Views, Procedures).
        sql_examples: Dictionary mapping SQL example IDs to SQLExample objects.
        facts: Dictionary mapping fact IDs to Fact objects.
        rendered_objects: Dictionary mapping object IDs to their rendered text representations.
        rendered_sql_examples: Dictionary mapping SQL example IDs to their rendered text representations.
        rendered_facts: Dictionary mapping fact IDs to their rendered text representations.
    """  # noqa: E501

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
    """Fetch database context relevant to a prompt using semantic search.

    Performs semantic search in the catalog to find database objects, SQL examples,
    and facts that are relevant to the given prompt. The retrieved items are added to
    the provided context (or a new context is created if none is provided).

    Args:
        catalog_con: Connection to the semantic catalog database.
        target_con: Connection to the target database (where the objects are defined).
        catalog_id: ID of the semantic catalog to search in.
        embedding_name: Name of the embedding column to use for semantic search.
        embedding_config: Configuration for the embedding model.
        prompt: The natural language prompt to search for relevant context.
        ctx: Optional existing DatabaseContext to add to (None creates a new one).
        sample_size: Number of sample rows to include for tables and views (default: 3).

    Returns:
        A DatabaseContext containing the relevant database objects, SQL examples, and facts.
    """  # noqa: E501
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
            exclude_ids=[k for k in ctx.objects],
        )
    }
    missing_object_ids = object_descs.keys() - ctx.objects.keys()
    if missing_object_ids:
        objects = await loader.load_objects(
            catalog_con,
            target_con,
            catalog_id,
            [object_descs[id] for id in missing_object_ids],
            sample_size,
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
        exclude_ids=[k for k in ctx.sql_examples],
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
        exclude_ids=[k for k in ctx.rendered_facts],
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
    """Fetch database context by explicit IDs or fetch all items from the catalog.

    Retrieves database objects, SQL examples, and facts from the semantic catalog based
    on either explicit IDs or by fetching all items if no IDs are provided.

    Args:
        catalog_con: Connection to the semantic catalog database.
        target_con: Connection to the target database (where the objects are defined).
        catalog_id: ID of the semantic catalog to fetch from.
        obj_ids: Optional list of object IDs to fetch (None fetches all).
        sql_ids: Optional list of SQL example IDs to fetch (None fetches all).
        fact_ids: Optional list of fact IDs to fetch (None fetches all).
        sample_size: Number of sample rows to include for tables and views (default: 3).

    Returns:
        A DatabaseContext containing the specified database objects, SQL examples, and facts.
    """  # noqa: E501
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
            from ai.{} x
            {}
        """).format(
            Identifier(f"semantic_catalog_obj_{catalog_id}"),
            SQL("where x.id = any(%s)") if obj_ids is not None else SQL(""),
        )
        await cur.execute(sql, (obj_ids,) if obj_ids is not None else ())
        objects: list[ObjectDescription] = []
        for row in await cur.fetchall():
            objects.append(ObjectDescription(**row))
        ctx.objects = {
            x.id: x
            for x in await loader.load_objects(
                catalog_con, target_con, catalog_id, objects, sample_size
            )
        }
        ctx.rendered_objects = {
            x.id: render.render_object(x) for x in ctx.objects.values()
        }

        # sql examples
        sql = SQL("""\
            select x.*
            from ai.{} x
            {}
        """).format(
            Identifier(f"semantic_catalog_sql_{catalog_id}"),
            SQL("where x.id = any(%s)") if sql_ids is not None else SQL(""),
        )
        await cur.execute(sql, (sql_ids,) if sql_ids is not None else ())
        sql_examples: list[SQLExample] = []
        for row in await cur.fetchall():
            sql_examples.append(SQLExample(**row))
        ctx.sql_examples = {x.id: x for x in sql_examples}
        ctx.rendered_sql_examples = {
            x.id: render.render_sql_example(x) for x in sql_examples
        }

        # facts
        sql = SQL("""\
            select x.*
            from ai.{} x
            {}
        """).format(
            Identifier(f"semantic_catalog_fact_{catalog_id}"),
            SQL("where x.id = any(%s)") if fact_ids is not None else SQL(""),
        )
        await cur.execute(sql, (fact_ids,) if fact_ids is not None else ())
        facts: list[Fact] = []
        for row in await cur.fetchall():
            facts.append(Fact(**row))
        ctx.facts = {x.id: x for x in facts}
        ctx.rendered_facts = {x.id: render.render_fact(x) for x in facts}

    return ctx


def diagnostic_to_str(d: psycopg.errors.Diagnostic) -> str | None:
    msgs: list[str] = []
    if d.message_primary:
        msgs.append(d.message_primary)
    if d.message_detail:
        msgs.append(f"DETAIL: {d.message_detail}")
    if d.message_hint:
        msgs.append(f"HINT: {d.message_hint}")
    if d.statement_position:
        msgs.append(f"STATEMENT POSITION: {d.statement_position}")
    if d.context:
        msgs.append(f"CONTEXT: {d.context}")
    if d.schema_name:
        msgs.append(f"SCHEMA NAME: {d.schema_name}")
    if d.table_name:
        msgs.append(f"TABLE NAME: {d.table_name}")
    if d.column_name:
        msgs.append(f"COLUMN NAME: {d.column_name}")
    if d.constraint_name:
        msgs.append(f"CONSTRAINT NAME: {d.constraint_name}")
    if d.sqlstate:
        msgs.append(f"SQLSTATE: {d.sqlstate}")
    msg = "\n".join(msgs).strip()
    return msg if msg != "" else None


async def validate_sql_statement(
    target_con: psycopg.AsyncConnection,
    sql_statement: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate a SQL statement against the database.

    Attempts to execute an EXPLAIN command for the SQL statement to verify that it is
    syntactically correct and can be executed on the target database. This is done in
    a transaction that is rolled back to prevent any modifications to the database.

    Args:
        target_con: Connection to the target database.
        sql_statement: The SQL statement to validate.

    Returns:
        A tuple containing:
        - The query plan as a dictionary if validation succeeds, None otherwise.
        - The error message if validation fails, None otherwise.
    """
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
            msg = diagnostic_to_str(e.diag) or str(e)
            logger.info(f"sql statement is invalid {msg}")
            return None, msg


@dataclass
class GenerateSQLResponse:
    """Response object for the generate_sql function.

    Contains the generated SQL statement, the context used to generate it,
    the query plan, and additional information about the generation process.

    Attributes:
        sql_statement: The generated SQL statement.
        context: The database context used to generate the SQL statement.
        command_type: The type of SQL statement generated (e.g. SELECT, INSERT, UPDATE)
        query_plan: The PostgreSQL query plan for the generated SQL statement.
        final_prompt: The final prompt that was sent to the model.
        messages: List of all messages exchanged during the generation process.
        usage: Usage statistics for the AI model calls.
    """

    sql_statement: str
    context: DatabaseContext
    command_type: str
    query_plan: dict[str, Any]
    final_prompt: str
    messages: list[ModelRequest | ModelResponse]
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
    """Initialize database context based on the specified context mode.

    This function serves as a dispatcher to initialize the database context using
    one of three strategies:
    1. Semantic search: Find relevant items based on the prompt.
    2. Entire catalog: Fetch all items from the catalog.
    3. Specific IDs: Fetch items with the specified IDs.

    Args:
        catalog_con: Connection to the semantic catalog database.
        target_con: Connection to the target database.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to use for semantic search.
        embedding_config: Configuration for the embedding model.
        prompt: The natural language prompt to search for relevant context.
        sample_size: Number of sample rows to include for tables and views (default: 3).
        context_mode: The mode to use for initializing the context (default: "semantic_search").
        obj_ids: Optional list of object IDs to fetch (for "specific_ids" mode).
        sql_ids: Optional list of SQL example IDs to fetch (for "specific_ids" mode).
        fact_ids: Optional list of fact IDs to fetch (for "specific_ids" mode).

    Returns:
        A DatabaseContext based on the specified context mode.

    Raises:
        AssertionError: If the context_mode is not one of the supported values.
    """  # noqa: E501
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
        case _:
            raise RuntimeError(f"unrecognized context mode: {context_mode}")


class IterationLimitExceededException(Exception):
    """Exception raised when iteration limit exceeded."""

    def __init__(self, limit: int):
        self.limit = limit
        self.message = f"Iteration limit exceeded: {limit}"
        super().__init__(self.message)


_SEARCH_TOOL_NAME = "search_for_context"


def _search_tool_definition() -> ToolDefinition:
    return ToolDefinition(
        name=_SEARCH_TOOL_NAME,
        description=(
            "Request additional database context by providing "
            "focused questions for semantic search. Use this when the current "
            "context is insufficient to generate a SQL query confidently. Frame "
            "your questions to target specific tables, relationships, or "
            "attributes needed."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "One or more natural language questions for a semantic search "
                        "to find database objects, SQL examples, or facts to provide "
                        "context. Questions should focus on a specific database "
                        "structure, relationship, or calculation. Avoid "
                        "explaining reasoning or context. Provide the search phrase "
                        "only."
                    ),
                }
            },
            "required": ["questions"],
        },
    )


_RECORD_TOOL_NAME = "record_sql_answer"


def _answer_tool_definition() -> ToolDefinition:
    return ToolDefinition(
        name=_RECORD_TOOL_NAME,
        description="Provide a SQL statement that addresses the user's question.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "sql_statement": {
                    "type": "string",
                    "description": (
                        "A valid SQL statement that accurately "
                        "addresses the user's prompt"
                    ),
                },
                "command_type": {
                    "type": "string",
                    "description": (
                        "Indicate the type of SQL command used in the sql_statement. "
                        "(e.g. 'SELECT', 'INSERT', 'UPDATE', or 'DELETE')"
                    ),
                },
                "relevant_object_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Indicate the ids of the database objects that were relevant "
                        "to answering the user's prompt"
                    ),
                },
                "relevant_sql_example_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Indicate the ids of the SQL examples that were relevant "
                        "to answering the user's prompt"
                    ),
                },
                "relevant_fact_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Indicate the ids of the facts that were relevant to "
                        "answering the user's prompt"
                    ),
                },
            },
            "required": [
                "sql_statement",
                "command_type",
                "relevant_object_ids",
                "relevant_sql_example_ids",
                "relevant_fact_ids",
            ],
        },
    )


async def _increment_obj_usage(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, ids: list[int]
) -> None:
    async with catalog_con.cursor() as cur:
        await cur.execute(
            SQL("""\
            update ai.{} set usage = usage + 1
            where id = any(%s)
        """).format(Identifier(f"semantic_catalog_obj_{catalog_id}")),
            (ids,),
        )


async def _increment_sql_usage(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, ids: list[int]
) -> None:
    async with catalog_con.cursor() as cur:
        await cur.execute(
            SQL("""\
            update ai.{} set usage = usage + 1
            where id = any(%s)
        """).format(Identifier(f"semantic_catalog_sql_{catalog_id}")),
            (ids,),
        )


async def _increment_fact_usage(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, ids: list[int]
) -> None:
    async with catalog_con.cursor() as cur:
        await cur.execute(
            SQL("""\
            update ai.{} set usage = usage + 1
            where id = any(%s)
        """).format(Identifier(f"semantic_catalog_fact_{catalog_id}")),
            (ids,),
        )


async def _freq_used_objects(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, n: int = 20
) -> list[dict[str, Any]]:
    async with catalog_con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            SQL("""\
            select
              id
            , objtype
            , array_to_string(objnames, '.') as name
            from ai.{}
            where objsubid = 0
            order by usage desc
            limit %s
        """).format(Identifier(f"semantic_catalog_obj_{catalog_id}")),
            (n,),
        )
        return [row for row in await cur.fetchall()]


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
    iteration_limit: int = 10,
    sample_size: int = 3,
    context_mode: ContextMode = "semantic_search",
    obj_ids: list[int] | None = None,
    sql_ids: list[int] | None = None,
    fact_ids: list[int] | None = None,
) -> GenerateSQLResponse:
    """Generate a SQL statement based on natural language prompt and database context.
    This function uses an AI model to generate a SQL statement that fulfills the user's
    request, drawing on context from the semantic catalog about database objects, SQL
    examples, and facts. The generated SQL is validated against the target database
    to ensure correctness, and refinement iterations are performed if needed.
    The function uses an iterative approach:
    1. Initialize database context based on the specified context mode
    2. Generate a SQL statement using the AI model with the context
    3. Validate the SQL statement against the target database
    4. If invalid, refine the SQL statement with error feedback
    5. Repeat until a valid SQL statement is generated or iteration limit is reached
    Args:
        catalog_con: Connection to the semantic catalog database.
        target_con: Connection to the target database where SQL will be executed.
        model: AI model to use for generating SQL (KnownModelName or Model instance).
        catalog_id: ID of the semantic catalog to use for context.
        embedding_name: Name of the embedding column to use for semantic search.
        embedding_config: Configuration for the embedding model.
        prompt: Natural language prompt describing the desired SQL statement.
        usage: Optional Usage object to track token usage across calls.
        usage_limits: Optional limits on token usage and requests.
        model_settings: Optional settings for the AI model.
        iteration_limit: Maximum number of refinement iterations (default: 5).
        sample_size: Number of sample rows to include for tables/views (default: 3).
        context_mode: Strategy for initializing database context:
            - "semantic_search": Find relevant items semantically (default)
            - "entire_catalog": Include all items from the catalog
            - "specific_ids": Include only items with specified IDs
        obj_ids: Optional list of database object IDs to include (for "specific_ids" mode).
        sql_ids: Optional list of SQL example IDs to include (for "specific_ids" mode).
        fact_ids: Optional list of fact IDs to include (for "specific_ids" mode).
    Returns:
        A GenerateSQLResponse containing:
        - The generated SQL statement
        - The database context used for generation
        - The query plan for the SQL statement
        - The final prompt sent to the model
        - The final response from the model
        - All messages exchanged during generation
        - Usage statistics for the AI model calls
    Raises:
        IterationLimitExceededException: If the iteration limit is reached without
            generating a valid SQL statement.
        RuntimeError: If the semantic catalog is not properly configured.
    Example:
        ```python
        # Generate a SQL statement for a natural language query
        response = await generate_sql(
            catalog_con=catalog_connection,
            target_con=db_connection,
            model="anthropic:claude-3-opus-20240229",
            catalog_id=1,
            embedding_name="openai_embeddings",
            embedding_config=config,
            prompt="Find all orders placed last month with a total value over $1000",
            iteration_limit=3,
        )
        # Use the generated SQL
        print(response.sql_statement)
        ```
    """  # noqa: E501
    usage = usage or Usage()
    usage_limits = usage_limits or UsageLimits(request_limit=None)
    model_settings = model_settings or ModelSettings()
    iteration_limit = max(int(iteration_limit), 1) or 5

    ctx = await initialize_database_context(
        catalog_con,
        target_con,
        catalog_id,
        embedding_name,
        embedding_config,
        prompt,
        sample_size=sample_size,
        context_mode=context_mode,
        obj_ids=obj_ids,
        sql_ids=sql_ids,
        fact_ids=fact_ids,
    )

    _continue = True
    freq_used_objects: list[dict[str, Any]] = await _freq_used_objects(
        catalog_con, catalog_id
    )
    prior_prompts: list[str] = [prompt]
    answer: str | None = None
    command_type: str | None = None
    pgversion: int | None = await _get_database_version(target_con)
    messages: list[ModelRequest | ModelResponse] = []
    user_prompt: str | None = None
    query_plan: dict[str, Any] | None = None
    error: str | None = None
    iteration = 0

    while _continue:
        iteration += 1
        if iteration > iteration_limit:
            raise IterationLimitExceededException(limit=iteration_limit)

        if usage_limits:
            usage_limits.check_before_request(usage)
            if usage_limits.has_token_limits():
                usage_limits.check_tokens(usage)

        system_prompt: str = _template_system_prompt.render(
            pgversion=pgversion, semantic_search_available=(iteration < iteration_limit)
        )

        user_prompt = _template_user_prompt.render(
            ctx=ctx,
            prompt=prompt,
            prior_prompts=prior_prompts,
            freq_used_objects=freq_used_objects,
            error=error,
        )

        model_response: ModelResponse = await model_request(
            model=model,
            messages=[
                ModelRequest(
                    parts=[
                        SystemPromptPart(content=system_prompt),
                        UserPromptPart(content=user_prompt),
                    ]
                )
            ],
            model_request_parameters=ModelRequestParameters(
                function_tools=[_search_tool_definition()]
                if iteration < iteration_limit
                else [],
                output_tools=[_answer_tool_definition()],
                allow_text_output=False,
            ),
            model_settings=model_settings,
        )

        messages.append(model_response)
        usage = usage + model_response.usage

        for part in model_response.parts:
            match part.part_kind:
                case "tool-call":
                    tool_call_part: ToolCallPart = part
                    args = tool_call_part.args_as_dict()
                    logger.info(f"tool call: {tool_call_part.tool_name}")
                    if tool_call_part.tool_name == _SEARCH_TOOL_NAME:
                        questions: list[str] = (
                            cast(list[str], args.get("questions")) or []
                        )
                        for q in questions:
                            prior_prompts.append(q)
                            logger.info(f"semantic search for '{q}'")
                            ctx = await fetch_database_context(
                                catalog_con,
                                target_con,
                                catalog_id,
                                embedding_name,
                                embedding_config,
                                q,
                                ctx,
                                sample_size=sample_size,
                            )
                    elif tool_call_part.tool_name == _RECORD_TOOL_NAME:
                        answer = args.get("sql_statement")
                        if not answer:
                            logger.error("llm did not provide a sql_statement")
                            continue
                        _continue = False
                        command_type = str(args["command_type"])
                        if command_type.upper() in (
                            "SELECT",
                            "INSERT",
                            "UPDATE",
                            "DELETE",
                            "MERGE",
                            "VALUES",
                        ):
                            logger.info("validating the sql statement")
                            query_plan, error = await validate_sql_statement(
                                target_con, str(answer)
                            )
                            if error:
                                logger.info(
                                    "asking llm to fix the invalid sql statement"
                                )
                                _continue = True
                                continue
                        relevant_object_ids: list[int] | None = cast(
                            list[int] | None, args.get("relevant_object_ids")
                        )
                        relevant_sql_example_ids: list[int] | None = cast(
                            list[int] | None, args.get("relevant_sql_example_ids")
                        )
                        relevant_fact_ids: list[int] | None = cast(
                            list[int] | None, args.get("relevant_fact_ids")
                        )
                        if relevant_object_ids:
                            for irrelevant_id in (
                                ctx.objects.keys() - relevant_object_ids
                            ):
                                ctx.objects.pop(irrelevant_id)
                                ctx.rendered_objects.pop(irrelevant_id)
                            await _increment_obj_usage(
                                catalog_con,
                                catalog_id,
                                [id for id in ctx.objects],
                            )
                        if relevant_sql_example_ids:
                            for irrelevant_id in (
                                ctx.sql_examples.keys() - relevant_sql_example_ids
                            ):
                                ctx.sql_examples.pop(irrelevant_id)
                                ctx.rendered_sql_examples.pop(irrelevant_id)
                            await _increment_sql_usage(
                                catalog_con,
                                catalog_id,
                                [id for id in ctx.sql_examples],
                            )
                        if relevant_fact_ids:
                            for irrelevant_id in ctx.facts.keys() - relevant_fact_ids:
                                ctx.facts.pop(irrelevant_id)
                                ctx.rendered_facts.pop(irrelevant_id)
                            await _increment_fact_usage(
                                catalog_con, catalog_id, [id for id in ctx.facts]
                            )
                    else:
                        logger.error(
                            f"unrecognized tool name: {tool_call_part.tool_name}"
                        )
                case "text":
                    text_part: TextPart = part
                    logger.error(
                        f"unexpected textual model response: {text_part.content}"
                    )
                case _:
                    logger.error(f"unrecognized model response kind: {part.part_kind}")

    assert answer is not None, "answer is unexpectedly missing"
    return GenerateSQLResponse(
        sql_statement=answer,
        context=ctx,
        command_type=command_type or "UNKNOWN",
        query_plan=query_plan or {},
        final_prompt=user_prompt or "MISSING",
        messages=messages,
        usage=usage,
    )

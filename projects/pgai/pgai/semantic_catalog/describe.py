"""Module for generating descriptions of database objects using AI.

This module provides functionality for finding database objects (tables, views, procedures)
and generating natural language descriptions for them using AI models. These descriptions
can be used to populate a semantic catalog, making it easier for users to understand
the database schema and its purpose.
"""  # noqa: E501

import logging
from collections.abc import Callable
from typing import Any, TextIO

import psycopg
from psycopg.sql import SQL, Composable
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage, UsageLimits
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from pgai.semantic_catalog import TargetConnection, file, loader, render
from pgai.semantic_catalog.models import Procedure, Table, View

logger = logging.getLogger(__name__)


async def find_tables(
    con: TargetConnection,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_table: str | None = None,
    exclude_table: str | None = None,
    include_extensions: list[str] | None = None,
) -> list[int]:
    """Find PostgreSQL tables matching specified criteria.

    Searches the database for tables that match the specified inclusion/exclusion patterns
    for schemas and table names. System schemas and TimescaleDB internal schemas are excluded.
    Regular, foreign, and partitioned tables are included.

    Args:
        con: Database connection to use for the search.
        include_schema: Regular expression pattern for schemas to include (optional).
        exclude_schema: Regular expression pattern for schemas to exclude (optional).
        include_table: Regular expression pattern for tables to include (optional).
        exclude_table: Regular expression pattern for tables to exclude (optional).

    Returns:
        A list of PostgreSQL object IDs (OIDs) for the matching tables.
    """  # noqa: E501
    async with con.cursor() as cur:
        filters: list[Composable] = []
        params: dict[str, Any] = {}
        if include_schema:
            filters.append(SQL("\nand n.nspname ~ %(include_schema)s"))
            params["include_schema"] = include_schema
        if exclude_schema:
            filters.append(SQL("\nand n.nspname !~ %(exclude_schema)s"))
            params["exclude_schema"] = exclude_schema
        if include_table:
            filters.append(SQL("\nand c.relname ~ %(include_table)s"))
            params["include_table"] = include_table
        if exclude_table:
            filters.append(SQL("\nand c.relname !~ %(exclude_table)s"))
            params["exclude_table"] = exclude_table
        combined_filters = SQL(" ").join(filters) if filters else SQL("")
        extension_filter = SQL("")
        if include_extensions:
            extension_filter = SQL("and x.extname != any(%(include_extensions)s)")
            params["include_extensions"] = include_extensions
        query = SQL("""\
            select c.oid
            from pg_catalog.pg_class c
            inner join pg_catalog.pg_namespace n
                on (c.relnamespace = n.oid)
            where n.nspname not like 'pg_%%'
            and n.nspname != 'information_schema'
            and n.nspname != '_timescaledb_internal'
            and n.nspname != 'ai'
            and c.relkind in ('r', 'f', 'p')
            {filters}
            and not exists
            (
                select 1
                from pg_catalog.pg_depend d
                inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
                where d.classid = 'pg_catalog.pg_class'::regclass::oid
                and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
                and d.deptype = 'e'
                and d.objid = c.oid
                {extension_filter}
            )
        """).format(filters=combined_filters, extension_filter=extension_filter)
        await cur.execute(query, params)
        tables = [int(row[0]) for row in await cur.fetchall()]
        logger.debug(f"found {len(tables)} tables")
        return tables


async def find_views(
    con: TargetConnection,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_view: str | None = None,
    exclude_view: str | None = None,
    include_extensions: list[str] | None = None,
) -> list[int]:
    """Find PostgreSQL views matching specified criteria.

    Searches the database for views that match the specified inclusion/exclusion patterns
    for schemas and view names. System schemas and TimescaleDB internal schemas are excluded.
    Regular and materialized views are included.

    Args:
        con: Database connection to use for the search.
        include_schema: Regular expression pattern for schemas to include (optional).
        exclude_schema: Regular expression pattern for schemas to exclude (optional).
        include_view: Regular expression pattern for views to include (optional).
        exclude_view: Regular expression pattern for views to exclude (optional).

    Returns:
        A list of PostgreSQL object IDs (OIDs) for the matching views.
    """  # noqa: E501
    async with con.cursor() as cur:
        filters: list[Composable] = []
        params: dict[str, Any] = {}
        if include_schema:
            filters.append(SQL("\nand n.nspname ~ %(include_schema)s"))
            params["include_schema"] = include_schema
        if exclude_schema:
            filters.append(SQL("\nand n.nspname !~ %(exclude_schema)s"))
            params["exclude_schema"] = exclude_schema
        if include_view:
            filters.append(SQL("\nand c.relname ~ %(include_view)s"))
            params["include_view"] = include_view
        if exclude_view:
            filters.append(SQL("\nand c.relname !~ %(exclude_view)s"))
            params["exclude_view"] = exclude_view
        combined_filters = SQL(" ").join(filters) if filters else SQL("")
        extension_filter = SQL("")
        if include_extensions:
            extension_filter = SQL("and x.extname != any(%(include_extensions)s)")
            params["include_extensions"] = include_extensions
        query = SQL("""\
            select c.oid
            from pg_catalog.pg_class c
            inner join pg_catalog.pg_namespace n
                on (c.relnamespace = n.oid)
            where n.nspname not like 'pg_%%'
            and n.nspname != 'information_schema'
            and n.nspname != '_timescaledb_internal'
            and n.nspname != 'ai'
            and c.relkind in ('v', 'm')
            {filters}
            and not exists
            (
                select 1
                from pg_catalog.pg_depend d
                inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
                where d.classid = 'pg_catalog.pg_class'::regclass::oid
                and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
                and d.deptype = 'e'
                and d.objid = c.oid
                {extension_filter}
            )
        """).format(filters=combined_filters, extension_filter=extension_filter)
        await cur.execute(query, params)
        views = [int(row[0]) for row in await cur.fetchall()]
        logger.debug(f"found {len(views)} views")
        return views


async def find_procedures(
    con: TargetConnection,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_proc: str | None = None,
    exclude_proc: str | None = None,
    include_extensions: list[str] | None = None,
) -> list[int]:
    """Find PostgreSQL procedures and functions matching specified criteria.

    Searches the database for procedures and functions that match the specified
    inclusion/exclusion patterns for schemas and procedure/function names.
    System schemas and TimescaleDB internal schemas are excluded.

    Args:
        con: Database connection to use for the search.
        include_schema: Regular expression pattern for schemas to include (optional).
        exclude_schema: Regular expression pattern for schemas to exclude (optional).
        include_proc: Regular expression pattern for procedures/functions to include (optional).
        exclude_proc: Regular expression pattern for procedures/functions to exclude (optional).

    Returns:
        A list of PostgreSQL object IDs (OIDs) for the matching procedures and functions.
    """  # noqa: E501
    async with con.cursor() as cur:
        filters: list[Composable] = []
        params: dict[str, Any] = {}
        if include_schema:
            filters.append(SQL("\nand n.nspname ~ %(include_schema)s"))
            params["include_schema"] = include_schema
        if exclude_schema:
            filters.append(SQL("\nand n.nspname !~ %(exclude_schema)s"))
            params["exclude_schema"] = exclude_schema
        if include_proc:
            filters.append(SQL("\nand p.proname ~ %(include_proc)s"))
            params["include_proc"] = include_proc
        if exclude_proc:
            filters.append(SQL("\nand p.proname !~ %(exclude_proc)s"))
            params["exclude_proc"] = exclude_proc
        combined_filters = SQL(" ").join(filters) if filters else SQL("")
        extension_filter = SQL("")
        if include_extensions:
            extension_filter = SQL("and x.extname != any(%(include_extensions)s)")
            params["include_extensions"] = include_extensions
        query = SQL("""\
            select p.oid
            from pg_catalog.pg_proc p
            inner join pg_catalog.pg_namespace n
                on (p.pronamespace = n.oid)
            where n.nspname not like 'pg_%%'
            and n.nspname != 'information_schema'
            and n.nspname != '_timescaledb_internal'
            and n.nspname != 'ai'
            {filters}
            and not exists
            (
                select 1
                from pg_catalog.pg_depend d
                inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
                where d.classid = 'pg_catalog.pg_proc'::regclass::oid
                and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
                and d.deptype = 'e'
                and d.objid = p.oid
                {extension_filter}
            )
        """).format(filters=combined_filters, extension_filter=extension_filter)
        await cur.execute(query, params)
        procs = [int(row[0]) for row in await cur.fetchall()]
        logger.debug(f"found {len(procs)} procedures")
        return procs


async def generate_table_descriptions(
    con: TargetConnection,
    oids: list[int],
    model: KnownModelName | Model,
    callback: Callable[[file.Table], None],
    progress_callback: Callable[[str], None] | None = None,
    usage: Usage | None = None,
    usage_limits: UsageLimits | None = None,
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
    sample_size: int = 3,
) -> Usage:
    """Generate natural language descriptions for tables and their columns using AI.

    Retrieves table metadata from the database in batches, renders it, and uses an AI model
    to generate concise descriptions for each table and column. The descriptions are provided
    to the callback function as they are generated.

    Args:
        con: Database connection to use for loading table metadata.
        oids: List of PostgreSQL object IDs for the tables to describe.
        model: AI model to use for generating descriptions.
        callback: Function to call with each generated table description.
        progress_callback: Optional function to call with progress updates.
        usage: Optional Usage object to track API usage across multiple calls.
        usage_limits: Optional UsageLimits object to set limits on API usage.
        model_settings: Optional settings for the AI model.
        batch_size: Number of tables to process in each batch (default: 5).
        sample_size: Number of sample rows to include for each table (default: 3).

    Returns:
        Updated Usage object with information about token usage.
    """  # noqa: E501

    def batches(batch_size: int):
        for i in range(0, len(oids), batch_size):
            yield oids[i : i + batch_size]

    usage = usage or Usage()
    usage_limits = usage_limits or UsageLimits(request_limit=None)
    table_index: dict[int, file.Table] = {}

    for batch in batches(batch_size):
        logger.debug(f"loading details for batch of {len(batch)} tables")
        tables: list[Table] = await loader.load_tables(
            con, batch, sample_size=sample_size
        )
        table_index.clear()
        for table in tables:
            table_index[table.objid] = file.Table(
                schema=table.schema_name,
                name=table.table_name,
                description="",
                columns=[
                    file.Column(name=c.name, description="")
                    for c in (table.columns or [])  # noqa: E501
                ],
            )
        logger.debug(f"rendering details for batch of {len(batch)} tables")
        rendered: str = render.render_tables(tables)
        prompt = (
            (
                "Below are representations of one or more PostgreSQL tables. "
                "Generate a natural language description for each table and column represented. "  # noqa: E501
                "Use tools to record your description. Respond ONLY with 'done' when finished. "  # noqa: E501
                "\n\n"
            )
            + rendered
        )

        agent = Agent(
            model,
            model_settings=model_settings,
            name="table-describer",
            system_prompt=(
                "You are a SQL expert who generates natural language descriptions of tables in a PostgreSQL database. "  # noqa: E501
                "The descriptions that you generate should be a concise, single sentence."  # noqa: E501
            ),
        )

        @agent.tool_plain
        def record_table_description(table_id: int, description: str) -> None:  # pyright: ignore [reportUnusedFunction]
            """Records the description of a table

            Args:
                table_id (int): The ID of the table (specified in the XML tag)
                description (str): a concise, single sentence description of the table
            """
            nonlocal table_index
            table = table_index.get(table_id)
            if table is None:
                logger.warning(f"invalid table id provided by LLM: {table_id}")
                return
            logger.debug(
                f"recording description for table {table.schema_name}.{table.name}"  # noqa: E501
            )
            table.description = description
            if progress_callback:
                progress_callback(".".join([table.schema_name, table.name]))

        @agent.tool_plain
        def record_column_description(  # pyright: ignore [reportUnusedFunction]
            table_id: int, column_name: str, description: str
        ) -> None:
            """Records the description of a column

            Args:
                table_id (int): The ID of the table (specified in the XML tag)
                column_name (str): the name of the column
                description (str): a concise, single sentence description of the column
            """
            nonlocal table_index
            table = table_index.get(table_id)
            if table is None:
                logger.warning(
                    f"invalid table id provided by LLM: {table_id} {column_name}"
                )  # noqa: E501
                return
            if not table.columns:
                logger.warning(
                    f"column described by LLM but table has no columns: {table_id} {column_name}"  # noqa: E501
                )
                return
            column = next((c for c in table.columns if c.name == column_name), None)
            if column is None:
                logger.warning(
                    f"invalid column provided by LLM: {table_id} {column_name}"
                )  # noqa: E501
                return
            column.description = description
            logger.debug(
                f"recording description for column {table.schema_name}.{table.name}.{column.name}"  # noqa
            )
            if progress_callback:
                progress_callback(
                    ".".join([table.schema_name, table.name, column_name])
                )

        logger.debug(f"asking llm to generate descriptions for {len(batch)} tables")
        result = await agent.run(
            user_prompt=prompt, usage_limits=usage_limits, usage=usage
        )
        usage = result.usage()

        for table in table_index.values():
            callback(table)

    return usage


async def generate_view_descriptions(
    con: TargetConnection,
    oids: list[int],
    model: KnownModelName | Model,
    callback: Callable[[file.View], None],
    progress_callback: Callable[[str], None] | None = None,
    usage: Usage | None = None,
    usage_limits: UsageLimits | None = None,
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
    sample_size: int = 3,
) -> Usage:
    """Generate natural language descriptions for views and their columns using AI.

    Retrieves view metadata from the database in batches, renders it, and uses an AI model
    to generate concise descriptions for each view and column. The descriptions are provided
    to the callback function as they are generated.

    Args:
        con: Database connection to use for loading view metadata.
        oids: List of PostgreSQL object IDs for the views to describe.
        model: AI model to use for generating descriptions.
        callback: Function to call with each generated view description.
        progress_callback: Optional function to call with progress updates.
        usage: Optional Usage object to track API usage across multiple calls.
        usage_limits: Optional UsageLimits object to set limits on API usage.
        model_settings: Optional settings for the AI model.
        batch_size: Number of views to process in each batch (default: 5).
        sample_size: Number of sample rows to include for each view (default: 3).

    Returns:
        Updated Usage object with information about token usage.
    """  # noqa: E501

    def batches(batch_size: int):
        for i in range(0, len(oids), batch_size):
            yield oids[i : i + batch_size]

    usage = usage or Usage()
    usage_limits = usage_limits or UsageLimits(request_limit=None)
    view_index: dict[int, file.View] = {}

    for batch in batches(batch_size):
        logger.debug(f"loading details for batch of {len(batch)} views")
        views: list[View] = await loader.load_views(con, batch, sample_size=sample_size)
        view_index.clear()
        for view in views:
            view_index[view.objid] = file.View(
                schema=view.schema_name,
                name=view.view_name,
                description="",
                columns=[
                    file.Column(name=c.name, description="")
                    for c in (view.columns or [])  # noqa: E501
                ],
            )

        logger.debug(f"rendering details for batch of {len(batch)} views")
        rendered: str = render.render_views(views)
        prompt = (
            (
                "Below are representations of one or more PostgreSQL views. "
                "Generate a natural language description for each view and column represented. "  # noqa: E501
                "Use tools to record your description. Respond ONLY with 'done' when finished. "  # noqa: E501
                "\n\n"
            )
            + rendered
        )

        agent = Agent(
            model,
            model_settings=model_settings,
            name="view-describer",
            system_prompt=(
                "You are a SQL expert who generates natural language descriptions of views in a PostgreSQL database. "  # noqa: E501
                "The descriptions that you generate should be a concise, single sentence."  # noqa: E501
            ),
        )

        @agent.tool_plain
        def record_view_description(view_id: int, description: str) -> None:  # pyright: ignore [reportUnusedFunction]
            """Records the description of a view

            Args:
                view_id (int): The ID of the view (specified in the XML tag)
                description (str): a concise, single sentence description of the view
            """
            nonlocal view_index
            view = view_index.get(view_id)
            if view is None:
                logger.warning(f"invalid view id provided by LLM: {view_id}")
                return
            logger.debug(
                f"recording description for view {view.schema_name}.{view.name}"
            )
            view.description = description
            if progress_callback:
                progress_callback(".".join([view.schema_name, view.name]))

        @agent.tool_plain
        def record_column_description(  # pyright: ignore [reportUnusedFunction]
            view_id: int, column_name: str, description: str
        ) -> None:
            """Records the description of a column

            Args:
                view_id (int): The ID of the view (specified in the XML tag)
                column_name (str): the name of the column in the view
                description (str): a concise, single sentence description of the column
            """
            nonlocal view_index
            view = view_index.get(view_id)
            if view is None:
                logger.warning(
                    f"invalid view id provided by LLM: {view_id} {column_name}"
                )
                return
            if not view.columns:
                logger.warning(
                    f"column description provided for view but view has no columns: {view_id} {column_name}"  # noqa
                )
                return
            column = next((c for c in view.columns if c.name == column_name), None)
            if column is None:
                logger.warning(
                    f"invalid view column provided by LLM: {view_id} {column_name}"
                )
                return
            column.description = description
            logger.debug(
                f"recording description for view column {view.schema_name}.{view.name}.{column.name}"  # noqa
            )
            if progress_callback:
                progress_callback(".".join([view.schema_name, view.name, column.name]))

        logger.debug(f"asking llm to generate descriptions for {len(batch)} views")
        result = await agent.run(
            user_prompt=prompt, usage_limits=usage_limits, usage=usage
        )
        usage = result.usage()

        for view in view_index.values():
            callback(view)

    return usage


async def generate_procedure_descriptions(
    con: TargetConnection,
    oids: list[int],
    model: KnownModelName | Model,
    callback: Callable[[file.Function | file.Procedure | file.Aggregate], None],
    progress_callback: Callable[[str], None] | None = None,
    usage: Usage | None = None,
    usage_limits: UsageLimits | None = None,
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
) -> Usage:
    """Generate natural language descriptions for procedures and functions using AI.

    Retrieves procedure/function metadata from the database in batches, renders it, and uses
    an AI model to generate concise descriptions. The descriptions are provided
    to the callback function as they are generated. Supports procedures, functions, and aggregates.

    Args:
        con: Database connection to use for loading procedure metadata.
        oids: List of PostgreSQL object IDs for the procedures to describe.
        model: AI model to use for generating descriptions.
        callback: Function to call with each generated procedure description.
        progress_callback: Optional function to call with progress updates.
        usage: Optional Usage object to track API usage across multiple calls.
        usage_limits: Optional UsageLimits object to set limits on API usage.
        model_settings: Optional settings for the AI model.
        batch_size: Number of procedures to process in each batch (default: 5).

    Returns:
        Updated Usage object with information about token usage.
    """  # noqa: E501

    def batches(batch_size: int):
        for i in range(0, len(oids), batch_size):
            yield oids[i : i + batch_size]

    usage = usage or Usage()
    usage_limits = usage_limits or UsageLimits(request_limit=None)
    proc_index: dict[int, file.Function | file.Procedure | file.Aggregate] = {}

    for batch in batches(batch_size):
        logger.debug(f"loading details for batch of {len(batch)} procedures")
        procs: list[Procedure] = await loader.load_procedures(con, batch)
        proc_index.clear()
        for proc in procs:
            match proc.kind:
                case "function":
                    proc_index[proc.objid] = file.Function(
                        schema=proc.schema_name,
                        name=proc.proc_name,
                        args=proc.objargs,
                        description="",
                    )
                case "procedure":
                    proc_index[proc.objid] = file.Procedure(
                        schema=proc.schema_name,
                        name=proc.proc_name,
                        args=proc.objargs,
                        description="",
                    )
                case "aggregate":
                    proc_index[proc.objid] = file.Aggregate(
                        schema=proc.schema_name,
                        name=proc.proc_name,
                        args=proc.objargs,
                        description="",
                    )

        logger.debug(f"rendering details for batch of {len(batch)} procedures")
        rendered: str = render.render_procedures(procs)
        prompt = (
            (
                "Below are representations of one or more PostgreSQL procedures/functions. "  # noqa
                "Generate a natural language description for each procedure/function represented. "  # noqa
                "Use the tool to record your description. Respond ONLY with 'done' when finished. "  # noqa
                "\n\n"
            )
            + rendered
        )

        agent = Agent(
            model,
            model_settings=model_settings,
            name="procedure-describer",
            system_prompt=(
                "You are a SQL expert who generates natural language descriptions of procedures and functions in a PostgreSQL database. "  # noqa: E501
                "The descriptions that you generate should be a concise, single sentence."  # noqa: E501
            ),
        )

        @agent.tool_plain
        def record_description(proc_id: int, description: str) -> None:  # pyright: ignore [reportUnusedFunction]
            """Records the description of a procedure or function

            Args:
                proc_id (int): The ID of the procedure or function (specified in the XML tag)
                description (str): a concise, single sentence description of the procedure/function
            """  # noqa: E501
            nonlocal proc_index
            proc = proc_index.get(proc_id)
            if proc is None:
                logger.warning(f"invalid procedure id provided by LLM: {proc_id}")
                return
            logger.debug(
                f"recording description for procedure {proc.schema_name}.{proc.name}"
            )
            proc.description = description
            if progress_callback:
                progress_callback(".".join([proc.schema_name, proc.name]))
            callback(proc)

        logger.debug(f"asking llm to generate descriptions for {len(batch)} procedures")
        result = await agent.run(
            user_prompt=prompt, usage_limits=usage_limits, usage=usage
        )
        usage = result.usage()
    return usage


async def _count_columns(con: psycopg.AsyncConnection, oids: list[int]) -> int:
    """Count the number of columns in the specified tables or views.

    Queries the database to count the total number of columns in the tables or views
    with the given object IDs. Used to track progress when describing tables and views.

    Args:
        con: Database connection to use for the query.
        oids: List of PostgreSQL object IDs for the tables or views.

    Returns:
        The total number of columns in the specified tables or views.
    """
    async with con.cursor() as cur:
        await cur.execute(
            """\
            select count(*)
            from pg_class k
            inner join pg_attribute a on (k.oid = a.attrelid)
            where k.oid = any(%s)
            and not a.attisdropped
            and a.attnum > 0
        """,
            (oids,),
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def _class_names(
    con: psycopg.AsyncConnection, oids: list[int]
) -> list[tuple[str, str]]:
    async with con.cursor() as cur:
        await cur.execute(
            """\
            select
              case
                when k.relkind in ('r', 'p', 'f')
                    then 'Table'
                when k.relkind in ('v', 'm')
                    then 'View'
              end
            , n.nspname || '.' || k.relname
            from pg_class k
            inner join pg_namespace n on (k.relnamespace = n.oid)
            where k.oid = any(%s)
            order by n.nspname, k.relname
        """,
            (oids,),
        )
        return [(str(row[0]), str(row[1])) for row in await cur.fetchall()]


async def _proc_names(
    con: psycopg.AsyncConnection, oids: list[int]
) -> list[tuple[str, str]]:
    async with con.cursor() as cur:
        await cur.execute(
            """\
            select
              case p.prokind
                when 'f' then 'Function'
                when 'p' then 'Procedure'
                when 'a' then 'Aggregate'
                when 'w' then 'Window Function'
              end
            , format
              ( '%%s.%%s(%%s)'
              , n.nspname
              , p.proname
              , pg_get_function_identity_arguments(p.oid)
              )
            from pg_proc p
            inner join pg_namespace n on (p.pronamespace = n.oid)
            where p.oid = any(%s)
            order by n.nspname, p.proname
        """,
            (oids,),
        )
        return [(str(row[0]), str(row[1])) for row in await cur.fetchall()]


async def describe(
    db_url: str,
    model: KnownModelName | Model,
    output: TextIO,
    console: Console | None = None,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_table: str | None = None,
    exclude_table: str | None = None,
    include_view: str | None = None,
    exclude_view: str | None = None,
    include_proc: str | None = None,
    exclude_proc: str | None = None,
    include_extensions: list[str] | None = None,
    usage: Usage | None = None,
    usage_limits: UsageLimits | None = None,
    batch_size: int = 5,
    sample_size: int = 3,
    dry_run: bool = False,
) -> Usage:
    """Generate natural language descriptions for database objects and export them to YAML.

    This is the main entry point for the describe functionality. It finds database objects
    matching the specified criteria, generates descriptions for them using AI, and writes
    the results to the output file in YAML format. Progress is tracked and displayed using
    the rich console.

    Args:
        db_url: Database connection URL.
        model: AI model to use for generating descriptions.
        output: Text output stream to write the YAML data to.
        console: Optional Rich console for displaying progress and messages.
        include_schema: Regular expression pattern for schemas to include (optional).
        exclude_schema: Regular expression pattern for schemas to exclude (optional).
        include_table: Regular expression pattern for tables to include (optional).
        exclude_table: Regular expression pattern for tables to exclude (optional).
        include_view: Regular expression pattern for views to include (optional).
        exclude_view: Regular expression pattern for views to exclude (optional).
        include_proc: Regular expression pattern for procedures to include (optional).
        exclude_proc: Regular expression pattern for procedures to exclude (optional).
        usage: Optional Usage object to track API usage across multiple calls.
        usage_limits: Optional UsageLimits object to set limits on API usage.
        batch_size: Number of objects to process in each batch (default: 5).
        sample_size: Number of sample rows to include for tables and views (default: 3).

    Returns:
        Updated Usage object with information about token usage.
    """  # noqa: E501
    usage = usage or Usage()
    usage_limits = usage_limits or UsageLimits(request_limit=None)

    if console is None:
        console = Console(quiet=True)

    async with await psycopg.AsyncConnection.connect(db_url) as con:
        # find tables
        with console.status("finding tables..."):
            table_oids = await find_tables(
                con,
                include_schema,
                exclude_schema,
                include_table,
                exclude_table,
                include_extensions,
            )
        # find views
        with console.status("finding views..."):
            view_oids = await find_views(
                con,
                include_schema,
                exclude_schema,
                include_view,
                exclude_view,
                include_extensions,
            )
        # find procedures
        with console.status("finding procedures/functions..."):
            proc_oids = await find_procedures(
                con,
                include_schema,
                exclude_schema,
                include_proc,
                exclude_proc,
                include_extensions,
            )
        if len(table_oids) == 0:
            console.print(":warning: no tables found.")
        else:
            console.print(f"tables found: {len(table_oids)}")
        if len(view_oids) == 0:
            console.print(":warning: no views found.")
        else:
            console.print(f"views found: {len(view_oids)}")
        if len(proc_oids) == 0:
            console.print(":warning: no procedures/functions found.")
        else:
            console.print(f"procedures/functions found: {len(proc_oids)}")

        if dry_run:
            from rich.table import Table

            table = Table(title="Objects Found", expand=True)
            table.add_column("Type")
            table.add_column("Name")
            for t in await _class_names(con, table_oids):
                table.add_row(t[0], t[1])
            for v in await _class_names(con, view_oids):
                table.add_row(v[0], v[1])
            for p in await _proc_names(con, proc_oids):
                table.add_row(p[0], p[1])
            console.print(table)
            return usage

        total_table = (
            len(table_oids) + (await _count_columns(con, table_oids))
            if len(table_oids) > 0
            else 0
        )
        total_view = (
            len(view_oids) + (await _count_columns(con, view_oids))
            if len(view_oids) > 0
            else 0
        )
        total_proc = len(proc_oids)

        pbcols = [
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        ]

        output.write(file.Header().to_yaml())
        output.flush()

        with Progress(*pbcols, console=console) as progress:
            # tables/columns
            if total_table > 0:
                task_table = progress.add_task(
                    "generate table/column descriptions",
                    total=total_table,
                    visible=total_table > 0,
                )

                def table_callback(t: file.Table):
                    output.write(t.to_yaml())
                    output.flush()

                def table_progress_callback(msg: str):
                    nonlocal progress, task_table
                    progress.console.print(msg)
                    progress.update(task_table, advance=1.0)

                usage = await generate_table_descriptions(
                    con,
                    table_oids,
                    model,
                    table_callback,
                    progress_callback=table_progress_callback,
                    usage=usage,
                    usage_limits=usage_limits,
                    batch_size=batch_size,
                    sample_size=sample_size,
                )

            # views/columns
            if total_view > 0:
                task_view = progress.add_task(
                    "generate view/column descriptions",
                    total=total_view,
                    visible=total_view > 0,
                )

                def view_callback(v: file.View):
                    output.write(v.to_yaml())
                    output.flush()

                def view_progress_callback(msg: str):
                    nonlocal progress, task_view
                    progress.console.print(msg)
                    progress.update(task_view, advance=1.0)

                usage = await generate_view_descriptions(
                    con,
                    view_oids,
                    model,
                    view_callback,
                    progress_callback=view_progress_callback,
                    usage=usage,
                    usage_limits=usage_limits,
                    batch_size=batch_size,
                    sample_size=sample_size,
                )

            # procedures/functions
            if total_proc > 0:
                task_proc = progress.add_task(
                    "generate procedure/function descriptions", total=total_proc
                )

                def proc_callback(x: file.Function | file.Procedure | file.Aggregate):
                    output.write(x.to_yaml())
                    output.flush()

                def proc_progress_callback(msg: str):
                    nonlocal progress, task_proc
                    progress.console.print(msg)
                    progress.update(task_proc, advance=1.0)

                usage = await generate_procedure_descriptions(
                    con,
                    proc_oids,
                    model,
                    proc_callback,
                    progress_callback=proc_progress_callback,
                    usage=usage,
                    usage_limits=usage_limits,
                    batch_size=batch_size,
                )

    output.flush()

    from rich.table import Table

    table = Table(title="Usage")

    table.add_column("Metric", justify="left", no_wrap=True)
    table.add_column("Value", justify="right", no_wrap=True)

    table.add_row("Requests", str(usage.requests))
    table.add_row(
        "Request Tokens",
        str(usage.request_tokens) if usage.request_tokens else "?",  # noqa: E501
    )
    table.add_row(
        "Response Tokens",
        str(usage.response_tokens) if usage.response_tokens else "?",  # noqa: E501
    )
    table.add_row(
        "Total Tokens",
        str(usage.total_tokens) if usage.total_tokens else "?",  # noqa: E501
    )

    console.print(table)

    return usage

from collections.abc import Callable
from typing import Literal, TextIO

import psycopg
from psycopg.sql import SQL, Composable
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage

from pgai.semantic_catalog import TargetConnection, loader, render
from pgai.semantic_catalog.models import ObjectDescription, Procedure, Table, View


async def find_tables(
    con: TargetConnection,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_table: str | None = None,
    exclude_table: str | None = None,
) -> list[int]:
    async with con.cursor() as cur:
        filters: list[Composable] = []
        params: dict[str, str] = {}
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
        query = SQL("""\
            select c.oid
            from pg_catalog.pg_class c
            inner join pg_catalog.pg_namespace n
                on (c.relnamespace = n.oid)
            where n.nspname not like 'pg_%%'
            and n.nspname != 'information_schema'
            and c.relkind in ('r', 'f', 'p')
            {filters}
        """).format(filters=combined_filters)
        await cur.execute(query, params)
        return [int(row[0]) for row in await cur.fetchall()]


async def find_views(
    con: TargetConnection,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_view: str | None = None,
    exclude_view: str | None = None,
) -> list[int]:
    async with con.cursor() as cur:
        filters: list[Composable] = []
        params: dict[str, str] = {}
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
        query = SQL("""\
            select c.oid
            from pg_catalog.pg_class c
            inner join pg_catalog.pg_namespace n
                on (c.relnamespace = n.oid)
            where n.nspname not like 'pg_%%'
            and n.nspname != 'information_schema'
            and c.relkind in ('v', 'm')
            {filters}
        """).format(filters=combined_filters)
        await cur.execute(query, params)
        return [int(row[0]) for row in await cur.fetchall()]


async def find_procedures(
    con: TargetConnection,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_proc: str | None = None,
    exclude_proc: str | None = None,
) -> list[int]:
    async with con.cursor() as cur:
        filters: list[Composable] = []
        params: dict[str, str] = {}
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
        query = SQL("""\
            select p.oid
            from pg_catalog.pg_proc p
            inner join pg_catalog.pg_namespace n
                on (p.pronamespace = n.oid)
            where n.nspname not like 'pg_%%'
            and n.nspname != 'information_schema'
            {filters}
        """).format(filters=combined_filters)
        await cur.execute(query, params)
        return [int(row[0]) for row in await cur.fetchall()]


async def generate_table_descriptions(
    con: TargetConnection,
    oids: list[int],
    model: KnownModelName | Model,
    callback: Callable[[ObjectDescription], None],
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
) -> Usage:
    def batches():
        for i in range(0, len(oids), batch_size):
            yield oids[i : i + batch_size]

    table_index: dict[int, Table] = {}

    agent = Agent(
        model,
        model_settings=model_settings,
        name="table-describer",
        system_prompt=(
            "You are a SQL expert who generates natural language descriptions of tables in a PostgreSQL database. "  # noqa: E501
            "The descriptions that you generate should be a concise, single sentence."
        ),
    )

    @agent.tool_plain
    def record_table_description(table_id: int, description: str) -> None:  # pyright: ignore [reportUnusedFunction]
        """Records the description of a table

        Args:
            table_id (int): The ID of the table (specified in the XML tag)
            description (str): a concise, single sentence description of the table
        """
        table = table_index.get(table_id)
        if table is None:
            # TODO: handle this somehow
            return
        callback(
            ObjectDescription(
                classid=table.classid,
                objid=table.objid,
                objsubid=0,
                objtype="table",
                objnames=[table.schema_name, table.table_name],
                objargs=[],
                description=description,
            )
        )

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
        table = table_index.get(table_id)
        if table is None:
            # TODO: handle this somehow
            return
        if not table.columns:
            # TODO: handle this somehow
            return
        column = next((c for c in table.columns if c.name == column_name), None)
        if column is None:
            # TODO: handle this somehow
            return
        callback(
            ObjectDescription(
                classid=column.classid,
                objid=column.objid,
                objsubid=column.objsubid,
                objtype="table column",
                objnames=[table.schema_name, table.table_name, column_name],
                objargs=[],
                description=description,
            )
        )

    usage: Usage = Usage()
    for batch in batches():
        tables: list[Table] = await loader.load_tables(con, batch)
        table_index = {table.objid: table for table in tables}
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
        result = await agent.run(user_prompt=prompt)
        usage = usage + result.usage()
    return usage


async def generate_view_descriptions(
    con: TargetConnection,
    oids: list[int],
    model: KnownModelName | Model,
    callback: Callable[[ObjectDescription], None],
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
) -> Usage:
    def batches():
        for i in range(0, len(oids), batch_size):
            yield oids[i : i + batch_size]

    view_index: dict[int, View] = {}

    agent = Agent(
        model,
        model_settings=model_settings,
        name="view-describer",
        system_prompt=(
            "You are a SQL expert who generates natural language descriptions of views in a PostgreSQL database. "  # noqa: E501
            "The descriptions that you generate should be a concise, single sentence."
        ),
    )

    @agent.tool_plain
    def record_view_description(view_id: int, description: str) -> None:  # pyright: ignore [reportUnusedFunction]
        """Records the description of a view

        Args:
            view_id (int): The ID of the view (specified in the XML tag)
            description (str): a concise, single sentence description of the view
        """
        view = view_index.get(view_id)
        if view is None:
            # TODO: handle this somehow
            return
        callback(
            ObjectDescription(
                classid=view.classid,
                objid=view.objid,
                objsubid=0,
                objtype="view",
                objnames=[view.schema_name, view.view_name],
                objargs=[],
                description=description,
            )
        )

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
        view = view_index.get(view_id)
        if view is None:
            # TODO: handle this somehow
            return
        if not view.columns:
            # TODO: handle this somehow
            return
        column = next((c for c in view.columns if c.name == column_name), None)
        if column is None:
            # TODO: handle this somehow
            return
        callback(
            ObjectDescription(
                classid=column.classid,
                objid=column.objid,
                objsubid=column.objsubid,
                objtype="view column",
                objnames=[view.schema_name, view.view_name, column_name],
                objargs=[],
                description=description,
            )
        )

    usage: Usage = Usage()
    for batch in batches():
        views: list[View] = await loader.load_views(con, batch)
        view_index = {view.objid: view for view in views}
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
        result = await agent.run(user_prompt=prompt)
        usage = usage + result.usage()
    return usage


async def generate_procedure_descriptions(
    con: TargetConnection,
    oids: list[int],
    model: KnownModelName | Model,
    callback: Callable[[ObjectDescription], None],
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
) -> Usage:
    def batches():
        for i in range(0, len(oids), batch_size):
            yield oids[i : i + batch_size]

    proc_index: dict[int, Procedure] = {}

    agent = Agent(
        model,
        model_settings=model_settings,
        name="procedure-describer",
        system_prompt=(
            "You are a SQL expert who generates natural language descriptions of procedures and functions in a PostgreSQL database. "  # noqa: E501
            "The descriptions that you generate should be a concise, single sentence."
        ),
    )

    @agent.tool_plain
    def record_description(id: int, description: str) -> None:  # pyright: ignore [reportUnusedFunction]
        """Records the description of a procedure or function

        Args:
            id (int): The ID of the procedure or function (specified in the XML tag)
            description (str): a concise, single sentence description of the procedure/function
        """  # noqa: E501
        proc = proc_index.get(id)
        if proc is None:
            # TODO: handle this somehow
            return
        callback(
            ObjectDescription(
                classid=proc.classid,
                objid=proc.objid,
                objsubid=0,
                objtype=proc.kind,
                objnames=[proc.schema_name, proc.proc_name],
                objargs=proc.objargs,
                description=description,
            )
        )

    usage: Usage = Usage()
    for batch in batches():
        procs: list[Procedure] = await loader.load_procedures(con, batch)
        proc_index = {proc.objid: proc for proc in procs}
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
        result = await agent.run(user_prompt=prompt)
        usage = usage + result.usage()
    return usage


async def build(
    db_url: str,
    model: KnownModelName | Model,
    catalog_name: str,
    output: TextIO,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_table: str | None = None,
    exclude_table: str | None = None,
    include_view: str | None = None,
    exclude_view: str | None = None,
    include_proc: str | None = None,
    exclude_proc: str | None = None,
    batch_size: int = 5,
    format: Literal["semantic-catalog", "comment"] = "semantic-catalog",
) -> Usage:
    assert format in {"semantic-catalog", "comment"}

    def callback(description: ObjectDescription):
        match format:
            case "semantic-catalog":
                output.write(
                    render.render_description_to_sql(con, catalog_name, description)
                )
            case "comment":
                output.write(render.render_description_to_comment(con, description))

    async with await psycopg.AsyncConnection.connect(db_url) as con:
        # tables
        table_oids = await find_tables(
            con,
            include_schema,
            exclude_schema,
            include_table,
            exclude_table,
        )
        usage = await generate_table_descriptions(
            con,
            table_oids,
            model,
            callback,
            batch_size=batch_size,
        )
        output.flush()

        # views
        view_oids = await find_views(
            con,
            include_schema,
            exclude_schema,
            include_view,
            exclude_view,
        )
        usage += await generate_view_descriptions(
            con,
            view_oids,
            model,
            callback,
            batch_size=batch_size,
        )
        output.flush()

        # procedures
        proc_oids = await find_procedures(
            con,
            include_schema,
            exclude_schema,
            include_proc,
            exclude_proc,
        )
        usage += await generate_procedure_descriptions(
            con,
            proc_oids,
            model,
            callback,
            batch_size=batch_size,
        )
    output.flush()
    return usage

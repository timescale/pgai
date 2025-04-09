from collections.abc import Generator
import asyncio

import psycopg
from psycopg.sql import SQL, Composable
from pydantic_ai import Agent
from pydantic_ai.models import Model, ModelSettings

from pgai.semantic_catalog import loader, render
from pgai.semantic_catalog.models import Table


async def find_tables(
    con: psycopg.AsyncConnection,
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
    con: psycopg.AsyncConnection,
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
    con: psycopg.AsyncConnection,
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
    con: psycopg.AsyncConnection,
    oids: list[int],
    model: str | Model,
    model_settings: ModelSettings | None = None,
    batch_size: int = 5,
):
    def batches():
        for i in range(0, len(oids), batch_size):
            yield oids[i:i + batch_size]

    table_descriptions = []
    column_descriptions = []

    agent = Agent(
        model,
        model_settings=model_settings,
        name="table-describer",
        system_prompt=(
            "You are a SQL expert who generates natural language descriptions of tables in a PostgreSQL database. "
            "The descriptions that you generate should be a concise, single sentence."
        )
    )

    @agent.tool_plain
    def record_table_description(schema_name: str, table_name: str, description: str) -> None:
        """Records the description of a table

        Args:
            schema_name: the name of the schema the table belongs to
            table_name: the name of the table
            description: a concise, single sentence description of the table
        """
        print(f"{schema_name}.{table_name}: {description}")
        table_descriptions.append((schema_name, table_name, description))

    @agent.tool_plain
    def record_column_description(schema_name: str, table_name: str, column_name: str, description: str) -> None:
        """Records the description of a column

        Args:
            schema_name: the name of the schema the table belongs to
            table_name: the name of the table the column belongs to
            column_name: the name of the column
            description: a concise, single sentence description of the column
        """
        print(f"{schema_name}.{table_name}.{column_name}: {description}")
        column_descriptions.append((schema_name, table_name, column_name, description))

    for i, batch in enumerate(batches()):
        print(f"processing batch {i}")
        table_descriptions.clear()
        column_descriptions.clear()
        tables: list[Table] = await loader.load_tables(con, batch)
        assert len(tables) == len(batch)
        print(f"loaded {len(tables)} tables")
        rendered: str = render.render_tables(tables)
        prompt = (
            "Below are representations of one or more PostgreSQL tables. "
            "Generate a natural language description for each table and column represented. "
            "Use tools to record your description. Respond ONLY with 'done' when finished. "
            "\n\n"
        ) + rendered
        print("contacting agent...")
        run_result = await agent.run(user_prompt=prompt)
        print(run_result.data)
        print(f"Collected {len(table_descriptions)} table descriptions")
        print(f"Collected {len(column_descriptions)} column descriptions")


async def build(db_url: str, model: str):
    async with await psycopg.AsyncConnection.connect(db_url) as con:
        table_oids = await find_tables(con)
        print(f"found {len(table_oids)} tables")
        await generate_table_descriptions(con, table_oids, model)


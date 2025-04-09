import psycopg
from psycopg.sql import SQL, Composable


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


async def find_procs(
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
            filters.append(SQL("\nand p.proname ~ %(include_table)s"))
            params["include_proc"] = include_proc
        if exclude_proc:
            filters.append(SQL("\nand p.proname !~ %(exclude_table)s"))
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


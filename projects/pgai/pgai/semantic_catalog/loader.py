import psycopg
from psycopg.rows import dict_row

from pgai.semantic_catalog.models import Procedure, Table, View


async def load_tables(con: psycopg.AsyncConnection, oids: list[int]) -> list[Table]:
    # TODO: add support for hypertable info
    # TODO: add support for partitioning info
    # TODO: add support for inheritance info
    # TODO: add support for foreign tables
    assert len(oids) > 0, "list of oids must not be empty"
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            with x as
            (
                select
                  'pg_catalog.pg_class'::regclass::oid as classid
                , k.oid as objid
                , n.nspname as schema_name
                , k.relname as table_name
                , case k.relpersistence
                    when 'u' then 'unlogged'
                    when 't' then 'temporary'
                  end as persistence
                , ( -- columns
                    select jsonb_agg
                    (
                      jsonb_build_object
                      ( 'classid', 'pg_catalog.pg_class'::regclass::oid
                      , 'objid', k.oid
                      , 'objsubid', a.attnum
                      , 'name', a.attname
                      , 'type', pg_catalog.format_type(a.atttypid, a.atttypmod)
                      , 'is_not_null', a.attnotnull
                      , 'default_value', pg_get_expr(d.adbin, d.adrelid)
                      )
                      order by a.attnum
                    )
                    from pg_attribute a
                    left outer join pg_attrdef d
                        on (a.attrelid = d.adrelid and a.attnum = d.adnum)
                    where a.attrelid = k.oid
                    and a.attnum > 0
                    and not a.attisdropped
                  ) as columns
                , ( -- constraints
                    select jsonb_agg
                    (
                        jsonb_build_object
                        ( 'name', c.conname
                        , 'definition', pg_get_constraintdef(c.oid)
                        )
                        order by c.oid
                    )
                    from pg_constraint c
                    where c.conrelid = k.oid
                  ) as constraints
                , ( -- indexes
                    select jsonb_agg
                    (
                      jsonb_build_object
                      ( 'name', x.relname
                      , 'definition', pg_get_indexdef(i.indexrelid)
                      )
                      order by i.indexrelid
                    )
                    from pg_index i
                    inner join pg_class x on (i.indexrelid = x.oid)
                    where i.indrelid = k.oid
                    and i.indisprimary = false -- already represented in constraints
                  ) as indexes
                from pg_class k
                inner join pg_namespace n on (k.relnamespace = n.oid)
                where k.oid = any(%s::oid[])
                and k.relkind in ('r', 'p', 'f')
            )
            select *
            from x
        """,
            (oids,),
        )
        tables: list[Table] = []
        for row in await cur.fetchall():
            tables.append(Table.model_validate(row))
        return tables


async def load_views(con: psycopg.AsyncConnection, oids: list[int]) -> list[View]:
    # TODO: add support for continuous aggregates
    assert len(oids) > 0, "list of oids must not be empty"
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select
              'pg_catalog.pg_class'::regclass::oid as classid
            , k.oid as objid
            , n.nspname as schema_name
            , k.relname as view_name
            , k.relkind = 'm' as is_materialized
            , pg_get_viewdef(k.oid, true) as definition
            , ( -- columns
                select jsonb_agg
                (
                  jsonb_build_object
                  ( 'classid', 'pg_catalog.pg_class'::regclass::oid
                  , 'objid', k.oid
                  , 'objsubid', a.attnum
                  , 'name', a.attname
                  , 'type', pg_catalog.format_type(a.atttypid, a.atttypmod)
                  , 'is_not_null', a.attnotnull
                  , 'default_value', null::text
                  )
                  order by a.attnum
                )
                from pg_attribute a
                left outer join pg_attrdef d
                    on (a.attrelid = d.adrelid and a.attnum = d.adnum)
                where a.attrelid = k.oid
                and a.attnum > 0
                and not a.attisdropped
              ) as columns
            from pg_class k
            inner join pg_namespace n on (k.relnamespace = n.oid)
            where k.oid = any(%s::oid[])
            and k.relkind in ('v', 'm')
        """,
            (oids,),
        )
        views: list[View] = []
        for row in await cur.fetchall():
            views.append(View.model_validate(row))
        return views


async def load_procedures(
    con: psycopg.AsyncConnection, oids: list[int]
) -> list[Procedure]:
    assert len(oids) > 0, "list of oids must not be empty"
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select
              'pg_catalog.pg_proc'::regclass::oid as classid
            , p.oid as objid
            , n.nspname as schema_name
            , p.proname as proc_name
            , case p.prokind
                when 'f' then 'function'
                when 'w' then 'function'
                when 'p' then 'procedure'
                when 'a' then 'aggregate'
              end as kind
            , pg_get_function_identity_arguments(p.oid) as identity_args
            , pg_get_functiondef(p.oid) as definition
            , x.object_args as objargs
            from pg_proc p
            inner join pg_namespace n on (p.pronamespace = n.oid)
            cross join lateral pg_identify_object_as_address
            ( 'pg_catalog.pg_proc'::regclass::oid
            , p.oid
            , 0
            ) x
            where p.oid = any(%s::oid[])
        """,
            (oids,),
        )
        procedures: list[Procedure] = []
        for row in await cur.fetchall():
            procedures.append(Procedure.model_validate(row))
        return procedures

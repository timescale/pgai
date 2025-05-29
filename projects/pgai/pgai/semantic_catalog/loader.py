import logging

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from pgai.semantic_catalog.models import (
    ObjectDescription,
    Procedure,
    Table,
    View,
)
from pgai.semantic_catalog.sample import sample_table, sample_view

logger = logging.getLogger(__name__)


async def load_tables(
    con: psycopg.AsyncConnection, oids: list[int], sample_size: int = 0
) -> list[Table]:
    """Load table definitions from the database based on object IDs.

    Retrieves table metadata including columns, constraints, and indexes for the
    specified table OIDs. If sample_size is greater than 0, it also retrieves sample
    data from each table.

    Args:
        con: Asynchronous database connection object.
        oids: List of table object IDs to load.
        sample_size: Number of sample rows to retrieve from each table (default: 0).
            If 0, no sample data is retrieved.

    Returns:
        A list of Table objects with metadata and optionally sample data.

    Raises:
        AssertionError: If the list of oids is empty.
    """
    # TODO: add support for hypertable info
    # TODO: add support for partitioning info
    # TODO: add support for inheritance info
    # TODO: add support for foreign tables
    assert len(oids) > 0, "list of oids must not be empty"
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute("select 1 from pg_extension where extname = 'timescaledb'")
        is_timescale = await cur.fetchone() is not None
        timescale_cte = """
        select
            null as schema_name
            , null as table_name, null as dimensions
        """
        if is_timescale:
            timescale_cte = """
            select
                h.schema_name
                , h.table_name
                , d.dimensions
            from
                _timescaledb_catalog.hypertable AS h
            join (
                select
                    d.hypertable_id
                    , json_agg(json_build_object(
                        'dimension_builder', d.dimension_builder
                        , 'column_name', d.column_name
                        , 'partition_func', d.partition_func
                        , 'partition_interval', d.partition_interval
                        , 'number_partitions', d.number_partitions
                    )) as dimensions
                from (
                    select
                    d.hypertable_id,
                    case
                        when d.partitioning_func is null then 'by_range'
                        when d.partitioning_func = 'get_partition_hash' then 'by_hash'
                        when f.function_type IN ('int2', 'int4', 'int8') then 'by_hash'
                        else 'by_range'
                    end AS dimension_builder,
                    d.column_name AS column_name,
                    case
                        when d.partitioning_func is null then null
                        when d.partitioning_func = 'get_partition_hash' then null
                        else format(
                            '%%s.%%s'
                            , d.partitioning_func_schema
                            , d.partitioning_func
                        )
                    end as partition_func,
                    case
                        when d.interval_length is null then null
                        else 'INTERVAL '''
                            || justify_interval(
                                d.interval_length * interval '1 microsecond'
                            )
                            || ''''
                    end as partition_interval,
                    d.num_slices as number_partitions
                    from _timescaledb_catalog.dimension as d
                    left join
                    (
                        select
                        n.nspname as function_schema
                        , p.proname as function_name
                        , t.typname as function_type
                        from pg_proc p
                        join pg_namespace n on n.oid = p.pronamespace
                        join pg_type t on t.oid = p.prorettype
                    ) as f on (
                        f.function_schema = d.partitioning_func_schema
                        and f.function_name = d.partitioning_func
                    )
                    order by d.id
                ) as d
                group by d.hypertable_id
            ) as d on d.hypertable_id = h.id
            where h.schema_name != '_timescaledb_internal'
            """

        await cur.execute(
            f"""
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
            ),
            y as
            (
                {timescale_cte}
            )
            select x.*, y.dimensions
            from x
            left join y on (
                x.schema_name = y.schema_name
                and x.table_name = y.table_name
            )
        """,
            (oids,),
        )
        tables: list[Table] = []
        for row in await cur.fetchall():
            tables.append(Table.model_validate(row))
        if len(tables) != len(oids):
            logger.warning(
                f"{len(oids)} oids were provided but only {len(tables)} tables were loaded"  # noqa
            )
        if sample_size > 0:
            logger.debug(
                f"sampling {sample_size} rows from each of {len(tables)} tables"
            )
            for table in tables:
                logger.debug(f"sampling {table.schema_name}.{table.table_name}")
                table.sample = await sample_table(
                    con, table.schema_name, table.table_name, limit=sample_size
                )
        return tables


async def load_views(
    con: psycopg.AsyncConnection, oids: list[int], sample_size: int = 0
) -> list[View]:
    """Load view definitions from the database based on object IDs.

    Retrieves view metadata including columns and definition SQL for the specified
    view OIDs. Handles both regular views and materialized views. If TimescaleDB is
    installed, it also identifies continuous aggregates. If sample_size is greater
    than 0, it also retrieves sample data from each view.

    Args:
        con: Asynchronous database connection object.
        oids: List of view object IDs to load.
        sample_size: Number of sample rows to retrieve from each view (default: 0).
            If 0, no sample data is retrieved.

    Returns:
        A list of View objects with metadata and optionally sample data.

    Raises:
        AssertionError: If the list of oids is empty.
    """
    assert len(oids) > 0, "list of oids must not be empty"
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute("select 1 from pg_extension where extname = 'timescaledb'")
        is_timescale = await cur.fetchone() is not None
        continuous_aggregate = "false"
        materialized = "k.relkind = 'm'"
        view_def = "pg_get_viewdef(k.oid, true)"
        ts_join = ""
        if is_timescale:
            continuous_aggregate = "ca.view_definition is not null"
            materialized = f"{continuous_aggregate} or {materialized}"
            view_def = f"coalesce(ca.view_definition, {view_def})"
            ts_join = """
            left join timescaledb_information.continuous_aggregates ca
                on (ca.view_schema = n.nspname and ca.view_name = k.relname)
            """

        await cur.execute(
            f"""\
            select
              'pg_catalog.pg_class'::regclass::oid as classid
            , k.oid as objid
            , n.nspname as schema_name
            , k.relname as view_name
            , {materialized} as is_materialized
            , {continuous_aggregate} as is_continuous_aggregate
            , {view_def} as definition
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
            {ts_join}
            where k.oid = any(%s::oid[])
            and k.relkind in ('v', 'm')
        """,
            (oids,),
        )
        views: list[View] = []
        for row in await cur.fetchall():
            views.append(View.model_validate(row))
        if len(views) != len(oids):
            logger.warning(
                f"{len(oids)} oids were provided but only {len(views)} views were loaded"  # noqa
            )
        if sample_size > 0:
            logger.debug(f"sampling {sample_size} rows from each of {len(views)} views")
            for view in views:
                logger.debug(f"sampling {view.schema_name}.{view.view_name}")
                view.sample = await sample_view(
                    con, view.schema_name, view.view_name, limit=sample_size
                )
        return views


async def load_procedures(
    con: psycopg.AsyncConnection, oids: list[int]
) -> list[Procedure]:
    """Load procedure definitions from the database based on object IDs.

    Retrieves metadata for procedures, functions, and aggregates for the specified OIDs,
    including their full definition SQL.

    Args:
        con: Asynchronous database connection object.
        oids: List of procedure object IDs to load.

    Returns:
        A list of Procedure objects with metadata.

    Raises:
        AssertionError: If the list of oids is empty.
    """
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
            , case
                when p.prokind = 'a' then
                  'CREATE OR REPLACE AGGREGATE FUNCTION '
                  || quote_ident(n.nspname) || '.' || quote_ident(p.proname)
                  || '(' || pg_get_function_identity_arguments(p.oid) ||  ') (' || E'\n'
                  || '  sfunc = ' || a.aggtransfn::text
                  || ',' || E'\n' || '  stype = ' || tt.typname::text
                  || case
                    when a.aggmtransfn != 0 then
                      ',' || E'\n' || '  msfunc = ' || a.aggmtransfn::text || ','
                      || E'\n' || '  mstype = ' || tm.typname::text
                    else ''
                  end
                  || case
                    when a.aggfinalfn != 0 then
                      ',' || E'\n' || '  finalfunc = ' || a.aggfinalfn::text
                      || case
                        when a.aggfinalextra is true then
                          ', ' || E'\n' || '  finalfunc_extra'
                        else ''
                      end
                      || ',' || E'\n' || '  finalfunc_modify = '
                      || case
                        when a.aggfinalmodify = 'r' then 'READ_ONLY'
                        when a.aggfinalmodify = 's' then 'SHAREABLE'
                        when a.aggfinalmodify = 'w' then 'READ_WRITE'
                      end
                    else ''
                  end
                  || case
                    when a.aggcombinefn != 0 then
                      ',' || E'\n' || '  combinefunc = ' || a.aggcombinefn::text
                    else ''
                  end
                  || case
                    when a.aggserialfn != 0 then
                      ',' || E'\n' || '  serialfunc = ' || a.aggserialfn::text
                    else ''
                  end
                  || case
                    when a.aggdeserialfn != 0 then
                      ',' || E'\n' || '  deserialfunc = ' || a.aggdeserialfn::text
                    else ''
                  end
                  || case
                    when a.aggmfinalfn != 0 then
                      ',' || E'\n' || '  mfinalfunc = ' || a.aggmfinalfn::text
                      || case
                        when a.aggmfinalextra is true then
                        ', ' || E'\n' || '  mfinalfunc_extra'
                        else ''
                      end
                      || ',' || E'\n' || '  mfinalfunc_modify = '
                      || case
                        when a.aggmfinalmodify = 'r' then 'READ_ONLY'
                        when a.aggmfinalmodify = 's' then 'SHAREABLE'
                        when a.aggmfinalmodify = 'w' then 'READ_WRITE'
                      end
                      else ''
                  end
                  || case
                    when a.aggminvtransfn != 0 then ',' || E'\n'
                      || '  minvfunc = ' || a.aggminvtransfn::text
                    else ''
                  end
                  || case
                    when a.agginitval is not null then ',' || E'\n'
                      || '  initcond = ' || a.agginitval
                    else ''
                  end
                  || case
                    when a.aggminitval is not null then ',' || E'\n'
                      || '  minitcond = ' || a.aggminitval
                    else ''
                  end
                  || case
                    when a.aggsortop != 0 then
                      ',' || E'\n' || '  sortop = ' || o.oprname
                    else ''
                  end
                  || E'\n' || ')'
                else pg_get_functiondef(p.oid)
            end as definition
            , x.object_args as objargs
            from pg_proc p
            inner join pg_namespace n on (p.pronamespace = n.oid)
            left join pg_aggregate a on (p.oid = a.aggfnoid)
            left join pg_type tt on (a.aggtranstype = tt.oid)
            left join pg_type tm on (a.aggmtranstype = tm.oid)
            left join pg_operator o on (a.aggsortop = o.oid)
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
        if len(procedures) != len(oids):
            logger.warning(
                f"{len(oids)} oids were provided but only {len(procedures)} procedures were loaded"  # noqa
            )
    return procedures


async def _load_descriptions(
    con: psycopg.AsyncConnection, catalog_id: int, classid: int, objids: list[int]
) -> list[ObjectDescription]:
    """Loads ObjectDescriptions from the semantic catalog
    Given a classid and a list of objids, this will load the corresponding
    ObjectDescriptions.
    Args:
        con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to search in.
        classid: PostgreSQL object class ID
        objids: list of PostgreSQL object IDs
    Returns:
        A list of ObjectDescription objects.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            where x.classid = %(classid)s
            and x.objid = any(%(objids)s)
            order by x.classid, x.objid
        """).format(
            table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
        )
        await cur.execute(
            sql,
            dict(
                classid=classid,
                objids=objids,
            ),
        )
        results: list[ObjectDescription] = []
        for row in await cur.fetchall():
            results.append(ObjectDescription(**row))
        return results


async def load_objects(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    obj_desc: list[ObjectDescription],
    sample_size: int = 0,
) -> list[Table | View | Procedure]:
    """Load database objects based on their descriptions.

    Takes a list of object descriptions and loads the corresponding database objects
    (tables, views, procedures) with their metadata. Matches the descriptions with
    the loaded objects and attaches them. If sample_size is greater than 0, it also
    retrieves sample data for tables and views.

    Args:
        catalog_con: Connection to the semantic catalog database.
        target_con: Connection to the target database where the objects are defined.
        catalog_id: ID of the semantic catalog to use for retrieving descriptions.
        obj_desc: List of object descriptions to match with database objects.
        sample_size: Number of sample rows to retrieve from tables and views (default: 0).
            If 0, no sample data is retrieved.

    Returns:
        A list of database objects (Tables, Views, Procedures) with metadata and descriptions.

    Raises:
        ValueError: If an unknown object type is encountered.
    """  # noqa: E501
    t: set[int] = set()  # distinct objid
    v: set[int] = set()  # distinct objid
    p: set[int] = set()  # distinct objid
    td: dict[int, ObjectDescription] = {}  # objid -> OD
    cd: dict[tuple[int, int], ObjectDescription] = {}  # (objid, objsubid) -> OD
    vd: dict[int, ObjectDescription] = {}  # objid -> OD
    pd: dict[int, ObjectDescription] = {}  # objid -> OD
    classid: int = -1
    tv: set[int] = set()  # all tables and views objid
    for od in obj_desc:
        match od.objtype:
            case "table":
                t.add(od.objid)
                td[od.objid] = od
                tv.add(od.objid)
                classid = od.classid
            case "view":
                v.add(od.objid)
                vd[od.objid] = od
                tv.add(od.objid)
                classid = od.classid
            case "procedure":
                p.add(od.objid)
                pd[od.objid] = od
            case "table column":
                t.add(od.objid)
                cd[(od.objid, od.objsubid)] = od
                tv.add(od.objid)
                classid = od.classid
            case "view column":
                v.add(od.objid)
                cd[(od.objid, od.objsubid)] = od
                tv.add(od.objid)
                classid = od.classid
            case _:
                raise ValueError(f"unknown object type {od.objtype}")
    # make sure all the descriptions for each table/view are loaded
    for od in await _load_descriptions(
        catalog_con, catalog_id, classid, [o for o in tv]
    ):
        match od.objtype:
            case "table":
                td[od.objid] = od
            case "view":
                vd[od.objid] = od
            case "table column":
                cd[(od.objid, od.objsubid)] = od
            case "view column":
                vd[od.objid] = od
            case _:
                raise ValueError(f"unknown object type {od.objtype}")
    tables = await load_tables(target_con, list(t), sample_size) if len(t) > 0 else []
    views = await load_views(target_con, list(v), sample_size) if len(v) > 0 else []
    procedures = await load_procedures(target_con, list(p)) if len(p) > 0 else []
    for table in tables:
        d = td.get(table.objid, None)
        table.description = d
        table.id = d.id if d is not None else -1
        if table.columns:
            for column in table.columns:
                column.description = cd.get((column.objid, column.objsubid), None)
    for view in views:
        d = vd.get(view.objid, None)
        view.description = d
        view.id = d.id if d is not None else -1
        if view.columns:
            for column in view.columns:
                column.description = cd.get((column.objid, column.objsubid), None)
    for procedure in procedures:
        d = pd.get(procedure.objid, None)
        procedure.description = d
        procedure.id = d.id if d is not None else -1
    results: list[Table | View | Procedure] = []
    results.extend(tables)
    results.extend(views)
    results.extend(procedures)
    return results

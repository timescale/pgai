"""Database object reference fixing utilities for semantic catalog.

This module provides functions to fix database object references in the semantic
catalog. When database objects like tables, views, or columns are changed, their
internal identifiers and object names might need to be updated in the semantic catalog
to maintain proper references.
"""

import logging
from dataclasses import dataclass

import psycopg
from psycopg.rows import class_row
from psycopg.sql import SQL, Composed, Identifier, Literal
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

logger = logging.getLogger(__name__)


@dataclass
class _Object:
    """Represents a database object reference stored in the semantic catalog.

    Contains both PostgreSQL internal identifiers (classid, objid, objsubid) and
    object name identifiers (objtype, objnames, objargs) for a database object.
    """

    id: int  # Semantic catalog object ID
    classid: int  # PostgreSQL pg_class.oid for the system catalog containing the object
    objid: int  # PostgreSQL oid of the object in the system catalog
    objsubid: int  # Sub-object ID for columns and other sub-objects
    objtype: str  # Type of object (table, view, function, etc.)
    objnames: list[str]  # Fully qualified object name as a list of identifiers
    objargs: list[str]  # Function arguments (if applicable)


@dataclass
class _Ids:
    """Container for PostgreSQL internal object identifiers.

    Represents the system identifiers for a PostgreSQL database object,
    as returned by pg_get_object_address().
    """

    classid: int  # PostgreSQL pg_class.oid for the system catalog containing the object
    objid: int  # PostgreSQL oid of the object in the system catalog
    objsubid: int  # Sub-object ID for columns and other sub-objects


@dataclass
class _Names:
    """Container for PostgreSQL object name identifiers.

    Represents the name-based identifiers for a PostgreSQL database object,
    as returned by pg_identify_object_as_address().
    """

    objtype: str  # Type of object (table, view, function, etc.)
    objnames: list[str]  # Fully qualified object name as a list of identifiers
    objargs: list[str]  # Function arguments (if applicable)


async def _list_ids(catalog_con: psycopg.AsyncConnection, catalog_id: int) -> list[int]:
    """Retrieve all object IDs from the specified semantic catalog.

    Args:
        catalog_con: Connection to the database containing the semantic catalog
        catalog_id: ID of the semantic catalog

    Returns:
        List of all object IDs in the catalog, sorted by ID
    """
    async with catalog_con.cursor() as cur:
        await cur.execute(
            SQL("""\
            select id
            from ai.{}
            order by id
        """).format(Identifier(f"semantic_catalog_obj_{catalog_id}"))
        )
        return [row[0] for row in await cur.fetchall()]


async def _get_obj(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, id: int
) -> _Object | None:
    """Retrieve a specific object from the semantic catalog by ID.

    Args:
        catalog_con: Connection to the database containing the semantic catalog
        catalog_id: ID of the semantic catalog
        id: ID of the specific object to retrieve

    Returns:
        The object if found, None otherwise
    """
    async with catalog_con.cursor(row_factory=class_row(_Object)) as cur:
        await cur.execute(
            SQL("""\
            select
              id
            , classid
            , objid
            , objsubid
            , objtype
            , objnames
            , objargs
            from ai.{}
            where id = %s
        """).format(Identifier(f"semantic_catalog_obj_{catalog_id}")),
            (id,),
        )
        obj = await cur.fetchone()
        return obj


async def _ids_from_names(
    target_con: psycopg.AsyncConnection, obj: _Object
) -> _Ids | None:
    """Convert object name identifiers to PostgreSQL internal IDs.

    Uses pg_get_object_address() to find current internal IDs for an object
    identified by name, type, and arguments.

    Args:
        target_con: Connection to the target database
        obj: Object with name identifiers to convert

    Returns:
        Internal IDs if object exists, None if object not found
    """
    try:
        async with (
            target_con.cursor(row_factory=class_row(_Ids)) as cur,
            target_con.transaction() as _,
        ):
            await cur.execute(
                """\
                select
                  a.classid
                , a.objid
                , a.objsubid as objsubid
                from pg_get_object_address
                ( case
                    when %(objtype)s = 'view column' then 'table column'
                    else %(objtype)s
                  end
                , %(objnames)s
                , %(objargs)s
                ) a
            """,
                dict(objtype=obj.objtype, objnames=obj.objnames, objargs=obj.objargs),
            )
            ids = await cur.fetchone()
            return ids
    except psycopg.Error as e:
        logger.debug(f"object not found {obj.id}: {str(e)}")
    return None


def _del_obj_sql(catalog_id: int, obj: _Object) -> Composed:
    """Generate SQL to delete an object from the semantic catalog.

    Args:
        catalog_id: ID of the semantic catalog
        obj: Object to delete

    Returns:
        SQL query to delete the object
    """
    return SQL("DELETE from ai.{table} WHERE id = {id};").format(
        table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
        id=Literal(obj.id),
    )


def _ids_dont_match(obj: _Object, ids: _Ids) -> bool:
    """Check if the internal IDs in the object match the provided IDs.

    Args:
        obj: Object with stored IDs
        ids: Current IDs to compare against

    Returns:
        True if IDs don't match, False if they do
    """
    return (
        obj.classid != ids.classid
        or obj.objid != ids.objid
        or obj.objsubid != ids.objsubid
    )


def _update_ids_sql(catalog_id: int, obj: _Object, ids: _Ids) -> Composed:
    """Generate SQL to update an object's internal IDs in the semantic catalog.

    Args:
        catalog_id: ID of the semantic catalog
        obj: Object to update
        ids: New internal IDs to set

    Returns:
        SQL query to update the object's IDs
    """
    return SQL(
        "UPDATE ai.{table} SET classid={classid}, objid={objid}, objsubid={objsubid} WHERE id = {id};"  # noqa
    ).format(
        table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
        classid=Literal(ids.classid),
        objid=Literal(ids.objid),
        objsubid=Literal(ids.objsubid),
        id=Literal(obj.id),
    )


async def _names_from_ids(
    target_con: psycopg.AsyncConnection, obj: _Object
) -> _Names | None:
    """Convert PostgreSQL internal IDs to object name identifiers.

    Uses pg_identify_object_as_address() to find current name identifiers for an object
    identified by internal IDs.

    Args:
        target_con: Connection to the target database
        obj: Object with internal IDs to convert

    Returns:
        Name identifiers if object exists, None if object not found
    """
    try:
        async with (
            target_con.cursor(row_factory=class_row(_Names)) as cur,
            target_con.transaction() as _,
        ):
            await cur.execute(
                """\
                select
                  a."type" as objtype
                , a.object_names as objnames
                , a.object_args as objargs
                from pg_identify_object_as_address
                ( %(classid)s
                , %(objid)s
                , %(objsubid)s
                ) a
            """,
                dict(classid=obj.classid, objid=obj.objid, objsubid=obj.objsubid),
            )
            names = await cur.fetchone()
            return names
    except psycopg.Error as e:
        logger.debug(f"object not found {obj.id}: {str(e)}")
    return None


def _names_dont_match(obj: _Object, names: _Names) -> bool:
    """Check if the name identifiers in the object match the provided names.

    Args:
        obj: Object with stored name identifiers
        names: Current name identifiers to compare against

    Returns:
        True if name identifiers don't match, False if they do
    """
    return (
        obj.objtype != names.objtype
        or obj.objnames != names.objnames
        or obj.objargs != names.objargs
    )


def _update_names_sql(catalog_id: int, obj: _Object, names: _Names) -> Composed:
    """Generate SQL to update an object's name identifiers in the semantic catalog.

    Args:
        catalog_id: ID of the semantic catalog
        obj: Object to update
        names: New name identifiers to set

    Returns:
        SQL query to update the object's name identifiers
    """
    return SQL(
        "UPDATE ai.{table} set objtype={objtype}, objnames={objnames}, objargs={objargs} WHERE id = {id};"  # noqa
    ).format(
        table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
        objtype=Literal(names.objtype),
        objnames=Literal(names.objnames),
        objargs=Literal(names.objargs),
        id=Literal(obj.id),
    )


async def _defer_name_constraint(
    catalog_cur: psycopg.AsyncCursor, catalog_id: int
) -> None:
    await catalog_cur.execute(
        """\
        select x.conname
        from pg_class k
        inner join pg_namespace n on (k.relnamespace = n.oid)
        cross join lateral
        (
            select array_agg(a.attnum order by a.attnum) as cols
            from pg_attribute a
            where a.attrelid = k.oid
            and a.attname in ('objtype', 'objnames', 'objargs')
        ) a
        inner join pg_constraint x on (x.conrelid = k.oid and x.conkey = a.cols)
        where k.relname = %s
        and n.nspname = 'ai'
        and x.contype = 'u'
        and x.condeferrable
    """,
        (f"semantic_catalog_obj_{catalog_id}",),
    )
    row = await catalog_cur.fetchone()
    assert row is not None, "could not find unique constraint"
    conname: str = str(row[0])
    await catalog_cur.execute(
        SQL("""\
        set constraints ai.{conname} deferred
    """).format(conname=Identifier(conname))
    )


async def _defer_id_constraint(
    catalog_cur: psycopg.AsyncCursor, catalog_id: int
) -> None:
    await catalog_cur.execute(
        """\
        select x.conname
        from pg_class k
        inner join pg_namespace n on (k.relnamespace = n.oid)
        cross join lateral
        (
            select array_agg(a.attnum order by a.attnum) as cols
            from pg_attribute a
            where a.attrelid = k.oid
            and a.attname in ('classid', 'objid', 'objsubid')
        ) a
        inner join pg_constraint x on (x.conrelid = k.oid and x.conkey = a.cols)
        where k.relname = %s
        and n.nspname = 'ai'
        and x.contype = 'u'
        and x.condeferrable
    """,
        (f"semantic_catalog_obj_{catalog_id}",),
    )
    row = await catalog_cur.fetchone()
    assert row is not None, "could not find unique constraint"
    conname: str = str(row[0])
    await catalog_cur.execute(
        SQL("""\
        set constraints ai.{conname} deferred
    """).format(conname=Identifier(conname))
    )


async def fix_ids(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    dry_run: bool,
    console: Console,
) -> None:
    """Fix internal PostgreSQL IDs in the semantic catalog.

    Checks all objects in the semantic catalog against the target database. For each object:
    - If object doesn't exist in target database, marks it for deletion
    - If object's internal IDs don't match current values, marks it for update
    - If object is already correct, leaves it unchanged

    If not a dry run, performs all deletions and updates in a transaction.
    Shows progress with a rich progress bar.

    Args:
        catalog_con: Connection to the database containing the semantic catalog
        target_con: Connection to the target database containing the actual objects
        catalog_id: ID of the semantic catalog to fix
        dry_run: If True, only check for issues without making changes
        console: Rich console for output and progress display
    """  # noqa
    pbcols = [
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ]

    with Progress(*pbcols, console=console) as progress:
        ids = await _list_ids(catalog_con, catalog_id)

        task_check = progress.add_task(
            "checking ids",
            total=len(ids),
            visible=len(ids) > 0,
        )

        queries: list[tuple[str, Composed]] = []
        for id in ids:
            obj = await _get_obj(catalog_con, catalog_id, id)
            if obj is None:
                progress.update(task_check, advance=1.0)
                continue
            ids = await _ids_from_names(target_con, obj)
            if ids is None:
                logger.info(f"obj {obj.id} no longer matches anything. deleting")
                progress.console.print(f'{obj.id} {".".join(obj.objnames)}: MISSING')
                queries.append(
                    (
                        "DELETING: " + ".".join(obj.objnames),
                        _del_obj_sql(catalog_id, obj),
                    )
                )
            elif _ids_dont_match(obj, ids):
                logger.info(f"updating the ids for obj {obj.id}")
                progress.console.print(f'{obj.id} {".".join(obj.objnames)}: FIX')
                queries.append(
                    (
                        "UPDATING: " + ".".join(obj.objnames),
                        _update_ids_sql(catalog_id, obj, ids),
                    )
                )
            else:
                progress.console.print(f'{obj.id} {".".join(obj.objnames)}: OK')
                logger.info(f"obj {obj.id} is already correct")
            progress.update(task_check, advance=1.0)

        task_fix = progress.add_task(
            "applying fixes",
            total=len(queries),
            visible=len(queries) > 0,
        )

        if dry_run:
            return

        # do these changes in a transaction to take advantage of deferrable constraints
        async with catalog_con.transaction() as _, catalog_con.cursor() as cur:
            await _defer_id_constraint(cur, catalog_id)
            for msg, query in queries:
                progress.console.print(msg)
                await cur.execute(query)
                progress.update(task_fix, advance=1.0)


async def fix_names(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    dry_run: bool,
    console: Console,
) -> None:
    """Fix object name identifiers in the semantic catalog.

    Checks all objects in the semantic catalog against the target database. For each object:
    - If object doesn't exist in target database, marks it for deletion
    - If object's name identifiers don't match current values, marks it for update
    - If object is already correct, leaves it unchanged

    If not a dry run, performs all deletions and updates in a transaction.
    Shows progress with a rich progress bar.

    Args:
        catalog_con: Connection to the database containing the semantic catalog
        target_con: Connection to the target database containing the actual objects
        catalog_id: ID of the semantic catalog to fix
        dry_run: If True, only check for issues without making changes
        console: Rich console for output and progress display
    """  # noqa
    pbcols = [
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ]

    with Progress(*pbcols, console=console) as progress:
        ids = await _list_ids(catalog_con, catalog_id)

        task_check = progress.add_task(
            "checking names",
            total=len(ids),
            visible=len(ids) > 0,
        )

        queries: list[tuple[str, Composed]] = []
        for id in ids:
            obj = await _get_obj(catalog_con, catalog_id, id)
            if obj is None:
                progress.update(task_check, advance=1.0)
                continue
            names = await _names_from_ids(target_con, obj)
            if names is None:
                logger.info(f"obj {obj.id} no longer matches anything. deleting")
                progress.console.print(f'{obj.id} {".".join(obj.objnames)}: MISSING')
                queries.append(
                    (
                        "DELETING: " + ".".join(obj.objnames),
                        _del_obj_sql(catalog_id, obj),
                    )
                )
            elif _names_dont_match(obj, names):
                logger.info(f"updating the names for obj {obj.id}")
                progress.console.print(f'{obj.id} {".".join(obj.objnames)}: FIX')
                queries.append(
                    (
                        "UPDATING: " + ".".join(obj.objnames),
                        _update_names_sql(catalog_id, obj, names),
                    )
                )
            else:
                progress.console.print(f'{obj.id} {".".join(obj.objnames)}: OK')
                logger.info(f"obj {obj.id} is already correct")
            progress.update(task_check, advance=1.0)

        task_fix = progress.add_task(
            "applying fixes",
            total=len(queries),
            visible=len(queries) > 0,
        )

        if dry_run:
            return

        # do these changes in a transaction to take advantage of deferrable constraints
        async with catalog_con.transaction() as _, catalog_con.cursor() as cur:
            await _defer_name_constraint(cur, catalog_id)
            for msg, query in queries:
                progress.console.print(msg)
                await cur.execute(query)
                progress.update(task_fix, advance=1.0)

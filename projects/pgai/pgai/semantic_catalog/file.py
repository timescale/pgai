import logging
from collections.abc import AsyncGenerator, AsyncIterator, Generator, Iterator
from typing import (
    Any,
    Literal,
    TextIO,
)

import psycopg
import yaml
from psycopg.rows import DictRow, dict_row
from psycopg.sql import SQL, Identifier
from pydantic import BaseModel, Field

from pgai.semantic_catalog.models import ObjectDescription

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"


class Header(BaseModel):
    type: Literal["header"] = "header"
    schema_version: str = SCHEMA_VERSION

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class Column(BaseModel):
    name: str
    description: str


class Table(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    type: Literal["table"] = "table"
    description: str
    columns: list[Column] = []

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True, by_alias=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class View(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    type: Literal["view"] = "view"
    description: str
    columns: list[Column] = []

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True, by_alias=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class Function(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    args: list[str] = []
    type: Literal["function"] = "function"
    description: str

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True, by_alias=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class Procedure(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    args: list[str] = []
    type: Literal["procedure"] = "procedure"
    description: str

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True, by_alias=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class Aggregate(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    args: list[str] = []
    type: Literal["aggregate"] = "aggregate"
    description: str

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True, by_alias=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class Fact(BaseModel):
    type: Literal["fact"] = "fact"
    id: int | None = None
    description: str

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


class SQLExample(BaseModel):
    type: Literal["sql_example"] = "sql_example"
    id: int | None = None
    sql: str
    description: str

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True),
            explicit_start=True,
            sort_keys=False,
            explicit_end=True,
        )


Item = Table | View | Procedure | Function | Aggregate | SQLExample | Fact


def item_from_dict(d: dict[str, Any]) -> Item:
    """Convert a dictionary to the appropriate catalog item type.

    Takes a dictionary that represents a catalog item and converts it to the
    corresponding model class based on the 'type' field.

    Args:
        d: Dictionary containing item data with a 'type' field.

    Returns:
        An instance of the appropriate Item type.

    Raises:
        ValueError: If the 'type' field is not recognized.
    """
    mapping = {
        "table": Table,
        "view": View,
        "procedure": Procedure,
        "function": Function,
        "aggregate": Aggregate,
        "sql_example": SQLExample,
        "fact": Fact,
    }
    item_type = d.get("type")
    if item_type not in mapping:
        raise ValueError(f"unrecognized type: {item_type}")
    return mapping[item_type].model_validate(d)


def import_from_yaml(text: TextIO) -> Generator[Item, None, None]:
    """Import catalog items from a YAML file.

    Reads a YAML stream containing multiple documents. The first document should be a
    header with schema version information, followed by one or more catalog items.

    Args:
        text: A text IO stream containing YAML documents.

    Returns:
        A generator yielding catalog items (Tables, Views, Functions, etc.).

    Raises:
        RuntimeError: If the first document is not a header or has an invalid schema version.
    """  # noqa: E501
    for i, doc in enumerate(yaml.safe_load_all(text)):
        if not doc:
            continue
        if i == 0:
            schema_version = doc.get("schema_version")
            if schema_version is None:
                raise RuntimeError("the first document in yaml must be a header")
            if schema_version != SCHEMA_VERSION:
                raise RuntimeError(f"invalid schema_version: {schema_version}")
            continue
        yield item_from_dict(doc)


async def _look_up_class(
    target_con: psycopg.AsyncConnection, item: Table | View
) -> list[ObjectDescription]:
    """Look up database object IDs for a table or view and its columns.

    Queries the database to find the object IDs for a table or view and all its columns,
    then creates ObjectDescription objects for each.

    Args:
        target_con: Asynchronous database connection to the target database.
        item: A Table or View object to look up.

    Returns:
        A list of ObjectDescription objects for the table/view and its columns.

    Raises:
        RuntimeError: If the table or view is not found in the database.
    """
    descs: list[ObjectDescription] = []
    async with target_con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select x.classid, x.objid
            from pg_get_object_address
            ( %(type)s
            , array[%(schema_name)s, %(name)s]::text[]
            , array[]::text[]
            ) x
        """,
            dict(
                type=item.type,
                schema_name=item.schema_name,
                name=item.name,
            ),
        )
        row = await cur.fetchone()
        if not row:
            raise RuntimeError(f"table/view not found: {item.schema_name}.{item.name}")
        classid = row["classid"]
        objid = row["objid"]
        descs.append(
            ObjectDescription(
                classid=classid,
                objid=objid,
                objsubid=0,
                objtype=item.type,
                objnames=[item.schema_name, item.name],
                objargs=[],
                description=item.description,
            )
        )
        await cur.execute(
            """\
            select c, x.objsubid
            from unnest(%(columns)s::text[]) c
            cross join lateral pg_get_object_address
            ( 'table column'
            , array[%(schema_name)s, %(name)s, c]::text[]
            , array[]::text[]
            ) x
        """,
            dict(
                type=item.type,
                schema_name=item.schema_name,
                name=item.name,
                columns=[c.name for c in item.columns],
            ),
        )
        name_to_id: dict[str, int] = {}
        for row in await cur.fetchall():
            name_to_id[row["c"]] = row["objsubid"]
        for column in item.columns:
            descs.append(
                ObjectDescription(
                    classid=classid,
                    objid=objid,
                    objsubid=name_to_id[column.name],
                    objtype=f"{item.type} column",
                    objnames=[item.schema_name, item.name, column.name],
                    objargs=[],
                    description=column.description,
                )
            )
    return descs


async def _look_up_proc(
    target_con: psycopg.AsyncConnection, item: Procedure | Function | Aggregate
) -> ObjectDescription:
    """Look up database object IDs for a procedure, function, or aggregate.

    Queries the database to find the object ID for a procedure, function, or aggregate,
    then creates an ObjectDescription object for it.

    Args:
        target_con: Asynchronous database connection to the target database.
        item: A Procedure, Function, or Aggregate object to look up.

    Returns:
        An ObjectDescription object for the procedure, function, or aggregate.

    Raises:
        RuntimeError: If the procedure, function, or aggregate is not found in the database.
    """  # noqa: E501
    async with target_con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """\
            select x.classid, x.objid
            from pg_get_object_address
            ( %(type)s
            , array[%(schema_name)s, %(name)s]::text[]
            , %(args)s::text[]
            ) x
        """,
            dict(
                type=item.type,
                schema_name=item.schema_name,
                name=item.name,
                args=item.args,
            ),
        )
        row = await cur.fetchone()
        if not row:
            raise RuntimeError(
                f"procedure/function not found: {item.schema_name}.{item.name}"
            )
        return ObjectDescription(
            classid=row["classid"],
            objid=row["objid"],
            objsubid=0,
            objtype=item.type,
            objnames=[item.schema_name, item.name],
            objargs=item.args,
            description=item.description,
        )


async def _save_objs(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, objs: list[ObjectDescription]
) -> None:
    """Save object descriptions to the semantic catalog.

    Stores the provided object descriptions in the semantic catalog database.

    Args:
        catalog_con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to save to.
        objs: List of ObjectDescription objects to save.
    """
    async with catalog_con.cursor() as cur:
        for obj in objs:
            await cur.execute(
                """\
                select ai.sc_set_obj_desc
                ( %(classid)s
                , %(objid)s
                , %(objsubid)s
                , %(objtype)s
                , %(objnames)s
                , %(objargs)s
                , %(description)s
                , c.catalog_name
                )
                from ai.semantic_catalog c
                where c.id = %(catalog_id)s
            """,
                dict(
                    catalog_id=catalog_id,
                    classid=obj.classid,
                    objid=obj.objid,
                    objsubid=obj.objsubid,
                    objtype=obj.objtype,
                    objnames=obj.objnames,
                    objargs=obj.objargs,
                    description=obj.description,
                ),
            )


async def _save_sql_example(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, sql_example: SQLExample
) -> None:
    """Save a SQL example to the semantic catalog.

    Stores the provided SQL example in the semantic catalog database.

    Args:
        catalog_con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to save to.
        sql_example: SQLExample object to save.
    """
    async with catalog_con.cursor() as cur:
        if sql_example.id:
            await cur.execute(
                """\
                select ai.sc_update_sql_desc
                ( %(id)s
                , %(sql)s
                , %(description)s
                , c.catalog_name
                )
                from ai.semantic_catalog c
                where c.id = %(catalog_id)s
            """,
                dict(
                    catalog_id=catalog_id,
                    id=sql_example.id,
                    sql=sql_example.sql,
                    description=sql_example.description,
                ),
            )
        else:
            await cur.execute(
                """\
                select ai.sc_add_sql_desc
                ( %(sql)s
                , %(description)s
                , c.catalog_name
                )
                from ai.semantic_catalog c
                where c.id = %(catalog_id)s
            """,
                dict(
                    catalog_id=catalog_id,
                    sql=sql_example.sql,
                    description=sql_example.description,
                ),
            )


async def _save_fact(
    catalog_con: psycopg.AsyncConnection, catalog_id: int, fact: Fact
) -> None:
    """Save a fact to the semantic catalog.

    Stores the provided fact in the semantic catalog database.

    Args:
        catalog_con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to save to.
        fact: Fact object to save.
    """
    async with catalog_con.cursor() as cur:
        if fact.id:
            await cur.execute(
                """\
                select ai.sc_update_fact
                ( %(id)s
                , %(description)s
                , c.catalog_name
                )
                from ai.semantic_catalog c
                where c.id = %(catalog_id)s
            """,
                dict(catalog_id=catalog_id, id=fact.id, description=fact.description),
            )
        else:
            await cur.execute(
                """\
                select ai.sc_add_fact
                ( %(description)s
                , c.catalog_name
                )
                from ai.semantic_catalog c
                where c.id = %(catalog_id)s
            """,
                dict(catalog_id=catalog_id, description=fact.description),
            )


async def save_to_catalog(
    catalog_con: psycopg.AsyncConnection,
    target_con: psycopg.AsyncConnection,
    catalog_id: int,
    items: Iterator[Item],
) -> None:
    """Save catalog items to the semantic catalog database.

    Takes a collection of catalog items and saves them to the semantic catalog database.
    Resolves object IDs from the target database and creates appropriate descriptions.

    Args:
        catalog_con: Asynchronous database connection to the catalog database.
        target_con: Asynchronous database connection to the target database (where objects are defined).
        catalog_id: ID of the semantic catalog to save to.
        items: Iterator of catalog items to save.
    """  # noqa: E501
    for item in items:
        match item.type:
            case "table" | "view":
                await _save_objs(
                    catalog_con, catalog_id, await _look_up_class(target_con, item)
                )
            case "function" | "procedure" | "aggregate":
                await _save_objs(
                    catalog_con, catalog_id, [await _look_up_proc(target_con, item)]
                )
            case "sql_example":
                await _save_sql_example(catalog_con, catalog_id, item)
            case "fact":
                await _save_fact(catalog_con, catalog_id, item)


async def _load_tables_views(
    cur: psycopg.AsyncCursor[DictRow], catalog_id: int
) -> AsyncGenerator[Item, None]:
    """Load table and view descriptions from the semantic catalog.

    Queries the semantic catalog to retrieve table and view descriptions,
    including column descriptions.

    Args:
        cur: Asynchronous database cursor.
        catalog_id: ID of the semantic catalog to load from.

    Returns:
        An async generator yielding Table and View objects.
    """
    await cur.execute(
        SQL("""\
            select
              x.objnames[1] as schema
            , x.objnames[2] as name
            , x.objtype as type
            , x.description
            , (
                select jsonb_agg
                (
                    jsonb_build_object
                    ( 'name', x1.objnames[3]
                    , 'description', x1.description
                    )
                    order by x1.objsubid
                )
                from ai.{} x1
                where x.classid = x1.classid
                and x.objid = x1.objid
                and x1.objsubid != 0
              ) as columns
            from ai.{} x
            where x.objtype in ('table', 'view')
        """).format(
            Identifier(f"semantic_catalog_obj_{catalog_id}"),
            Identifier(f"semantic_catalog_obj_{catalog_id}"),
        )
    )
    for row in await cur.fetchall():
        yield item_from_dict(row)


async def _load_functions_procedures_aggregates(
    cur: psycopg.AsyncCursor[DictRow], catalog_id: int
) -> AsyncGenerator[Item, None]:
    """Load function, procedure, and aggregate descriptions from the semantic catalog.

    Queries the semantic catalog to retrieve function, procedure, and aggregate descriptions.

    Args:
        cur: Asynchronous database cursor.
        catalog_id: ID of the semantic catalog to load from.

    Returns:
        An async generator yielding Function, Procedure, and Aggregate objects.
    """  # noqa: E501
    await cur.execute(
        SQL("""\
            select
              x.objnames[1] as schema
            , x.objnames[2] as name
            , x.objargs as args
            , x.objtype as type
            , x.description
            from ai.{} x
            where x.objtype in ('function', 'procedure', 'aggregate')
        """).format(Identifier(f"semantic_catalog_obj_{catalog_id}"))
    )
    for row in await cur.fetchall():
        yield item_from_dict(row)


async def _load_sql_examples(
    cur: psycopg.AsyncCursor[DictRow], catalog_id: int
) -> AsyncGenerator[Item, None]:
    """Load SQL examples from the semantic catalog.

    Queries the semantic catalog to retrieve SQL examples.

    Args:
        cur: Asynchronous database cursor.
        catalog_id: ID of the semantic catalog to load from.

    Returns:
        An async generator yielding SQLExample objects.
    """
    await cur.execute(
        SQL("""\
            select
              x.id
            , x.sql
            , x.description
            from ai.{} x
        """).format(Identifier(f"semantic_catalog_sql_{catalog_id}"))
    )
    for row in await cur.fetchall():
        row["type"] = "sql_example"
        yield item_from_dict(row)


async def _load_facts(
    cur: psycopg.AsyncCursor[DictRow], catalog_id: int
) -> AsyncGenerator[Item, None]:
    """Load facts from the semantic catalog.

    Queries the semantic catalog to retrieve facts.

    Args:
        cur: Asynchronous database cursor.
        catalog_id: ID of the semantic catalog to load from.

    Returns:
        An async generator yielding Fact objects.
    """
    await cur.execute(
        SQL("""\
            select
              x.id
            , x.description
            from ai.{} x
        """).format(Identifier(f"semantic_catalog_fact_{catalog_id}"))
    )
    for row in await cur.fetchall():
        row["type"] = "fact"
        yield item_from_dict(row)


async def load_from_catalog(
    con: psycopg.AsyncConnection, catalog_id: int
) -> AsyncGenerator[Item, None]:
    """Load all items from the semantic catalog.

    Retrieves all catalog items (tables, views, functions, procedures, aggregates,
    SQL examples, and facts) from the specified semantic catalog.

    Args:
        con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to load from.

    Returns:
        An async generator yielding all catalog items.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        async for item in _load_tables_views(cur, catalog_id):
            yield item
        async for item in _load_functions_procedures_aggregates(cur, catalog_id):
            yield item
        async for item in _load_sql_examples(cur, catalog_id):
            yield item
        async for item in _load_facts(cur, catalog_id):
            yield item


def export_to_yaml(text: TextIO, items: Iterator[Item]) -> None:
    """Export catalog items to a YAML file.

    Writes catalog items to a YAML file with multiple documents. The first document
    is a header with schema version information, followed by one document per item.

    Args:
        text: A text IO stream to write the YAML documents to.
        items: Iterator of catalog items to export.
    """
    text.write(Header().to_yaml())
    for item in items:
        text.write(item.to_yaml())
        text.flush()


async def async_export_to_yaml(text: TextIO, items: AsyncIterator[Item]) -> None:
    """Export catalog items to a YAML file asynchronously.

    Asynchronously writes catalog items to a YAML file with multiple documents. The first document
    is a header with schema version information, followed by one document per item.

    Args:
        text: A text IO stream to write the YAML documents to.
        items: Async iterator of catalog items to export.
    """  # noqa: E501
    text.write(Header().to_yaml())
    async for item in items:
        text.write(item.to_yaml())
        text.flush()

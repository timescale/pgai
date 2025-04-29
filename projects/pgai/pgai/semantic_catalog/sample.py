import io
import logging

import psycopg
from psycopg.sql import SQL, Composed, Identifier, Literal

logger = logging.getLogger(__name__)


async def _sample_as_inserts(
    con: psycopg.AsyncConnection, schema_name: str, object_name: str, limit: int = 3
) -> str:
    async with con.cursor() as cur:
        await cur.execute(
            SQL("select * from {}.{} limit %s").format(
                Identifier(schema_name), Identifier(object_name)
            ),
            (limit,),
        )
        assert cur.description is not None, "cursor description not set"
        rows: list[Composed] = []
        for row in await cur.fetchall():
            rows.append(SQL("({})").format(SQL(", ").join(Literal(val) for val in row)))
        logger.debug(f"sampled {len(rows)} rows from {schema_name}.{object_name}")
        sql = SQL("insert into {}.{} ({}) values\n  {};").format(
            Identifier(schema_name),
            Identifier(object_name),
            SQL(", ").join([Identifier(col.name) for col in cur.description]),
            SQL("\n, ").join(rows),
        )
        return sql.as_string(con)


async def _sample_as_copy_text(
    con: psycopg.AsyncConnection, schema_name: str, object_name: str, limit: int = 3
) -> str:
    query = SQL(
        "copy (select * from {}.{} limit {}) to stdout with (format text, header true)"
    ).format(
        Identifier(schema_name),
        Identifier(object_name),
        Literal(limit),
    )
    buf = io.StringIO()
    buf.write(query.as_string(con))
    buf.write(";\n/*\n")

    async with con.cursor() as cur:
        copy_writer = io.StringIO()
        async with cur.copy(query) as copy_:
            while data := await copy_.read():
                copy_writer.write(bytes(data).decode("utf-8"))
        sample_data = copy_writer.getvalue()
        buf.write(sample_data)

    buf.write("*/")
    return buf.getvalue()


async def sample_table(
    con: psycopg.AsyncConnection,
    schema_name: str,
    table_name: str,
    limit: int = 3,
    format: str = "copy_text",
) -> str:
    assert format in {"inserts", "copy_text"}
    match format:
        case "inserts":
            return await _sample_as_inserts(con, schema_name, table_name, limit)
        case "copy_text":
            return await _sample_as_copy_text(con, schema_name, table_name, limit)
        case _:
            raise RuntimeError(f"unsupported format: {format}")


async def sample_view(
    con: psycopg.AsyncConnection,
    schema_name: str,
    view_name: str,
    limit: int = 3,
    format: str = "copy_text",
) -> str:
    assert format in {"inserts", "copy_text"}
    match format:
        case "inserts":
            return await _sample_as_inserts(con, schema_name, view_name, limit)
        case "copy_text":
            return await _sample_as_copy_text(con, schema_name, view_name, limit)
        case _:
            raise RuntimeError(f"unsupported format: {format}")

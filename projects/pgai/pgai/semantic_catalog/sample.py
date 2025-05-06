import io
import logging

import psycopg
from psycopg.sql import SQL, Composed, Identifier, Literal

logger = logging.getLogger(__name__)


async def _sample_as_inserts(
    con: psycopg.AsyncConnection, schema_name: str, object_name: str, limit: int = 3
) -> str:
    """Generate INSERT statements for sample data from a database object.

    Queries the specified database object and generates INSERT statements
    for a limited number of rows.

    Args:
        con: Asynchronous database connection object.
        schema_name: Name of the schema containing the object.
        object_name: Name of the table or view to sample.
        limit: Maximum number of rows to sample (default: 3).

    Returns:
        A string containing SQL INSERT statements for the sampled data.
    """
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
        sql = SQL("INSERT INTO {}.{} ({}) VALUES\n  {};").format(
            Identifier(schema_name),
            Identifier(object_name),
            SQL(", ").join([Identifier(col.name) for col in cur.description]),
            SQL("\n, ").join(rows),
        )
        return sql.as_string(con)


async def _sample_as_copy_text(
    con: psycopg.AsyncConnection, schema_name: str, object_name: str, limit: int = 3
) -> str:
    """Generate COPY command text for sample data from a database object.

    Queries the specified database object and generates a COPY command with
    sample data in text format, including headers.

    Args:
        con: Asynchronous database connection object.
        schema_name: Name of the schema containing the object.
        object_name: Name of the table or view to sample.
        limit: Maximum number of rows to sample (default: 3).

    Returns:
        A string containing the COPY command followed by the sampled data in text format.
    """  # noqa: E501
    query = SQL(
        "COPY (SELECT * FROM {}.{} LIMIT {}) TO STDOUT WITH (FORMAT TEXT, HEADER true)"
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
    """Sample data from a database table.

    Retrieves a limited number of rows from the specified table and formats the data
    according to the specified format.

    Args:
        con: Asynchronous database connection object.
        schema_name: Name of the schema containing the table.
        table_name: Name of the table to sample.
        limit: Maximum number of rows to sample (default: 3).
        format: Output format, either "inserts" or "copy_text" (default: "copy_text").

    Returns:
        A string containing the sampled data in the requested format.

    Raises:
        RuntimeError: If an unsupported format is specified.
    """
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
    """Sample data from a database view.

    Retrieves a limited number of rows from the specified view and formats the data
    according to the specified format.

    Args:
        con: Asynchronous database connection object.
        schema_name: Name of the schema containing the view.
        view_name: Name of the view to sample.
        limit: Maximum number of rows to sample (default: 3).
        format: Output format, either "inserts" or "copy_text" (default: "copy_text").

    Returns:
        A string containing the sampled data in the requested format.

    Raises:
        RuntimeError: If an unsupported format is specified.
    """
    assert format in {"inserts", "copy_text"}
    match format:
        case "inserts":
            return await _sample_as_inserts(con, schema_name, view_name, limit)
        case "copy_text":
            return await _sample_as_copy_text(con, schema_name, view_name, limit)
        case _:
            raise RuntimeError(f"unsupported format: {format}")

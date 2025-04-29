from importlib.resources import files

import psycopg
import semver
import structlog
from psycopg import sql as sql_lib

from .. import __version__

GUC_VECTORIZER_URL = "ai.external_functions_executor_url"

log = structlog.get_logger()


def _get_sql(vector_extension_schema: str) -> str:
    with files("pgai.data").joinpath("ai.sql").open(mode="r") as f:
        sql = f.read()
    sql = sql.replace("@extschema:vector@", vector_extension_schema)
    sql = sql.replace("__version__", __version__)
    return sql


def warn_if_pre_release() -> None:
    if semver.VersionInfo.parse(__version__).prerelease is not None:
        log.warning("""
            Installing pre-release version of pgai.
                                        
            This is unstable software and no upgrade path is guaranteed.
                    
            Instead, install using the latest release in pip:
            https://pypi.org/project/pgai/
        """)


def _get_guc_vectorizer_url_sql() -> sql_lib.SQL:
    return sql_lib.SQL("select pg_catalog.current_setting(%s, true) as val")


def _get_vector_extension_schema_sql() -> sql_lib.SQL:
    return sql_lib.SQL("""
        select n.nspname
        from pg_extension e
        join pg_namespace n on n.oid = e.extnamespace
        where e.extname = 'vector'
    """)


def _get_server_version_sql() -> sql_lib.SQL:
    return sql_lib.SQL(
        "select current_setting('server_version_num', true)::int / 10000"
    )


def verify_error_library_already_installed(
    error_from_result: psycopg.errors.DuplicateObject,
) -> bool:
    if error_from_result.diag.message_primary is None:
        return False
    return (
        "the pgai library has already been installed/upgraded"
        in error_from_result.diag.message_primary
    )


async def ainstall(
    db_url: str, vector_extension_schema: str | None = None, strict: bool = False
) -> None:
    """Asynchronously install the pgai library into a PostgreSQL database.

    Args:
        db_url: Database connection URL
        vector_extension_schema: Schema where the vector extension is installed if it
            doesn't exist. If None, then the vector extension will be installed in the
            default schema (default: None)
        strict: If False, ignore if library is already installed. If True,
            raise error (default: False)

    Raises:
        psycopg.errors.DuplicateObject: If library is already installed and
            strict=True
    """
    warn_if_pre_release()
    async with (
        await psycopg.AsyncConnection.connect(db_url, autocommit=True) as conn,
        conn.cursor() as cur,
        conn.transaction(),
    ):
        await cur.execute(_get_server_version_sql())
        result = await cur.fetchone()
        pg_version = int(result[0]) if result is not None else None
        if pg_version and pg_version < 15:
            raise RuntimeError(
                f"postgres {pg_version} is unsupported, pgai requires postgres version 15 or greater"  # noqa
            )

        if vector_extension_schema is None:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        else:
            await conn.execute(
                sql_lib.SQL(
                    "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA {}"
                ).format(sql_lib.Literal(vector_extension_schema))
            )

        await cur.execute(_get_vector_extension_schema_sql())
        result = await cur.fetchone()
        if result is None or result[0] is None:
            raise Exception("vector extension not installed")

        sql = _get_sql(result[0])

        # if we need to send a ping to an external url then
        # we need to install the ai extension
        await cur.execute(_get_guc_vectorizer_url_sql(), (GUC_VECTORIZER_URL,))
        result = await cur.fetchone()
        if result is not None and result[0] is not None:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS ai cascade")

        try:
            await conn.execute(sql)  # type: ignore
        except psycopg.errors.DuplicateObject as error_from_result:
            # note the duplicate object error is raised in head.sql by a raise
            # that uses the 42710 error code.
            if not strict and verify_error_library_already_installed(error_from_result):
                pass
            else:
                raise error_from_result


def install(
    db_url: str, vector_extension_schema: str | None = None, strict: bool = False
) -> None:
    """Install the pgai library into a PostgreSQL database.

    Args:
        db_url: Database connection URL
        vector_extension_schema: Schema where the vector extension is installed if it
            doesn't exist. If None, then the vector extension will be installed in the
            default schema (default: None)
        strict: If False, ignore if library is already installed. If True,
            raise error (default: False)

    Raises:
        psycopg.errors.DuplicateObject: If library is already installed and
            strict=True
    """
    warn_if_pre_release()
    with (
        psycopg.connect(db_url, autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(_get_server_version_sql())
        result = cur.fetchone()
        pg_version = int(result[0]) if result is not None else None
        if pg_version and pg_version < 15:
            raise RuntimeError(
                f"postgres {pg_version} is unsupported, pgai requires postgres version 15 or greater"  # noqa
            )

        if vector_extension_schema is None:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        else:
            conn.execute(
                sql_lib.SQL(
                    "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA {}"
                ).format(sql_lib.Literal(vector_extension_schema))
            )

        cur.execute(_get_vector_extension_schema_sql())
        result = cur.fetchone()
        if result is None or result[0] is None:
            raise Exception("vector extension not installed")

        sql = _get_sql(result[0])

        # if we need to send a ping to an external url then
        # we need to install the ai extension
        cur.execute(_get_guc_vectorizer_url_sql(), (GUC_VECTORIZER_URL,))
        result = cur.fetchone()
        if result is not None and result[0] is not None:
            conn.execute("CREATE EXTENSION IF NOT EXISTS ai cascade")

        try:
            conn.execute(sql)  # type: ignore
        except psycopg.errors.DuplicateObject as error_from_result:
            # note the duplicate object error is raised in head.sql by a raise
            # that uses the 42710 error code.
            if not strict and verify_error_library_already_installed(error_from_result):
                pass
            else:
                raise error_from_result

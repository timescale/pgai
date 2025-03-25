from importlib.resources import files
import psycopg
from .. import __version__

GUC_VECTORIZER_URL = "ai.external_functions_executor_url"

def _get_sql(vector_extension_schema: str) -> str:
    with files('pgai.data').joinpath('ai.sql').open(mode='r') as f:
        sql = f.read()
    sql = sql.replace('@extschema:vector@', vector_extension_schema)
    sql = sql.replace('__version__', __version__)
    return sql
    
def _get_guc_vectorizer_url_sql() -> str:
    return f"select pg_catalog.current_setting(%s, true) as val"

def _get_vector_extension_schema_sql() -> str:
    return """
        select n.nspname
        from pg_extension e
        join pg_namespace n on n.oid = e.extnamespace
        where e.extname = 'vector'
    """


def verify_error_library_already_installed(error_from_result: psycopg.errors.DuplicateObject) -> bool:
    return "the pgai library has already been installed/upgraded" in error_from_result.diag.message_primary

async def ainstall(db_url: str, vector_extension_schema: str | None = None, if_not_exists: bool = True) -> None:
    """Asynchronously install the pgai library into a PostgreSQL database.

    Args:
        db_url: Database connection URL
        vector_extension_schema: Schema where the vector extension is installed if it doesn't exist. If None, then the vector extension will be installed in the default schema (default: None)
        if_not_exists: If True, ignore if library is already installed. If False, raise error (default: True)

    Raises:
        psycopg.errors.DuplicateObject: If library is already installed and if_not_exists=False
    """
    
    async with (
            await psycopg.AsyncConnection.connect(db_url, autocommit=True) as conn,
            conn.cursor() as cur,
            conn.transaction(),
        ):
        if vector_extension_schema is None:
            await conn.execute(f"CREATE EXTENSION IF NOT EXISTS vector")
        else:
            await conn.execute(f"CREATE EXTENSION IF NOT EXISTS vector with schema {vector_extension_schema}")
            
        await cur.execute(_get_vector_extension_schema_sql())
        result = await cur.fetchone()
        if result[0] is None:
            raise Exception("vector extension not installed")
        
        sql = _get_sql(result[0])
        
        # if we need to send a ping to an external url, we need to install the ai extension
        await cur.execute(_get_guc_vectorizer_url_sql(), (GUC_VECTORIZER_URL,))
        result = await cur.fetchone()
        if result[0] is not None:
            await conn.execute(f"CREATE EXTENSION IF NOT EXISTS ai cascade")
  
        try:
            await conn.execute(sql)
        except psycopg.errors.DuplicateObject as error_from_result:
            if if_not_exists and verify_error_library_already_installed(error_from_result):
                pass
            else:
                raise error_from_result
        
def install(db_url: str, vector_extension_schema: str | None = None, if_not_exists: bool = True) -> None:
    """Install the pgai library into a PostgreSQL database.

    Args:
        db_url: Database connection URL
        vector_extension_schema: Schema where the vector extension is installed if it doesn't exist. If None, then the vector extension will be installed in the default schema (default: None)
        if_not_exists: If True, ignore if library is already installed. If False, raise error (default: True)
    """
    with (
        psycopg.connect(db_url, autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        if vector_extension_schema is None:
            conn.execute(f"CREATE EXTENSION IF NOT EXISTS vector")
        else:
            conn.execute(f"CREATE EXTENSION IF NOT EXISTS vector with schema {vector_extension_schema}")
        
        cur.execute(_get_vector_extension_schema_sql())
        result = cur.fetchone()
        if result[0] is None:
            raise Exception("vector extension not installed")
        
        sql = _get_sql(result[0])
        
        # if we need to send a ping to an external url, we need to install the ai extension
        cur.execute(_get_guc_vectorizer_url_sql(), (GUC_VECTORIZER_URL,))
        result = cur.fetchone()
        if result[0] is not None:
            conn.execute(f"CREATE EXTENSION IF NOT EXISTS ai cascade")
            
        try:    
            conn.execute(sql)
        except psycopg.errors.DuplicateObject as error_from_result:
            if if_not_exists and verify_error_library_already_installed(error_from_result):
                pass
            else:
                raise error_from_result

from importlib.resources import files
import psycopg
from .. import __version__

def _get_sql(vector_extension_schema: str) -> str:
    with files('pgai.data').joinpath('ai.sql').open(mode='r') as f:
        sql = f.read()
    sql = sql.replace('@extschema:vector@', vector_extension_schema)
    sql = sql.replace('__version__', __version__)
    return sql
    

async def ainstall(db_url: str, vector_extension_schema: str = 'public') -> None:
    sql = _get_sql(vector_extension_schema)
    
    async with (
            await psycopg.AsyncConnection.connect(db_url, autocommit=True) as conn,
            conn.cursor() as cur,
            conn.transaction(),
        ):
        await conn.execute(f"CREATE EXTENSION IF NOT EXISTS vector with schema {vector_extension_schema}")
        await conn.execute(sql)
        
def install(db_url: str, vector_extension_schema: str = 'public') -> None:
    sql = _get_sql(vector_extension_schema)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(f"CREATE EXTENSION IF NOT EXISTS vector with schema {vector_extension_schema}")
        conn.execute(sql)
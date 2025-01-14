from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

connection_string = "postgresql+asyncpg://postgres:postgres@localhost/postgres"
engine = create_async_engine(connection_string)


class Base(DeclarativeBase):
    pass

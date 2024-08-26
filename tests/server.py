from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError
import psycopg
from typing import Union, Literal


app = FastAPI()


class IndexingNone(BaseModel):
    implementation: Literal['none']


class IndexingDiskANN(BaseModel):
    implementation: Literal['diskann']
    min_rows: int
    storage_layout: str | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None


class IndexingHNSW(BaseModel):
    implementation: Literal['hnsw']
    min_rows: int
    opclass: str | None = None
    m: int | None = None
    ef_construction: int | None = None


class Config(BaseModel):
    version: str
    indexing: Union[IndexingNone, IndexingDiskANN, IndexingHNSW] = Field(..., discriminator='implementation')
    formatting: dict
    embedding: dict
    chunking: dict


class PrimaryKeyColumn(BaseModel):
    attnum: int
    pknum: int
    attname: str
    typname: str


class Vectorizer(BaseModel):
    id: int
    asynchronous: bool
    external: bool
    source_schema: str
    source_table: str
    source_pk: list[PrimaryKeyColumn]
    target_schema: str
    target_table: str
    trigger_name: str
    queue_schema: str | None = None
    queue_table: str | None = None
    config: Config


def vectorize(v: Vectorizer) -> int:
    # pretend to work the queue
    with psycopg.connect("postgres://postgres@127.0.0.1:5432/test") as con:
        while True:
            with con.cursor() as cur:
                cur.execute(f"""
                    delete from {v.queue_schema}.{v.queue_table}
                """)
                return cur.rowcount


@app.post("/")
async def execute_vectorizer(vectorizer: Vectorizer):
    print(f"vectorizer: {vectorizer.id}")
    # do this in a blocking manner to make the tests easier
    # we KNOW that when the HTTP request has returned that the work has been done
    deleted = vectorize(vectorizer)
    print(f"queue emptied: {deleted} rows deleted")
    return {"id": vectorizer.id}
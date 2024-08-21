import random
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
import psycopg


app = FastAPI()


class PrimaryKeyColumn(BaseModel):
    attnum: int
    pknum: int
    attname: str
    typname: str
    attnotnull: bool


class Vectorizer(BaseModel):
    id: int
    asynchronous: bool
    external: bool
    source_schema: str
    source_table: str
    source_pk: list[PrimaryKeyColumn]
    target_schema: str
    target_table: str
    target_column: str
    queue_schema: str | None = None
    queue_table: str | None = None
    config: dict


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
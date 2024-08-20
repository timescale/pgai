
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import psycopg

app = FastAPI()


class Vectorizer(BaseModel):
    id: int
    asynchronous: bool
    external: bool
    source_schema: str
    source_table: str
    source_pk: list[dict]
    target_schema: str
    target_table: str
    target_column: str
    queue_schema: str | None = None
    queue_table: str | None = None
    config: dict


def work_the_queue(queue_schema: str, queue_table: str):
    # pretend to work the queue
    with psycopg.connect("postgres://postgres@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            cur.execute(f"""
                delete from {queue_schema}.{queue_table}
            """)


@app.post("/")
async def execute_vectorizer(vectorizer: Vectorizer):
    print(f"vectorizer: {vectorizer}")
    work_the_queue(vectorizer.queue_schema, vectorizer.queue_table)
    print("returning...")
    return {"id": vectorizer.id}
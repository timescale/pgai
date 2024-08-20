from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()


class Vectorizer(BaseModel):
    id: int
    asynchronous: bool
    external: bool
    source_schema: str
    source_table: str
    source_pk: dict
    target_schema: str
    target_table: str
    target_column: str
    queue_schema: Optional[str] = None
    queue_table: Optional[str] = None
    config: dict


@app.post("/")
async def execute_vectorizer(vectorizer: dict):
    return {"id": vectorizer["id"]}


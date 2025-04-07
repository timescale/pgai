import os
from datetime import datetime
from typing import Literal

import dotenv
import psycopg
from fastapi import FastAPI, Header, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

dotenv.load_dotenv()

app = FastAPI()

DB_URL = "postgres://postgres@127.0.0.1:5432/test"


class ChunkingCharacterTextSplitter(BaseModel):
    implementation: Literal["character_text_splitter"]
    config_type: Literal["chunking"]
    chunk_size: int
    chunk_overlap: int
    separator: str | None
    is_separator_regex: bool | None


class ChunkingRecursiveCharacterTextSplitter(BaseModel):
    implementation: Literal["recursive_character_text_splitter"]
    config_type: Literal["chunking"]
    chunk_size: int
    chunk_overlap: int
    separators: list[str] | None
    is_separator_regex: bool | None


class ChunkingNone(BaseModel):
    implementation: Literal["none"]
    config_type: Literal["chunking"]


class EmbeddingOpenAI(BaseModel):
    implementation: Literal["openai"]
    config_type: Literal["embedding"]
    model: str
    dimensions: int
    user: str | None = None
    api_key_name: str | None = "OPENAI_API_KEY"


class FormattingPythonTemplate(BaseModel):
    implementation: Literal["python_template"]
    config_type: Literal["formatting"]
    template: str


class IndexingNone(BaseModel):
    implementation: Literal["none"]
    config_type: Literal["indexing"]


class IndexingDiskANN(BaseModel):
    implementation: Literal["diskann"]
    config_type: Literal["indexing"]
    min_rows: int
    storage_layout: Literal["memory_optimized"] | Literal["plain"] | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None


class IndexingHNSW(BaseModel):
    implementation: Literal["hnsw"]
    config_type: Literal["indexing"]
    min_rows: int
    opclass: (
        Literal["vector_ip_ops"]
        | Literal["vector_cosine_ops"]
        | Literal["vector_l1_ops"]
        | None
    ) = None
    m: int | None = None
    ef_construction: int | None = None


class SchedulingNone(BaseModel):
    implementation: Literal["none"]
    config_type: Literal["scheduling"]


class SchedulingPgCron(BaseModel):
    implementation: Literal["pg_cron"]
    config_type: Literal["scheduling"]
    schedule: str


class SchedulingTimescaledb(BaseModel):
    implementation: Literal["timescaledb"]
    config_type: Literal["scheduling"]
    schedule_interval: str | None = None
    initial_start: datetime | None = None
    fixed_schedule: bool | None = None
    timezone: str | None = None


class ProcessingDefault(BaseModel):
    implementation: Literal["default"]
    config_type: Literal["processing"]
    batch_size: int | None = None
    concurrency: int | None = None


class LoadingColumn(BaseModel):
    implementation: Literal["column"]
    config_type: Literal["loading"]
    column_name: str


class LoadingUri(BaseModel):
    implementation: Literal["uri"]
    config_type: Literal["loading"]
    column_name: str


class ParsingAuto(BaseModel):
    implementation: Literal["auto"]
    config_type: Literal["parsing"]


class ParsingNone(BaseModel):
    implementation: Literal["none"]
    config_type: Literal["parsing"]


class ParsingPyMuPDF(BaseModel):
    implementation: Literal["pymupdf"]
    config_type: Literal["parsing"]


class ParsingDocling(BaseModel):
    implementation: Literal["docling"]
    config_type: Literal["parsing"]


class Config(BaseModel):
    version: str
    indexing: IndexingNone | IndexingDiskANN | IndexingHNSW = Field(
        ..., discriminator="implementation"
    )
    formatting: FormattingPythonTemplate
    embedding: EmbeddingOpenAI
    scheduling: SchedulingNone | SchedulingPgCron | SchedulingTimescaledb = Field(
        ..., discriminator="implementation"
    )
    chunking: (
        ChunkingCharacterTextSplitter
        | ChunkingRecursiveCharacterTextSplitter
        | ChunkingNone
    ) = Field(..., discriminator="implementation")
    processing: ProcessingDefault = Field(..., discriminator="implementation")
    loading: LoadingColumn | LoadingUri = Field(..., discriminator="implementation")
    parsing: ParsingAuto | ParsingNone | ParsingPyMuPDF | ParsingDocling = Field(
        ..., discriminator="implementation"
    )


class PrimaryKeyColumn(BaseModel):
    attnum: int
    pknum: int
    attname: str
    typname: str


class Vectorizer(BaseModel):
    id: int
    source_schema: str
    source_table: str
    source_pk: list[PrimaryKeyColumn]
    trigger_name: str
    queue_schema: str | None = None
    queue_table: str | None = None
    config: Config


def vectorize(v: Vectorizer) -> int:
    # pretend to work the queue
    with psycopg.connect(DB_URL) as con:
        while True:
            with con.cursor() as cur:
                cur.execute(f"""
                    delete from {v.queue_schema}.{v.queue_table}
                """)
                return cur.rowcount


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


@app.post("/api/v1/events")
async def execute_vectorizer(vectorizer: Vectorizer):
    print(f"execute vectorizer: {vectorizer.id}")
    # do this in a blocking manner to make the tests easier
    # we KNOW that when the HTTP request has returned that the work has been done
    deleted = vectorize(vectorizer)
    print(f"queue emptied: {deleted} rows deleted")
    return {"id": vectorizer.id}


@app.get("/api/v1/projects/secrets")
async def get_secrets(secret_name: str = Header(None, alias="Secret-Name")):
    if not secret_name:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Secret-Name header is required"},
        )

    # For now, we'll just return the test key if the secret_name matches
    if secret_name == "OPENAI_API_KEY" or secret_name == "OPENAI_API_KEY_2":
        return {secret_name: "test"}
    elif secret_name == "OPENAI_API_KEY_REAL":
        return {secret_name: os.environ["OPENAI_API_KEY"]}
    elif secret_name == "COHERE_API_KEY_REAL":
        return {secret_name: os.environ["COHERE_API_KEY"]}
    elif secret_name == "ANTHROPIC_API_KEY_REAL":
        return {secret_name: os.environ["ANTHROPIC_API_KEY"]}
    elif secret_name == "ERROR_SECRET":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "error secret"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Secret '{secret_name}' not found"},
        )

import asyncio
import fastapi
import ollama
import pgai
import psycopg
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pgai.vectorizer import Processor
from fastapi.logger import logger as fastapi_logger
from pgai.vectorizer import CreateVectorizer
from pgai.vectorizer.configuration import EmbeddingOllamaConfig, LoadingColumnConfig
from datasets import load_dataset
import logging
from typing import List, Optional, Tuple, Dict
from psycopg_pool import AsyncConnectionPool
from dataclasses import dataclass, asdict
from psycopg.rows import class_row, dict_row
from pgvector.psycopg import register_vector_async
import numpy as np
DB_URL = "postgresql://postgres:postgres@localhost:5432/test"

logger = logging.getLogger('fastapi_cli')

async def setup_pgvector_psycopg(conn: psycopg.AsyncConnection):
    await register_vector_async(conn)

# Change to AsyncConnectionPool
pool = AsyncConnectionPool(DB_URL, min_size=5, max_size=10, open=False, configure=setup_pgvector_psycopg)

async def create_wiki_table():
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS wiki (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL
                )
            """)
        await conn.commit()


async def create_vectorizer():
    vectorizer_statement = CreateVectorizer(
        source="wiki",
        target_table='wiki_embedding_storage',
        loading=LoadingColumnConfig(column_name='text'),
        embedding=EmbeddingOllamaConfig(model='all-minilm', dimensions=384, base_url="http://localhost:11434")
    ).to_sql()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(vectorizer_statement)
            await conn.commit()
    except Exception as e:
        if "already exists" in str(e):
            # ignore if the vectorizer already exists
            pass
        else:
            raise e

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting lifespan")
    
    # TODO: Remove this once we have latest extension in docker image
    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("DROP EXTENSION IF EXISTS ai")
        await conn.commit()
    
    # install pgai tables and functions into the database
    pgai.install(DB_URL)
   
    # Initialize the pool after the pgai tables and functions are installed
    await pool.open()
    
    # start the processor in a new process running in the background
    processor = Processor(DB_URL)
    task = asyncio.create_task(processor.run())
    
    await create_wiki_table()
    
    if await wiki_table_is_empty():
        await load_wiki_articles()
        
    await create_vectorizer()
    
    yield
    
    print("Shutting down...")
    
    # Close the pool during shutdown
    print("Closing pool")
    await pool.close()
    
    print("gracefully shutting down processor...")
    await processor.request_graceful_shutdown()
    try:
        result = await asyncio.wait_for(task, timeout=20)
        if result is not None:
            print("Processor shutdown with exception:", result)
        else:
            print("Processor shutdown successfully")
    except asyncio.TimeoutError:
        print("Processor did not shutdown in time, killing it")
    
    print("Shutting down complete")

app = FastAPI(lifespan=lifespan)

async def wiki_table_is_empty() -> bool:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM wiki")
            res = await cur.fetchone()
            return res[0] == 0

async def load_wiki_articles():
    # to keep the demo fast, we have some simple limits
    num_articles = 10
    max_text_length = 1000
    
    wiki_dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split=f"train", streaming=True)
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for article in wiki_dataset.take(num_articles):
                await cur.execute(
                    "INSERT INTO wiki (url, title, text) VALUES (%s, %s, %s)",
                    (article['url'], article['title'], article['text'][:max_text_length])
                )
            await conn.commit()

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@dataclass
class WikiSearchResult:
    id: int
    url: str
    title: str
    text: str
    chunk: str
    distance: float

async def _find_relevant_chunks(client: ollama.AsyncClient, query: str, limit: int = 2) -> List[WikiSearchResult]:
    response = await client.embed(model="all-minilm", input=query)
    embedding = np.array(response.embeddings[0])
    
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=class_row(WikiSearchResult)) as cur:
            await cur.execute("""
                SELECT w.id, w.url, w.title, w.text, w.chunk, w.embedding <=> %s as distance
                FROM wiki_embedding w
                ORDER BY distance
                LIMIT %s
            """, (embedding, limit))
            
            return await cur.fetchall()

@app.get("/search")
async def search(query: str):
    client = ollama.AsyncClient(host="http://localhost:11434")
    results = await _find_relevant_chunks(client, query)
    return [asdict(result) for result in results]  

@app.get("/vectorizer_status")
async def vectorizer_status():
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM ai.vectorizer_status")
            return await cur.fetchall()

@app.post("/insert_pgai_article")
async def insert_pgai_article():
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO wiki (url, title, text)
                VALUES (%s, %s, %s)
            """, (
                "https://en.wikipedia.org/wiki/Pgai",
                "pgai - Power your AI applications with PostgreSQL",
                "pgai is a tool to make developing RAG and other AI applications easier..."
            ))
            await conn.commit()
    return {"message": "Article inserted successfully"}

@app.get("/rag")
async def generate_rag_response(query: str) -> Optional[str]:
    """
    Generate a RAG response using pgai, Ollama embeddings, and database content.
    
    Args:
        query_text: The question or query to answer
    
    Returns:
        str: The generated response from the LLM
    """
    # Initialize Ollama client
    client = ollama.AsyncClient(host="http://localhost:11434")
    chunks = await _find_relevant_chunks(client, query)
    context = "\n\n".join(
        f"{chunk.title}:\n{chunk.text}" 
        for chunk in chunks
    )
    
    logger.debug(f"Context: {context}")
    
    # Construct prompt with context
    prompt = f"""Question: {query}

Please use the following context to provide an accurate response:

{context}

Answer:"""
            
    # Generate response using Ollama SDK
    response = await client.generate(
        model='tinyllama',
        prompt=prompt,
        stream=False
    )
    
    return response['response']

import fastapi
import ollama
import pgai
import sqlalchemy
from sqlalchemy.orm import Session
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgai.sqlalchemy import vectorizer_relationship
from datasets import load_dataset
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pgai.vectorizer import ProcProcessor
from fastapi.logger import logger as fastapi_logger

from pgai.vectorizer import CreateVectorizer
from pgai.vectorizer.configuration import EmbeddingOllamaConfig, ChunkingCharacterTextSplitterConfig, FormattingPythonTemplateConfig, LoadingColumnConfig

import logging
from typing import List, Optional, Tuple

DB_URL = "postgresql://postgres:postgres@localhost:5432/test"
engine = sqlalchemy.create_engine(DB_URL)

logger = logging.getLogger('fastapi_cli')


def create_vectorizer():
    vectorizer_statement = CreateVectorizer(
        source="wiki",
        target_table='wiki_embeddings',
        loading=LoadingColumnConfig(column_name='text'),
        embedding=EmbeddingOllamaConfig(model='all-minilm', dimensions=384, base_url="http://localhost:11434")
    ).to_sql()
    
    try:
        with Session(engine) as session:
            session.execute(sqlalchemy.text(vectorizer_statement))
            session.commit()
    except Exception as e:
        if "already exists" in str(e):
            logger.warning(f"Vectorizer already exists: {e}")
        else:
            logger.error(f"Error creating vectorizer: {e}")
            raise e


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting lifespan")
    with engine.connect() as connection:
        connection.execute(sqlalchemy.text("DROP EXTENSION IF EXISTS ai"))
        connection.commit()
    
    # install pgai tables and functions into the database
    pgai.install(DB_URL)
    
    # start the processor in a new process running in the background
    processor = ProcProcessor(DB_URL)
    processor.run_in_new_process()
    
    # Create the table
    Base.metadata.create_all(bind=engine)
    create_vectorizer()
    
    if wiki_table_is_empty():
        load_wiki_articles()
        
    # continue the main process
    yield
    
    print("Shutting down...")
    shutdown_exception = await processor.shutdown_gracefully()
    if shutdown_exception is not None:
        print("Shutdown exception:", shutdown_exception)

app = FastAPI(lifespan=lifespan)

class Base(DeclarativeBase):
    pass

class Wiki(Base):
    __tablename__ = "wiki"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str]
    title: Mapped[str]
    text: Mapped[str]

    # Add vector embeddings for the text field
    text_embeddings = vectorizer_relationship(
        target_table='wiki_embeddings',
        dimensions=384
    )

def wiki_table_is_empty():
    with Session(engine) as session:
        result = session.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(Wiki))
        return result.scalar() == 0

def load_wiki_articles():
    # to keep the demo fast, we have some simple limits
    num_articles = 10
    max_text_length = 1000
    
    # Load and insert Wikipedia dataset from Hugging Face
    wiki_dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split=f"train", streaming=True)
    
    with Session(engine) as session:
        for article in wiki_dataset.take(num_articles):
            wiki = Wiki(
                url=article['url'],
                title=article['title'],
                text=article['text'][:max_text_length]
            )
            session.add(wiki)
        session.commit()
    
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

WikiSearchResult = List[Tuple[Wiki, float]]

async def _find_relevant_chunks(client: ollama.AsyncClient, query: str, limit: int = 2) -> WikiSearchResult:
    response = await client.embed(model="all-minilm", input=query)
    embedding = response.embeddings[0]
    with Session(engine) as session:
        # Query both the Wiki model and its embeddings
        result = session.query(
            Wiki,
            Wiki.text_embeddings.embedding.cosine_distance(embedding).label('distance')
        ).join(Wiki.text_embeddings).order_by(
            'distance'
        ).limit(limit).all()
        
    return result
        
@app.get("/search")
async def search(query: str):
    client = ollama.AsyncClient(host="http://localhost:11434")
    
    result = await _find_relevant_chunks(client, query)
    # Convert results to a list of dictionaries
    return [
        {
            "id": article.id,
            "url": article.url,
            "title": article.title,
            "text": article.text,
            "distance": distance
        }
        for article, distance in result
    ]

@app.post("/insert_pgai_article")
async def insert_pgai_article():
    with Session(engine) as session:
        session.add(Wiki(
            url="https://en.wikipedia.org/wiki/Pgai",
            title="pgai - Power your AI applications with PostgreSQL",
            text="pgai is a tool to make developing RAG and other AI applications easier. It makes it simple to give an LLM access to data in your PostgreSQL database by enabling semantic search on your data and using the results as part of the Retrieval Augmented Generation (RAG) pipeline. This allows the LLM to answer questions about your data without needing to being trained on your data.'"
        ))
        session.commit()
    return {"message": "Article inserted successfully"}

@app.get("/rag")
async def generate_rag_response(query_text: str) -> Optional[str]:
    """
    Generate a RAG response using pgai, Ollama embeddings, and database content.
    
    Args:
        query_text: The question or query to answer
    
    Returns:
        str: The generated response from the LLM
    """
    # Initialize Ollama client
    client = ollama.AsyncClient(host="http://localhost:11434")
    chunks = await _find_relevant_chunks(client, query_text)
    context = "\n\n".join(f"{article.title}:\n{article.text}" for article, _ in chunks)
    
    logger.debug(f"Context: {context}")
    
    # Construct prompt with context
    prompt = f"""Question: {query_text}

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
import asyncio
from typing import List
import pgai
from pgai.vectorizer import Worker
import psycopg
from dataclasses import dataclass
import os
import dotenv
from openai import AsyncClient, AsyncOpenAI
from datasets import load_dataset
import numpy as np
from psycopg.rows import class_row
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool
import structlog
import logging
from pprint import pprint

# Configure structlog to only show WARNING level logs and above
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
)

# Load environment variables from .env file or system environment
dotenv.load_dotenv()
DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Create a connection pool to the database for efficient connection management
# Using a connection pool is best practice for production applications
async def setup_pgvector_psycopg(conn: psycopg.AsyncConnection):
    await register_vector_async(conn)
pool = AsyncConnectionPool(DB_URL, min_size=5, max_size=10, open=False, configure=setup_pgvector_psycopg)

async def define_schema(conn: psycopg.AsyncConnection):
    """
    Create the wiki table if it doesn't exist.
    This table stores Wikipedia articles with their URLs, titles, and text content.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS wiki (
                id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL
            )
        """)
 
async def create_vectorizer(conn: psycopg.AsyncConnection):
    """
    Create a vectorizer that defines how embeddings are generated from the wiki table.
    The vectorizer specifies:
    - The source table ('wiki')
    - The column to use for generating embeddings ('text')
    - The embedding model to use (OpenAI's text-embedding-ada-002 with 1536 dimensions)
    - The destination view for querying embeddings ('wiki_embedding')
    """
    async with conn.cursor() as cur:    
        await cur.execute("""
            SELECT ai.create_vectorizer(
                'wiki'::regclass,
                if_not_exists => true,
                loading => ai.loading_column(column_name=>'text'),
                embedding => ai.embedding_openai(model=>'text-embedding-ada-002', dimensions=>'1536'),
                destination => ai.destination_table(view_name=>'wiki_embedding')
            )
        """)   
    await conn.commit()

async def load_wiki_articles_from_huggingface(conn: psycopg.AsyncConnection):
    """
    Load a limited number of Wikipedia articles from the Hugging Face dataset.
    For demonstration purposes, we limit the number of articles and text length.
    """
    # Limit the number of articles and text length for demonstration purposes
    num_articles = 10
    max_text_length = 1000
    wiki_dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split="train", streaming=True)
    async with conn.cursor() as cur:
        for i, article in enumerate(wiki_dataset):
            if i >= num_articles:
                break
            await cur.execute(
                "INSERT INTO wiki (url, title, text) VALUES (%s, %s, %s)",
                (article['url'], article['title'], article['text'][:max_text_length])
            )
    await conn.commit()

@dataclass
class WikiSearchResult:
    """
    Data class representing a search result from the vector database.
    Contains metadata about the Wikipedia article and the similarity score.
    """
    id: int
    url: str
    title: str
    text: str
    chunk: str
    distance: float
    
    def __str__(self):
        return f"""WikiSearchResult:
    ID: {self.id}
    URL: {self.url}
    Title: {self.title}
    Text: {self.text[:100]}...
    Chunk: {self.chunk}
    Distance: {self.distance:.4f}"""

async def _find_relevant_chunks(client: AsyncOpenAI, query: str, limit: int = 1) -> List[WikiSearchResult]:
    """
    Find the most relevant text chunks for a given query using vector similarity search.
    
    Args:
        client: OpenAI client for generating embeddings
        query: The search query
        limit: Maximum number of results to return
        
    Returns:
        List of WikiSearchResult objects sorted by relevance
    """
    # Generate embedding for the query using OpenAI's API
    response = await client.embeddings.create(
        model="text-embedding-ada-002",
        input=query,
        encoding_format="float",
    )
    
    embedding = np.array(response.data[0].embedding)
    
    # Query the database for the most similar chunks using pgvector's cosine distance operator (<=>)
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=class_row(WikiSearchResult)) as cur:
            await cur.execute("""
                SELECT w.id, w.url, w.title, w.text, w.chunk, w.embedding <=> %s as distance
                FROM wiki_embedding w
                ORDER BY distance
                LIMIT %s
            """, (embedding, limit))
            
            return await cur.fetchall()
            
async def insert_article_about_pgai(conn: psycopg.AsyncConnection):
    """
    Insert a custom article about pgai into the wiki table.
    The vectorizer worker will automatically generate embeddings for this new article.
    """
    async with conn.cursor() as cur:
        await cur.execute("""
            INSERT INTO wiki (url, title, text) VALUES
            ('https://en.wikipedia.org/wiki/pgai', 'pgai', 'pgai is a Python library that turns PostgreSQL into the retrieval engine behind robust, production-ready RAG and Agentic applications. It does this by automatically creating vector embeddings for your data based on the vectorizer you define.')
        """)
    await conn.commit() 
    
async def run():
    """
    Main function that demonstrates the complete pgai workflow:
    1. Install pgai components in the database
    2. Set up the schema and vectorizer
    3. Load sample data
    4. Generate embeddings
    5. Perform vector similarity search
    6. Demonstrate RAG (Retrieval-Augmented Generation) with an LLM
    """
    # Install pgai components (catalog tables and functions) in the 'ai' schema
    pgai.install(DB_URL)

    # Initialize the connection pool after pgai installation
    await pool.open()  
    
    # Set up the database schema, create vectorizer, and load sample data
    async with pool.connection() as conn:
        await define_schema(conn)
        await create_vectorizer(conn)
        await load_wiki_articles_from_huggingface(conn)
    
    # Run the vectorizer worker once to generate embeddings for all articles
    worker = Worker(DB_URL, once=True)
    await worker.run()
   
    # Perform a vector similarity search to find relevant articles
    client = AsyncClient()
    results = await _find_relevant_chunks(client, "Who is the father of computer science?")
    print("Search results 1:")
    pprint(results)
    
    # Insert a new article about pgai to demonstrate dynamic embedding generation
    async with pool.connection() as conn:
        await insert_article_about_pgai(conn)
    
    # Run the worker again to process the new article
    # In a production environment, the worker would run continuously in the background
    # Example of how to run it continuously:
    # worker = Worker(DB_URL)
    # task = asyncio.create_task(worker.run())
    await worker.run()
    
    # Search again to demonstrate that the new article is now searchable
    results = await _find_relevant_chunks(client, "What is pgai?")
    print("Search results 2:")
    pprint(results)
    
    # Demonstrate RAG (Retrieval-Augmented Generation) by:
    # 1. Finding relevant chunks for a query
    # 2. Using those chunks as context for an LLM
    # 3. Getting a response that combines the retrieved information with the LLM's knowledge
    query = "What is the main thing pgai does right now?"
    relevant_chunks = await _find_relevant_chunks(client, query)
    context = "\n\n".join(
        f"{chunk.title}:\n{chunk.text}" 
        for chunk in relevant_chunks
    )
    prompt = f"""Question: {query}

Please use the following context to provide an accurate response:   

{context}

Answer:"""

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    print("RAG response:")
    print(response.choices[0].message.content)
    
    
# Run the main function
asyncio.run(run())
import numpy as np
from fastapi import FastAPI, Query, Depends
from sqlalchemy import select, literal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator


from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression

from db.engine import engine
from db.models import CodeFileEmbedding

from pydantic import BaseModel, Field, computed_field
from typing import List

SEPARATOR = "-" * 80
CODE_BLOCK = "```"


class CodeChunk(BaseModel):
    """Represents a single chunk of code with its context"""

    file_name: str = Field(description="Name of the source file")
    chunk: str = Field(description="The relevant code segment")
    chunk_seq: int = Field(description="Sequence number of this chunk in the file")
    similarity_score: float = Field(
        description="Cosine similarity score (higher is more similar)"
    )

    class Config:
        from_attributes = True


class CodeSearchResponse(BaseModel):
    """Response model for code search results"""

    query: str = Field(description="The search query that was used")
    matches: List[CodeChunk] = Field(description="Matching code chunks found")
    total_matches: int = Field(description="Total number of matches found")

    @computed_field
    @property
    def format_for_llm(self) -> str:
        """Returns the results formatted as a string suitable for LLM input"""
        chunks = []
        for match in self.matches:
            chunk_text = (
                f"File: {match.file_name}\n"
                f"Similarity: {match.similarity_score:.3f}\n"
                f"Code Chunk #{match.chunk_seq}:\n"
                f"{CODE_BLOCK}\n{match.chunk}\n{CODE_BLOCK}\n"
            )
            chunks.append(chunk_text)

        header = f"Search Query: {self.query}\n\nFound {self.total_matches} relevant code chunks:\n\n{SEPARATOR}\n\n"
        return header + "\n".join(chunks)


app = FastAPI()


@app.get("/", response_model=dict[str, str])
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session


def parse_embedding_string(embedding_str: str) -> np.ndarray:
    """Convert a pgai embedding string to a numpy array"""
    # Remove brackets and split on commas
    values = embedding_str.strip("[]").split(",")
    # Convert to float array
    return np.array([float(x) for x in values], dtype=">f4")


class OpenAIEmbed(FunctionElement):
    inherit_cache = True


class PGAIFunction(expression.FunctionElement):
    def __init__(self, model: str, text: str, dimensions: int):
        self.model = model
        self.text = literal(text)
        self.dimensions = dimensions
        super().__init__()


@compiles(PGAIFunction)
def _compile_pgai_embed(element, compiler, **kw):
    return "ai.openai_embed('%s', %s, dimensions => %d)" % (
        element.model,
        compiler.process(element.text),
        element.dimensions,
    )


@app.get("/search", response_model=CodeSearchResponse)
async def search_code(
    query: str = Query(..., description="Natural language search query for code"),
    limit: int = Query(
        default=5, ge=1, le=20, description="Maximum number of results to return"
    ),
    session: AsyncSession = Depends(get_db),
) -> CodeSearchResponse:
    """
    Search code files using semantic similarity.
    Returns code chunks most relevant to the natural language query.
    """
    embedding_func = PGAIFunction("text-embedding-3-small", query, 768)

    similarity_score = (
        1 - CodeFileEmbedding.embedding.cosine_distance(embedding_func)
    ).label("similarity_score")

    # Find most similar code chunks
    results = await session.execute(
        select(
            CodeFileEmbedding.file_name,
            CodeFileEmbedding.chunk,
            CodeFileEmbedding.chunk_seq,
            similarity_score,
        )
        .order_by(similarity_score.desc())
        .limit(limit)
    )

    matches = [
        CodeChunk(
            file_name=row.file_name,
            chunk=row.chunk,
            chunk_seq=row.chunk_seq,
            similarity_score=row.similarity_score,
        )
        for row in results
    ]

    return CodeSearchResponse(query=query, matches=matches, total_matches=len(matches))

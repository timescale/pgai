import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from db.models import CodeFile
from main import CodeSearchResponse

SAMPLE_CODE = [
    {
        "file_name": "auth.py",
        "contents": """
def authenticate_user(username: str, password: str) -> bool:
    \"\"\"Authenticate a user with username and password\"\"\"
    # Hash the password and check against stored hash
    hashed = hash_password(password)
    return check_password_hash(username, hashed)
""",
    },
    {
        "file_name": "utils.py",
        "contents": """
def format_datetime(dt: datetime, format: str = "%Y-%m-%d") -> str:
    \"\"\"Format a datetime object to string\"\"\"
    return dt.strftime(format)
""",
    },
    {
        "file_name": "logging.py",
        "contents": """
def setup_logger(name: str, level: str = "INFO") -> Logger:
    \"\"\"Configure and return a logger instance\"\"\"
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    return logger
""",
    },
]


@pytest.yield_fixture(scope="session")
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def sample_code(async_session: AsyncSession):
    """Insert sample code files and wait for embeddings to be created"""
    # Insert sample code
    for code in SAMPLE_CODE:
        code_file = CodeFile(file_name=code["file_name"], contents=code["contents"])
        async_session.add(code_file)
    await async_session.commit()

    # Wait for vectorizer to process (with timeout)
    max_wait = 15  # seconds
    check_interval = 1  # second

    for _ in range(max_wait):
        # Check if all files have embeddings
        result = await async_session.execute(
            text("""
            SELECT ai.vectorizer_queue_pending(1);
            """)
        )
        pending_count = result.scalar()

        if pending_count == 0:
            # All embeddings have been created
            return

        await asyncio.sleep(check_interval)

    raise TimeoutError("Vectorizer did not process items within expected timeframe")


@pytest.mark.asyncio
async def test_search_basic_functionality(test_client: TestClient, sample_code: None):
    """Test basic search functionality with known code samples"""
    # Search for authentication related code
    response = test_client.get(
        "/search", params={"query": "how to authenticate users", "limit": 2}
    )

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "query" in data
    assert "matches" in data
    assert "total_matches" in data

    # Verify the auth function is the top match
    assert len(data["matches"]) > 0
    top_match = data["matches"][0]
    assert top_match["file_name"] == "auth.py"
    assert "authenticate_user" in top_match["chunk"]
    assert top_match["similarity_score"] > 0.3

    # Verify formatting
    formatted = CodeSearchResponse(**data).format_for_llm
    assert "Search Query:" in formatted
    assert "```" in formatted  # Code blocks are present
    assert "auth.py" in formatted


@pytest.mark.asyncio
async def test_search_limit_handling(test_client: TestClient, sample_code: None):
    """Test search with different limit values"""
    # Test maximum limit
    response = test_client.get(
        "/search",
        params={
            "query": "code",
            "limit": 25,  # Over our max of 20
        },
    )
    assert response.status_code == 422  # Validation error

    # Test minimum limit
    response = test_client.get("/search", params={"query": "code", "limit": 0})
    assert response.status_code == 422  # Validation error

    # Test valid limit
    response = test_client.get("/search", params={"query": "code", "limit": 2})
    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) == 2


@pytest.mark.asyncio
async def test_search_semantic_matching(test_client: TestClient, sample_code: None):
    """Test that semantically similar concepts are matched"""
    # Search for logging with different terms
    response = test_client.get(
        "/search",
        params={
            "query": "how to create a logger",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # The logging.py file should be a top match even though
    # "create" isn't in the actual code
    assert any(
        match["file_name"] == "logging.py" and match["similarity_score"] > 0.1
        for match in data["matches"]
    )

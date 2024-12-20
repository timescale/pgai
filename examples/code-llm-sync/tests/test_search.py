import asyncio
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CodeFile
from main import CodeSearchResponse
from tests.utils import wait_for_vectorizer

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

    # Wait for vectorizer to process
    await wait_for_vectorizer(async_session)


@pytest.mark.asyncio
async def test_search_basic_functionality(test_client: AsyncClient, sample_code: None):
    """Test basic search functionality with known code samples"""
    # Search for authentication related code
    response = await test_client.get(
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
async def test_search_limit_handling(test_client: AsyncClient, sample_code: None):
    """Test search with different limit values"""
    # Test maximum limit
    response = await test_client.get(
        "/search",
        params={
            "query": "code",
            "limit": 25,  # Over our max of 20
        },
    )
    assert response.status_code == 422  # Validation error

    # Test minimum limit
    response = await test_client.get("/search", params={"query": "code", "limit": 0})
    assert response.status_code == 422  # Validation error

    # Test valid limit
    response = await test_client.get("/search", params={"query": "code", "limit": 2})
    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) == 2


@pytest.mark.asyncio
async def test_search_semantic_matching(test_client: AsyncClient, sample_code: None):
    """Test that semantically similar concepts are matched"""
    # Search for logging with different terms
    response = await test_client.get(
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




@pytest.mark.asyncio
async def test_create_file_basic(test_client: AsyncClient, async_session: AsyncSession, vectorizer_worker):
    """Test basic file creation with valid data and verify embeddings are created"""
    # Test data
    file_data = {
        "file_name": "test_file.py",
        "contents": """def hello_world():
    \"\"\"A simple test function\"\"\"
    return 'Hello, World!'"""
    }

    # Create the file
    response = await test_client.post("/files", json=file_data)

    # Verify response
    assert response.status_code == 201
    data = response.json()
    assert data["file_name"] == file_data["file_name"]
    assert data["contents"] == file_data["contents"]
    assert "id" in data
    assert "updated_at" in data

    # Verify the timestamp is recent
    updated_at = datetime.fromisoformat(data["updated_at"])
    assert (datetime.now(timezone.utc) - updated_at).total_seconds() < 60

    # Wait for vectorizer to process
    await wait_for_vectorizer(async_session)

    # Verify embeddings were created by doing a search
    search_response = await test_client.get(
        "/search",
        params={"query": "hello world function", "limit": 1}
    )

    assert search_response.status_code == 200
    search_data = search_response.json()
    assert len(search_data["matches"]) > 0

    # The new file should be the top match for this query
    top_match = search_data["matches"][0]
    assert top_match["file_name"] == file_data["file_name"]
    assert "hello_world" in top_match["chunk"]
    assert top_match["similarity_score"] > 0.3  # High relevance for exact match


@pytest.mark.asyncio
async def test_update_existing_file(
        test_client: AsyncClient,
        async_session: AsyncSession,
        vectorizer_worker,
):
    """Test updating an existing file and verify embeddings are updated"""
    # First create a test file
    initial_content = {
        "file_name": "update_me.py",
        "contents": """def hello():
    \"\"\"Initial version of function\"\"\"
    return 'Hello, World!'"""
    }

    # Create initial file
    response = await test_client.post("/files", json=initial_content)
    assert response.status_code == 201
    initial_data = response.json()

    # Wait for initial embeddings
    await wait_for_vectorizer(async_session)

    # Verify initial embeddings via search
    initial_search = await test_client.get(
        "/search",
        params={"query": "initial version of function", "limit": 1}
    )
    assert initial_search.status_code == 200
    assert any(
        match["file_name"] == "update_me.py"
        for match in initial_search.json()["matches"]
    )

    # Update the file with new content
    updated_content = {
        "file_name": "update_me.py",
        "contents": """def hello():
    \"\"\"Updated version of function\"\"\"
    return 'Hello, Updated World!'"""
    }

    update_response = await test_client.post("/files", json=updated_content)
    assert update_response.status_code == 201
    updated_data = update_response.json()

    # Verify response data
    assert updated_data["id"] == initial_data["id"]  # Same ID
    assert updated_data["file_name"] == initial_data["file_name"]  # Same filename
    assert updated_data["contents"] == updated_content["contents"]  # New content
    assert updated_data["updated_at"] > initial_data["updated_at"]  # Timestamp updated

    # Wait for embeddings to update
    await wait_for_vectorizer(async_session)

    # Verify new embeddings via search
    # Should find the updated content
    new_search = await test_client.get(
        "/search",
        params={"query": "updated version of function", "limit": 1}
    )
    assert new_search.status_code == 200
    new_matches = new_search.json()["matches"]
    assert len(new_matches) > 0
    assert any(
        match["file_name"] == "update_me.py" and "Updated version" in match["chunk"]
        for match in new_matches
    )

    # Verify old content is not findable
    old_search = await test_client.get(
        "/search",
        params={"query": "initial version of function", "limit": 5}
    )
    assert old_search.status_code == 200
    assert not any(
        match["file_name"] == "update_me.py" and "Initial version" in match["chunk"]
        for match in old_search.json()["matches"]
    )


@pytest.mark.asyncio
async def test_delete_file(
        test_client: AsyncClient,
        async_session: AsyncSession,
        vectorizer_worker,
):
    """Test deleting a file including verification of embedding cleanup"""
    # First create a test file
    file_data = {
        "file_name": "to_be_deleted.py",
        "contents": """def delete_me():
    \"\"\"A function that will be deleted\"\"\"
    return 'Goodbye!'"""
    }

    # Create the file
    response = await test_client.post("/files", json=file_data)
    assert response.status_code == 201

    # Wait for vectorizer to process and create embeddings
    await wait_for_vectorizer(async_session)

    # Verify embeddings exist by doing a search
    search_response = await test_client.get(
        "/search",
        params={"query": "function that will be deleted", "limit": 1}
    )
    assert search_response.status_code == 200
    assert len(search_response.json()["matches"]) > 0
    assert any(
        match["file_name"] == "to_be_deleted.py"
        for match in search_response.json()["matches"]
    )

    # Delete the file
    delete_response = await test_client.delete("/files/to_be_deleted.py")
    assert delete_response.status_code == 204

    await wait_for_vectorizer(async_session)

    # Verify file is gone by trying to search for it
    search_response = await test_client.get(
        "/search",
        params={"query": "function that will be deleted", "limit": 1}
    )
    assert search_response.status_code == 200
    assert not any(
        match["file_name"] == "to_be_deleted.py"
        for match in search_response.json()["matches"]
    )


@pytest.mark.asyncio
async def test_delete_nonexistent_file(
        test_client: AsyncClient,
        async_session: AsyncSession,
):
    """Test attempting to delete a file that doesn't exist"""
    response = await test_client.delete("/files/does_not_exist.py")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()
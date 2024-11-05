import os
from pathlib import Path

import docker
import pytest_asyncio
from docker import DockerClient
from docker.models.containers import Container
from fastapi.testclient import TestClient
from typing import Generator, AsyncGenerator

import pytest

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app

# Test database configuration
TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost/postgres"
project_root = Path(__file__).parent.parent


@pytest_asyncio.fixture(scope="session")
async def async_engine(event_loop):
    """Create a async database engine."""
    engine = create_async_engine(TEST_DB_URL, echo=True, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def load_dotenv():
    """Load environment variables from .env file"""
    from dotenv import load_dotenv

    env_file = project_root / ".env"
    load_dotenv(env_file)


@pytest.fixture(scope="session")
def docker_client() -> Generator[DockerClient, None, None]:
    """Create a Docker client"""
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture(scope="session")
def vectorizer_worker(
    docker_client: DockerClient, load_dotenv
) -> Generator[Container, None, None]:
    """Start vectorizer worker after database is ready"""
    # Configure container
    container_config = {
        "image": "timescale/pgai-vectorizer-worker:0.1.0",
        "environment": {
            "PGAI_VECTORIZER_WORKER_DB_URL": "postgres://postgres:postgres@host.docker.internal:5432/postgres",
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        },
        "command": ["--poll-interval", "5s"],
        "extra_hosts": {
            "host.docker.internal": "host-gateway"
        },  # Allow container to connect to host postgres
    }

    # Start container
    container = docker_client.containers.run(**container_config, detach=True)

    # Wait for container to be running
    container.reload()
    assert container.status == "running"

    yield container

    # Cleanup
    container.stop()
    container.remove()


@pytest.fixture(scope="session")
def test_client(
    vectorizer_worker: docker.models.containers.Container,
) -> Generator[TestClient, None, None]:
    """Create a FastAPI TestClient"""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def async_session_maker(async_engine):
    """Create a fixture for the async session maker."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def async_session(async_session_maker) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh sqlalchemy session for each test."""
    async with async_session_maker() as session:
        yield session
        await session.rollback()

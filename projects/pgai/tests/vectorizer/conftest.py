import os

import pytest
import tiktoken
from testcontainers.core.image import DockerImage  # type:ignore
from testcontainers.postgres import PostgresContainer  # type:ignore

from pgai.vectorizer.vectorizer import TIKTOKEN_CACHE_DIR

DIMENSION_COUNT = 1536


@pytest.fixture(autouse=True)
def __env_setup():  # type:ignore
    # Capture the current environment variables to restore after the test. The
    # lambda function sets an evironment variable for using the secrets. We
    # need to clear the environment after a test runs.
    original_env = os.environ.copy()

    # Use the existing tiktoken cache
    os.environ["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR
    yield

    tiktoken.registry.ENCODINGS = {}

    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="session")
def postgres_container():
    extension_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../extension/")
    )
    image = DockerImage(path=extension_dir, tag="pgai-test-db").build(  # type: ignore
        target="pgai-test-db"
    )
    with PostgresContainer(
        image=str(image),
        username="tsdbquerier",
        password="my-password",
        dbname="tsdb",
        driver=None,
    ) as postgres:
        yield postgres

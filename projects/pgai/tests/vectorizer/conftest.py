import os
from pathlib import Path
from typing import Any

import pytest
import tiktoken
import vcr  # type:ignore
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


def remove_set_cookie_header(response: dict[str, Any]):
    headers = response["headers"]
    headers_to_remove = ["set-cookie", "Set-Cookie"]
    for header in headers_to_remove:
        if header in headers:
            del headers[header]
    return response


@pytest.fixture(scope="session")
def vcr_():
    cassette_library_dir = Path(__file__).parent.joinpath("cassettes")
    cassette_library_dir.mkdir(exist_ok=True)
    return vcr.VCR(
        serializer="yaml",
        cassette_library_dir=str(cassette_library_dir),
        record_mode=vcr.mode.ONCE,
        filter_headers=["authorization"],
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
        before_record_response=remove_set_cookie_header,
    )


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

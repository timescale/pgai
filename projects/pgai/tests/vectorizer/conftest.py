import os
from collections.abc import Callable, Generator, Mapping
from pathlib import Path
from typing import Any

import pytest
import tiktoken
import vcr  # type:ignore
from dotenv import load_dotenv
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
        ignore_hosts=["huggingface.co"],
    )


@pytest.fixture(scope="session")
def postgres_container_manager() -> (
    Generator[Callable[[bool], PostgresContainer], None, None]
):
    extension_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../extension/")
    )
    image = DockerImage(path=extension_dir, tag="pgai-test-db").build(  # type: ignore
        target="pgai-test-db"
    )

    containers: dict[str, PostgresContainer] = {}

    def get_container(load_openai_key: bool = True) -> PostgresContainer:
        # Use config as cache key
        key = f"openai_{load_openai_key}"

        if key not in containers:
            container = PostgresContainer(
                image=str(image),
                username="tsdbquerier",
                password="my-password",
                dbname="tsdb",
                driver=None,
            )

            if load_openai_key:
                load_dotenv()
                openai_api_key = os.environ["OPENAI_API_KEY"]
                container = container.with_env("OPENAI_API_KEY", openai_api_key)

            containers[key] = container
            container.start()

        return containers[key]

    yield get_container

    # Cleanup all containers
    for container in containers.values():
        container.stop()


@pytest.fixture
def postgres_container(
    request: pytest.FixtureRequest,
    postgres_container_manager: Callable[[bool], PostgresContainer],
) -> Generator[PostgresContainer, None, None]:
    marker: pytest.Mark | None = None
    for marker in request.node.iter_markers():  # type: ignore
        if marker.name == "postgres_params":  # type: ignore
            break

    params: Mapping[str, Any] = marker.kwargs if marker else {}  # type: ignore
    load_openai_key: bool = params.get("load_openai_key", True)  # type: ignore

    return postgres_container_manager(load_openai_key=load_openai_key)  # type: ignore

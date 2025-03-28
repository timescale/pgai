import asyncio
import os
import threading
from collections.abc import Callable, Generator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import docling.utils.model_downloader
import pytest
import tiktoken
import vcr  # type:ignore
from dotenv import load_dotenv
from mitmproxy import options
from mitmproxy.http import HTTPFlow
from mitmproxy.tools.dump import DumpMaster
from testcontainers.core.image import DockerImage  # type:ignore
from testcontainers.postgres import PostgresContainer  # type:ignore

from pgai.vectorizer.parsing import DOCLING_CACHE_DIR
from pgai.vectorizer.vectorizer import TIKTOKEN_CACHE_DIR

DIMENSION_COUNT = 1536


@pytest.fixture(scope="session", autouse=True)
def download_docling_models():
    # pre-fetch all models required by docling
    # this is done to avoid downloading the models during the tests.
    # Models are downloaded to: ~/.cache/huggingface/hub/models--ds4sd--docling-models
    print("Attempting to download docling models.")
    docling.utils.model_downloader.download_models(
        progress=True,
        output_dir=DOCLING_CACHE_DIR,
    )


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
        filter_headers=["authorization", "api-key"],
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
        before_record_response=remove_set_cookie_header,
    )


@pytest.fixture(scope="session")
def postgres_container_manager() -> (
    Generator[Callable[[bool, bool, str], PostgresContainer], None, None]
):
    extension_dir = (
        Path(__file__).parent.parent.parent.parent.joinpath("extension").resolve()
    )
    image = DockerImage(path=extension_dir, tag="pgai-test-db").build(  # type: ignore
        target="pgai-test-db"
    )

    containers: dict[str, PostgresContainer] = {}

    def get_container(
        load_openai_key: bool = True,
        set_executor_url: bool = False,
        ai_extension_version: str = "",
    ) -> PostgresContainer:
        # Use config as cache key
        key = f"openai_{load_openai_key}+executor_url_{set_executor_url}+ai_extension_version_{ai_extension_version}"  # noqa: E501

        if key not in containers:
            container = PostgresContainer(
                image=str(image),
                username="tsdbquerier",
                password="my-password",
                dbname="tsdb",
                driver=None,
            )

            if set_executor_url:
                container = container.with_command(
                    "-c 'ai.external_functions_executor_url=http://www.example.com'"
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


def create_connection_url(
    container: PostgresContainer,
    username: str | None = None,
    password: str | None = None,
    dbname: str | None = None,
):
    host = container._docker.host()  # type: ignore
    return super(PostgresContainer, container)._create_connection_url(  # type: ignore
        dialect="postgresql",
        username=username or container.username,
        password=password or container.password,
        dbname=dbname or container.dbname,
        host=host,
        port=container.port,
    )


@pytest.fixture
def postgres_container(
    request: pytest.FixtureRequest,
    postgres_container_manager: Callable[[bool, str], PostgresContainer],
) -> PostgresContainer:
    marker: pytest.Mark | None = None
    for marker in request.node.iter_markers():  # type: ignore
        if marker.name == "postgres_params":  # type: ignore
            break

    params: Mapping[str, Any] = marker.kwargs if marker else {}  # type: ignore
    load_openai_key: bool = params.get("load_openai_key", True)  # type: ignore
    set_executor_url: bool = params.get("set_executor_url", False)  # type: ignore
    ai_extension_version: str = params.get("ai_extension_version", "")  # type: ignore

    return postgres_container_manager(  # type: ignore
        load_openai_key=load_openai_key,  # type: ignore
        set_executor_url=set_executor_url,
        ai_extension_version=ai_extension_version,
    )


class ReverseProxyAddon:
    def __init__(self, target_url: str):
        self.target = urlparse(target_url)

    def request(self, flow: HTTPFlow):
        flow.request.host = str(self.target.hostname)
        flow.request.path = self.target.path + flow.request.path
        flow.request.scheme = "https"
        flow.request.port = 443


def run_reverse_proxy(
    target_host: str, listen_port: int = 8000, listen_host: str = "localhost"
):
    async def start_proxy():
        opts = options.Options(listen_host=listen_host, listen_port=listen_port)
        master = DumpMaster(opts)
        master.addons.add(ReverseProxyAddon(target_host))  # type:ignore

        try:
            await master.run()
        finally:
            master.shutdown()

    # mitmproxy relies on asyncio for its event loop
    def run_event_loop():
        asyncio.run(start_proxy())

    proxy_thread = threading.Thread(target=run_event_loop, daemon=True)
    proxy_thread.start()


@pytest.fixture(scope="module")
def openai_proxy_url(request: pytest.FixtureRequest):
    if not hasattr(request, "param") or request.param is None:
        # a valid url is required in order to start the openai proxy fixture
        return None

    port = request.param
    run_reverse_proxy("https://api.openai.com/v1", port)

    proxy_url = f"http://localhost:{port}"
    print(f"OpenAI API proxy running on {proxy_url}")
    return f"http://localhost:{port}"

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
        ignore_hosts=["huggingface.co", "localhost:8000"],
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


from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
from urllib.parse import urlparse, urljoin
import threading

class OpenAIProxy(BaseHTTPRequestHandler):
    openai_api_url = "https://api.openai.com/v1"

    # Only Post is allowed by now (embeddings path is POST).
    def do_POST(self):
        target = urlparse(self.openai_api_url)
        dest_path = target.path + self.path
        print(f"Proxied request to {target.hostname}{dest_path}")

        conn = http.client.HTTPSConnection(target.hostname, 443)

        # Forward headers and body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        conn.request("POST", dest_path, body, {k: v for k, v in self.headers.items() if k.lower() != "host"})

        # Relay the response back to the client
        response = conn.getresponse()
        self.send_response(response.status)
        for key, value in response.getheaders():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.read())
        conn.close()


from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.http import HTTPFlow
import asyncio


class ReverseProxy:
    def __init__(self, target_url):
        self.target = urlparse(target_url)

    def request(self, flow: HTTPFlow):
        if flow.request.method == "POST":
            flow.request.host = self.target.hostname
            flow.request.path = self.target.path + flow.request.path
            flow.request.scheme = "https"
            flow.request.port = 443


def run_reverse_proxy(target_host, listen_host="localhost", listen_port=8080):
    async def start_proxy():
        # Create mitmproxy options
        opts = options.Options(listen_host=listen_host, listen_port=listen_port)

        # Initialize DumpMaster and add the ReverseProxy addon
        master = DumpMaster(opts)
        master.addons.add(ReverseProxy(target_host))

        try:
            await master.run()  # Run the proxy asynchronously
        except KeyboardInterrupt:
            await master.shutdown()

    # Start the event loop in a separate thread
    def run_event_loop():
        asyncio.run(start_proxy())

    proxy_thread = threading.Thread(target=run_event_loop, daemon=True)
    proxy_thread.start()
    return proxy_thread


@pytest.fixture(scope="function")
def openai_proxy_url(request: pytest.FixtureRequest):
    if not hasattr(request, "param") or request.param is None:
        # a valid url is required in order to start the openai proxy fixture
        yield None
        return

    port = request.param

    # # Start the reverse proxy, forwarding POST requests to "example.com"
    # master, proxy_thread = run_reverse_proxy("https://api.openai.com/v1", "localhost", port)
    # proxy_url = f"http://localhost:{port}"
    # print(f"OpenAI API proxy running on {proxy_url}")

    # yield f"http://localhost:{port}"

    proxy_thread = run_reverse_proxy("https://api.openai.com/v1", "localhost", port)

    proxy_url = f"http://localhost:{port}"
    print(f"OpenAI API proxy running on {proxy_url}")
    yield f"http://localhost:{port}"
    try:
        while proxy_thread.is_alive():
            pass
    except KeyboardInterrupt:
        print("Shutting down OpenAI proxy...")



# @pytest.fixture(scope="function")
# def openai_proxy_url(request: pytest.FixtureRequest):
#     if not hasattr(request, "param") or request.param is None:
#         # a valid url is required in order to start the openai proxy fixture
#         yield None
#         return
#
#     port = request.param
#
#     server = HTTPServer(('', port), OpenAIProxy)
#     print(f"OpenAI API proxy running on port {port}")
#     # server.serve_forever()
#
#     thread = threading.Thread(target=server.serve_forever, daemon=True)
#     thread.start()  # Start the server in a separate thread
#     yield f"http://localhost:{port}"
#     server.shutdown()
#     # try:
#     #     server.serve_forever()
#     # except KeyboardInterrupt:
#     #     print("Shutting down OpenAI API proxy...")
#     #     server.shutdown()


import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click
import vcr  # type: ignore
from vcr.record_mode import RecordMode  # type: ignore

from pgai import __version__ as pgai_version
from pgai.cli import TimeDurationParamType, async_run_vectorizer_worker


@click.command(name="worker-with-vcr")
@click.version_option(version=pgai_version)
@click.option(
    "--cassette",
    type=click.STRING,
    default="wiki_openai_500",
    show_default=True,
    help="VCR cassette to use on the benchmark",
)
@click.option(
    "--record-mode",
    type=click.STRING,
    default="once",
    show_default=True,
    help="VCR record mode (all, any, new_episodes, none, once)",
)
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The database URL to connect to",
)
@click.option(
    "-i",
    "--vectorizer-id",
    "vectorizer_ids",
    type=click.INT,
    multiple=True,
    help="Only fetch work from the given vectorizer ids. If not provided, all vectorizers will be fetched.",  # noqa
    default=[],
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
@click.option(
    "--poll-interval",
    type=TimeDurationParamType(),
    default="5m",
    show_default=True,
    help="The interval, in duration string or integer (seconds), "
    "to wait before checking for new work after processing "
    "all available work in the queue.",
    # noqa
)
@click.option(
    "--once",
    type=click.BOOL,
    is_flag=True,
    default=False,
    show_default=True,
    help="Exit after processing all available work (implies --exit-on-error).",
)
@click.option(
    "-c",
    "--concurrency",
    type=click.IntRange(1),
    default=None,
    show_default=True,
)
@click.option(
    "--exit-on-error",
    type=click.BOOL,
    default=None,
    show_default=True,
    help="Exit immediately when an error occurs.",
)
def worker_with_vcr(
    cassette: str,
    record_mode: str,
    db_url: str,
    vectorizer_ids: Sequence[int],
    concurrency: int,
    log_level: str,
    poll_interval: int,
    once: bool,
    exit_on_error: bool | None,
) -> None:
    cassette_library_dir = Path(__file__).parent.joinpath("cassettes")
    cassette_library_dir.mkdir(exist_ok=True)

    def remove_set_cookie_header(response: dict[str, Any]):
        headers = response["headers"]
        headers_to_remove = ["set-cookie", "Set-Cookie"]
        for header in headers_to_remove:
            if header in headers:
                del headers[header]
        return response

    vcr_ = vcr.VCR(
        serializer="yaml",
        cassette_library_dir=str(cassette_library_dir),
        record_mode=RecordMode(record_mode.lower()),
        filter_headers=["authorization", "api-key"],
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
        before_record_response=remove_set_cookie_header,
    )
    with vcr_.use_cassette(cassette):  # type: ignore
        asyncio.run(
            async_run_vectorizer_worker(
                db_url,
                vectorizer_ids,
                log_level,
                poll_interval,
                once,
                concurrency,
                exit_on_error,
            )
        )


@click.group()
@click.version_option(version=pgai_version)
def vectorizer():
    pass


@click.group()
@click.version_option(version=pgai_version)
def cli():
    pass


vectorizer.add_command(worker_with_vcr)
cli.add_command(vectorizer)

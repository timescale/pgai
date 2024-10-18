import asyncio
import logging
import os
from typing import Any

import structlog
from pydantic import AliasChoices, Field, ValidationError
from pydantic.dataclasses import dataclass

from . import db
from .processing import ProcessingDefault
from .vectorizer import Vectorizer, Worker

TIKTOKEN_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tiktoken_cache"
)
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
logger = structlog.get_logger()


@dataclass
class UpdateEmbeddings:
    db: db.ConnInfo
    secrets: dict[str, str | None]


@dataclass
class Event:
    update_embeddings: UpdateEmbeddings
    vectorizer: Vectorizer = Field(validation_alias=AliasChoices("payload"))


async def run_workers(
    concurrency: int,
    conn_info: db.ConnInfo,
    vectorizer: Vectorizer,
) -> list[int]:
    """Runs the embedding tasks and wait for them to finish."""
    tasks = [
        asyncio.create_task(Worker(conn_info.url, vectorizer).run())
        for _ in range(concurrency)
    ]
    return await asyncio.gather(*tasks)


def set_log_level(cf: ProcessingDefault):
    level = logging.getLevelName(cf.log_level)  # type: ignore
    if cf.log_level != "INFO" and isinstance(level, int):
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))


def lambda_handler(raw_event: dict[str, Any], _: Any) -> dict[str, int]:
    """Lambda entry point. Validates the config given via the event, and
    starts the embedding tasks.

    Args:
        raw_event (dict): maps to the `Event` dataclass.
    """
    try:
        event = Event(**raw_event)
    except ValidationError as e:
        raise e

    # The type error we are ignoring is because there's only one type available
    # for Config.processing. We keep the check to signal intent, in case we add
    # other types in the future.
    if isinstance(event.vectorizer.config.processing, ProcessingDefault):  # type: ignore
        set_log_level(event.vectorizer.config.processing)

    event.vectorizer.config.embedding.set_api_key(event.update_embeddings.secrets)

    os.environ["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR
    results = asyncio.run(
        run_workers(
            event.vectorizer.config.processing.concurrency,
            event.update_embeddings.db,
            event.vectorizer,
        )
    )
    return {"statusCode": 200, "processed_tasks": sum(results)}

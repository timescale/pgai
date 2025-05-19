import asyncio
import datetime
import os
import random
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass

import psycopg
import semver
import structlog
from psycopg.rows import dict_row, namedtuple_row

from .. import __version__
from .embeddings import ApiKeyMixin
from .features import Features
from .vectorizer import Vectorizer
from .worker_tracking import WorkerTracking

if sys.version_info >= (3, 11):
    from builtins import BaseExceptionGroup
else:
    # For Python 3.10 and below, use the backport
    from exceptiongroup import BaseExceptionGroup

logger = structlog.get_logger()


@dataclass
class Version:
    ext_version: str | None
    pgai_lib_version: str | None


class VectorizerNotFoundError(Exception):
    pass


class ApiKeyNotFoundError(Exception):
    pass


def warn_on_old_version(version: Version):
    if version.pgai_lib_version is None:
        if (
            version.ext_version is not None
            and semver.Version.parse(version.ext_version) < "0.10.0"
        ):
            logger.warning(
                "The pgai extension is outdated and can be upgraded. See https://github.com/timescale/pgai/blob/main/docs/vectorizer/migrating-from-extension.md"
            )
    else:
        if semver.Version.parse(__version__) > semver.Version.parse(
            version.pgai_lib_version
        ):
            logger.warning(
                f"The pgai installation in your database is outdated and can be upgraded. Installed version: {version.pgai_lib_version}, latest version: {__version__}."  # noqa
            )


class Worker:
    def __init__(
        self,
        db_url: str,
        poll_interval: datetime.timedelta = datetime.timedelta(minutes=1),
        once: bool = False,
        vectorizer_ids: Sequence[int] = [],
        exit_on_error: bool | None = None,
        concurrency: int | None = None,
    ):
        self.vectorizer_ids = vectorizer_ids
        self.db_url = db_url
        self.poll_interval = int(poll_interval.total_seconds())
        self.once = once
        self.exit_on_error = exit_on_error
        self.concurrency = concurrency
        self.shutdown_requested = asyncio.Event()

        self.dynamic_mode = len(self.vectorizer_ids) == 0
        if once and exit_on_error is None:
            # once implies exit-on-error
            self.exit_on_error = True

    @staticmethod
    def _get_pgai_version(cur: psycopg.Cursor) -> Version | None:
        cur.execute(
            "select extversion from pg_catalog.pg_extension where extname = 'ai'"
        )
        row = cur.fetchone()
        ext_version = row[0] if row is not None else None

        # todo: think this through more, expecially for Feature Flags
        pgai_lib_version = None
        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'ai'
                AND table_name = 'pgai_lib_version'
            )
        """)
        res = cur.fetchone()
        assert res is not None
        table_exists = res[0]
        if table_exists:
            cur.execute("select version from ai.pgai_lib_version where name = 'ai'")
            row = cur.fetchone()
            pgai_lib_version = row[0] if row is not None else None
        return Version(ext_version, pgai_lib_version)

    def _get_vectorizer(self, vectorizer_id: int, features: Features) -> Vectorizer:
        with (
            psycopg.Connection.connect(self.db_url) as con,
            con.cursor(row_factory=dict_row) as cur,
        ):
            cur.execute(
                "select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v where v.id = %s",  # noqa
                (vectorizer_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise VectorizerNotFoundError(f"vectorizer_id={vectorizer_id}")
            vectorizer = row["vectorizer"]
            embedding = vectorizer["config"]["embedding"]
            vectorizer = Vectorizer.model_validate(vectorizer)

            # The Ollama API doesn't need a key, so `api_key_name` may be unset
            if "api_key_name" in embedding:
                api_key_name = embedding["api_key_name"]
                api_key = os.getenv(api_key_name, None)
                if api_key is not None:
                    logger.debug(f"obtained secret '{api_key_name}' from environment")
                elif features.db_reveal_secrets:
                    cur.execute(
                        "select ai.reveal_secret(%s)",
                        (api_key_name,),
                    )
                    row = cur.fetchone()
                    api_key = row["reveal_secret"] if row is not None else None
                    if api_key is not None:
                        logger.debug(f"obtained secret '{api_key_name}' from database")
                if not api_key:
                    raise ApiKeyNotFoundError(
                        f"api_key_name={api_key_name} vectorizer_id={vectorizer_id}"
                    )
                secrets: dict[str, str | None] = {api_key_name: api_key}
                # The Ollama API doesn't need a key, so doesn't inherit `ApiKeyMixin`
                if isinstance(vectorizer.config.embedding, ApiKeyMixin):
                    vectorizer.config.embedding.set_api_key(secrets)
                else:
                    logger.error(
                        f"cannot set secret value '{api_key_name}' for vectorizer with id: '{vectorizer.id}'"  # noqa
                    )
            return vectorizer

    async def _handle_error(
        self,
        error_message: str,
        vectorizer_id: int | None,
        worker_tracking: WorkerTracking | None,
    ) -> Exception:
        kwargs = {}
        if vectorizer_id:
            kwargs["vectorizer_id"] = vectorizer_id
        logger.error(error_message, **kwargs)
        if worker_tracking is not None:
            await worker_tracking.save_vectorizer_error(vectorizer_id, error_message)
        if self.exit_on_error:
            if worker_tracking is not None:
                await worker_tracking.force_last_heartbeat_and_stop()
            logger.info("exiting processor due to error")
        return Exception(error_message)

    def _get_vectorizer_ids(
        self, vectorizer_ids: Sequence[int] | None = None
    ) -> list[int]:
        with (
            psycopg.Connection.connect(self.db_url) as con,
            con.cursor(row_factory=namedtuple_row) as cur,
        ):
            valid_vectorizer_ids: list[int] = []
            if vectorizer_ids is None or len(vectorizer_ids) == 0:
                cur.execute("select id from ai.vectorizer")
            else:
                cur.execute(
                    "select id from ai.vectorizer where id = any(%s)",
                    [
                        list(vectorizer_ids),
                    ],
                )
            for row in cur.fetchall():
                valid_vectorizer_ids.append(row[0])
            random.shuffle(valid_vectorizer_ids)
            return valid_vectorizer_ids

    async def request_graceful_shutdown(self):
        """
        Request a graceful shutdown of the processor.
        """
        self.shutdown_requested.set()

    async def run(self) -> Exception | None:
        logger.debug("starting vectorizer worker")

        valid_vectorizer_ids = []
        can_connect = False
        pgai_version = None
        features = None
        worker_tracking = None

        while not self.shutdown_requested.is_set():
            vectorizer_id = None
            try:
                if not can_connect or pgai_version is None:
                    with (
                        psycopg.Connection.connect(self.db_url) as con,
                        con.cursor(row_factory=namedtuple_row) as cur,
                    ):
                        pgai_version = self._get_pgai_version(cur)
                        if pgai_version is None or (
                            pgai_version.ext_version is None
                            and pgai_version.pgai_lib_version is None
                        ):
                            err_msg = "pgai is not installed in the database"
                            exception = await self._handle_error(
                                err_msg, None, worker_tracking
                            )
                            if self.exit_on_error:
                                return exception
                        else:
                            warn_on_old_version(pgai_version)
                            features = Features.from_db(cur)
                            worker_tracking = WorkerTracking(
                                self.db_url, self.poll_interval, features, __version__
                            )
                            await worker_tracking.start()
                            can_connect = True

                if can_connect and features is not None and worker_tracking is not None:
                    if not self.dynamic_mode and len(valid_vectorizer_ids) != len(
                        self.vectorizer_ids
                    ):
                        valid_vectorizer_ids = self._get_vectorizer_ids(
                            self.vectorizer_ids,
                        )
                        if len(valid_vectorizer_ids) != len(self.vectorizer_ids):
                            err_msg = f"invalid vectorizers, wanted: {list(self.vectorizer_ids)}, got: {valid_vectorizer_ids}"  # noqa: E501
                            exception = await self._handle_error(
                                err_msg,
                                None,
                                worker_tracking,
                            )
                            if self.exit_on_error:
                                return exception
                    else:
                        valid_vectorizer_ids = self._get_vectorizer_ids(
                            self.vectorizer_ids,
                        )
                        if len(valid_vectorizer_ids) == 0:
                            logger.warning("no vectorizers found")

                    for vectorizer_id in valid_vectorizer_ids:
                        try:
                            vectorizer = self._get_vectorizer(vectorizer_id, features)
                        except (VectorizerNotFoundError, ApiKeyNotFoundError) as e:
                            err_msg = f"error getting vectorizer: {type(e).__name__}: {str(e)}"  # noqa: E501
                            exception = await self._handle_error(
                                err_msg, vectorizer_id, worker_tracking
                            )
                            if self.exit_on_error:
                                return exception
                            break

                        logger.info("running vectorizer", vectorizer_id=vectorizer_id)

                        def should_continue(_: int, __: int) -> bool:
                            return not self.shutdown_requested.is_set()

                        await vectorizer.run(
                            db_url=self.db_url,
                            features=features,
                            worker_tracking=worker_tracking,
                            concurrency=self.concurrency,
                            should_continue_processing_hook=should_continue,
                        )
            except psycopg.OperationalError as e:
                if "connection failed" in str(e):
                    err_msg = f"unable to connect to database: {str(e)}"
                else:
                    err_msg = f"unexpected error: {str(e)}"
                exception = await self._handle_error(
                    err_msg, vectorizer_id, worker_tracking
                )
                if self.exit_on_error:
                    return exception
            except BaseExceptionGroup as e:  # type: ignore
                # catch any exceptions, log them, and keep on going
                for exception in e.exceptions:  # type: ignore
                    error_msg = str(exception)  # type: ignore
                    logger.error(error_msg, vectorizer_id=vectorizer_id)
                for exception_line in traceback.format_exception(e):  # type: ignore
                    for line in exception_line.rstrip().split("\n"):
                        logger.debug(line)
                err_msg = f"unexpected error: {str(e)}"  # type: ignore
                exception = await self._handle_error(
                    err_msg, vectorizer_id, worker_tracking
                )
                if self.exit_on_error:
                    return exception
            except Exception as e:
                # catch any exceptions, log them, and keep on going
                for exception_line in traceback.format_exception(e):
                    for line in exception_line.rstrip().split("\n"):
                        logger.debug(line)
                err_msg = f"unexpected error: {str(e)}"
                exception = await self._handle_error(
                    err_msg, vectorizer_id, worker_tracking
                )
                if self.exit_on_error:
                    return exception

            if self.once:
                if worker_tracking is not None:
                    await worker_tracking.force_last_heartbeat_and_stop()
                logger.info("once mode, exiting...")
                return None

            poll_interval_str = datetime.timedelta(seconds=self.poll_interval)
            logger.info(f"sleeping for {poll_interval_str} before polling for new work")
            try:
                await asyncio.wait_for(
                    self.shutdown_requested.wait(), timeout=self.poll_interval
                )
                # shutdown event was set, the loop should exit
                logger.info("got a graceful shutdown request")
            except asyncio.TimeoutError:
                # timeout means the sleep completed
                pass

        if worker_tracking is not None:
            await worker_tracking.force_last_heartbeat_and_stop()
        logger.info("exiting processor.run()")
        return None

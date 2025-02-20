import asyncio
import datetime

import psycopg
import structlog

from ..features import Features

log = structlog.get_logger()

class WorkerTracking:
    def __init__(
        self, db_url: str, poll_interval: int, features: Features, version: str
    ):
        self.db_url = db_url
        self.poll_interval = poll_interval
        self.worker_id = None
        self.num_errors_since_last_heartbeat = 0
        self.error_message = None
        self.enabled = features.worker_tracking
        self.version = version
        self.num_successes_since_last_heartbeat = 0

    async def start(self) -> None:
        if not self.enabled:
            return

        async with (
            await psycopg.AsyncConnection.connect(self.db_url, autocommit=True) as conn,
            conn.cursor() as cur,
            conn.transaction(),
        ):
            poll_interval_td = datetime.timedelta(seconds=self.poll_interval)
            await cur.execute(
                "select ai._worker_start(%s::text, %s::interval)",
                (self.version, poll_interval_td),
            )
            res = await cur.fetchone()
            self.worker_id = res[0]

    async def _report_error(self, error_message: str) -> None:
        self.num_errors_since_last_heartbeat += 1
        self.error_message = error_message

    async def force_heartbeat(self) -> None:
        if not self.enabled:
            return

        async with await psycopg.AsyncConnection.connect(
            self.db_url, autocommit=True
        ) as conn:
            await self._heartbeat(conn)

    async def _heartbeat(self, conn: psycopg.AsyncConnection) -> None:
        async with conn.cursor() as cur, conn.transaction():
            num_errors = self.num_errors_since_last_heartbeat
            self.num_errors_since_last_heartbeat = 0
            error_message = self.error_message
            self.error_message = None
            num_successes = self.num_successes_since_last_heartbeat
            self.num_successes_since_last_heartbeat = 0
            await cur.execute(
                "select ai._worker_heartbeat(%s, %s, %s, %s)",
                (self.worker_id, num_successes, num_errors, error_message),
            )

    async def heartbeat(self) -> None:
        if not self.enabled:
            return

        failures = 0
        while failures < 3:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self.db_url, autocommit=True
                ) as conn:
                    while True:
                        await self._heartbeat(conn)
                        # after a successful heartbeat, reset the failure count
                        failures = 0
                        await asyncio.sleep(self.poll_interval)
            except psycopg.OperationalError as e:
                failures += 1
                log.error("heartbeat failed", error=e)

    async def save_vectorizer_success(
        self,
        conn: psycopg.AsyncConnection,
        vectorizer_id: int,
        num_successes: int,
    ) -> None:
        if not self.enabled:
            return

        self.num_successes_since_last_heartbeat += num_successes

        async with conn.cursor() as cur, conn.transaction():
            await cur.execute(
                "select ai._worker_progress(%s, %s, %s, NULL)",
                (self.worker_id, vectorizer_id, num_successes),
            )

    async def save_vectorizer_error(
        self, vectorizer_id: int | None, error_message: str
    ) -> None:
        if not self.enabled:
            return

        await self._report_error(error_message)

        if vectorizer_id is None:
            return

        async with (
            await psycopg.AsyncConnection.connect(self.db_url, autocommit=True) as conn,
            conn.cursor() as cur,
            conn.transaction(),
        ):
            await cur.execute(
                "select ai._worker_progress(%s, %s, 0, %s)",
                (self.worker_id, vectorizer_id, error_message),
            )

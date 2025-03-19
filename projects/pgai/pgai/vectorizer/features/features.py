from functools import cached_property
from typing import TypeVar

import psycopg

Self = TypeVar("Self", bound="Features")


class Features:
    """Feature flags and version-dependent functionality manager."""

    def __init__(
        self, has_disabled_column: bool, has_worker_tracking_table: bool
    ) -> None:
        self.has_disabled_column = has_disabled_column
        self.has_worker_tracking_table = has_worker_tracking_table

    @classmethod
    def from_db(cls: type[Self], cur: psycopg.Cursor) -> Self:
        # for stuff that could be in extension or app,
        # explicitly check for db features instead of versions
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'ai'
              AND table_name = 'vectorizer'
              AND column_name = 'disabled';
        """
        cur.execute(query)
        has_disabled_column = cur.fetchone() is not None

        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'ai' AND table_name = 'vectorizer_worker_process';
        """
        cur.execute(query)
        has_worker_tracking_table = cur.fetchone() is not None

        return cls(has_disabled_column, has_worker_tracking_table)

    @classmethod
    def for_testing_latest_version(cls: type[Self]) -> Self:
        return cls(True, True)

    @classmethod
    def for_testing_no_features(cls: type[Self]) -> Self:
        return cls(False, False)

    @cached_property
    def disable_vectorizers(self) -> bool:
        """If the disable vectorizer feature is supported by the extension.

        The feature consists of a `disabled` column in the `ai.vectorizer`
        table, and the `ai.vectorizer_status` view.
        """
        return self.has_disabled_column

    @cached_property
    def worker_tracking(self) -> bool:
        """If the worker tracking feature is supported by the extension."""
        return self.has_worker_tracking_table

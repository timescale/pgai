from functools import cached_property

from packaging import version


class Features:
    """Feature flags and version-dependent functionality manager."""

    def __init__(self, ext_version: str) -> None:
        self.ext_version = version.parse(ext_version)

    @cached_property
    def disable_vectorizers(self) -> bool:
        """If the disable vectorizer feature is supported by the extension.

        The feature consists of a `disabled` column in the `ai.vectorizer`
        table, and the `ai.vectorizer_status` view.
        """
        return self.ext_version > version.parse("0.7.0")

    @cached_property
    def worker_tracking(self) -> bool:
        """If the worker tracking feature is supported by the extension."""
        return self.ext_version > version.parse("0.8.0")

    @cached_property
    def loading_retries(self) -> bool:
        """If the loading retries feature is supported by the extension.

        The feature includes changes in the way we fetch_work from the
        queueing tables, and also how we handle the retries.
        """
        return self.ext_version > version.parse("0.9.0")

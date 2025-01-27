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

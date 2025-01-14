from abc import ABC, abstractmethod
from functools import cached_property
from string import Template
from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import override


class Formatter(ABC):
    """
    Abstract base class for formatting chunks.

    Subclasses should implement the `format` method to define how a chunk of
    is formatted using a given item of data.
    """

    @abstractmethod
    def format(self, chunk: str, item: dict[str, Any]) -> str:
        pass


class ChunkValue(BaseModel, Formatter):
    """
    A formatter that returns the chunk value as-is without any modifications.

    Attributes:
        implementation (Literal["chunk_value"]): The literal identifier for
        this formatter.
    """

    implementation: Literal["chunk_value"]

    @override
    def format(self, chunk: str, item: dict[str, Any]) -> str:  # noqa
        """
        Returns the chunk of text without any formatting.

        Args:
            chunk (str): The chunk of text.
            item (dict[str, Any]): not used in this implementation.

        Returns:
            str: The original chunk of text.
        """
        return chunk


class PythonTemplate(BaseModel, Formatter):
    """
    A formatter that uses Python's string.Template to format chunks of text.

    The provided template can reference the chunk and any other fields in the `item`.

    Attributes:
        implementation (Literal["python_template"]): The literal identifier for
        this formatter. template (str): A template string used for formatting.
    """

    implementation: Literal["python_template"]
    template: str

    @override
    def format(self, chunk: str, item: dict[str, Any]) -> str:
        """
        Formats the chunk of text using the provided template and item data.

        Args:
            chunk (str): The chunk of text to be formatted.
            item (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data. Used for template substitution.

        Returns:
            str: The formatted string with template variables substituted.
        """
        return self._template.substitute(chunk=chunk, **item)

    @cached_property
    def _template(self) -> Template:
        return Template(self.template)

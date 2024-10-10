from abc import ABC, abstractmethod
from functools import cached_property
from string import Template
from typing import Any, Literal

from pydantic import BaseModel


class Formatter(ABC):
    @abstractmethod
    def format(self, chunk: str, item: dict[str, Any]) -> str:
        pass


class ChunkValue(BaseModel, Formatter):
    implementation: Literal["chunk_value"]

    def format(self, chunk: str, item: dict[str, Any]) -> str:  # noqa
        return chunk


class PythonTemplate(BaseModel, Formatter):
    implementation: Literal["python_template"]
    template: str

    def format(self, chunk: str, item: dict[str, Any]) -> str:
        return self._template.substitute(chunk=chunk, **item)

    @cached_property
    def _template(self) -> Template:
        return Template(self.template)

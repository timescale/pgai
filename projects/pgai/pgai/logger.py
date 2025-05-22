import json
from collections.abc import Callable
from typing import Any, TypeVar

from typing_extensions import override

T = TypeVar("T", bound="StructuredMessage")

# Type for the renderer function
RendererType = Callable[[str, dict[str, Any]], str]


class StructuredMessage:
    _renderer: RendererType | None = None

    def __init__(self, message: str, /, **kwargs: Any) -> None:
        self.message: str = message
        self.kwargs: dict[str, Any] = kwargs

    @override
    def __str__(self) -> str:
        renderer: RendererType = self._renderer or self.default_renderer
        return renderer(self.message, self.kwargs)

    @staticmethod
    def default_renderer(msg: str, kwargs: dict[str, Any]) -> str:
        return f"{msg} >>> {json.dumps(kwargs, default=str)}"

    @classmethod
    def set_renderer(cls: type[T], renderer_func: RendererType) -> None:
        cls._renderer = renderer_func


def set_renderer(renderer_func: RendererType) -> None:
    StructuredMessage.set_renderer(renderer_func)

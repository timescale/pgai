import json
import logging
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
        return f"{msg} >>> {json.dumps(kwargs)}"

    @classmethod
    def set_renderer(cls: type[T], renderer_func: RendererType) -> None:
        cls._renderer = renderer_func


def set_renderer(renderer_func: RendererType) -> None:
    StructuredMessage.set_renderer(renderer_func)


def get_logger(name: str = "") -> logging.Logger:
    """Get a logger instance with the pgai namespace.

    Args:
        name: The logger name, which will be prefixed with 'pgai.'

    Returns:
        A Logger instance with the appropriate namespace
    """
    if name:
        logger_name: str = f"pgai.{name}"
    else:
        logger_name: str = "pgai"

    return logging.getLogger(logger_name)


def set_level(level: int | str) -> None:
    """Set the log level for all pgai loggers.

    This does not affect the root logger or any other loggers outside
    the pgai namespace.

    Args:
        level: The logging level (e.g., logging.INFO, logging.DEBUG)
              or a string level name ('INFO', 'DEBUG', etc.)
    """
    if isinstance(level, str):
        numeric_level: int = getattr(logging, level.upper(), logging.INFO)
    else:
        numeric_level = level

    logging.getLogger("pgai").setLevel(numeric_level)

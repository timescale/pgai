from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from functools import cached_property
from string import Template
from typing import Any, Literal, Type, TypeVar, overload

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


# Type variable for Pydantic config models
F = TypeVar('F', bound=BaseModel)

# Type definition for formatting functions
FormatterFunc = Callable[
    [str, dict[str, Any], dict[str, Any]], str | Awaitable[str]
]

# Global registry for formatting functions and their config models
registered_formatters: dict[str, FormatterFunc] = dict()
formatter_config_models: dict[str, Type[BaseModel]] = dict()


@overload
def formatter(func: FormatterFunc) -> FormatterFunc: ...


@overload
def formatter(
    *, name: str | None = None, config_model: Type[F] | None = None
) -> Callable[[FormatterFunc], FormatterFunc]: ...


def formatter(
    func: FormatterFunc | None = None,
    *,  # enforce keyword-only arguments
    name: str | None = None,
    config_model: Type[BaseModel] | None = None,
) -> FormatterFunc | Callable[[FormatterFunc], FormatterFunc]:
    """
    Decorator to register formatting functions in the global registry.
    
    A formatting function takes a chunk, source item, and configuration and returns a formatted string.
    
    Example:
    ```python
    class MyFormatterConfig(FormatterConfig):
        template: str = "Title: ${title}\n\n${chunk}"
    
    @formatter(name="my_custom_formatter", config_model=MyFormatterConfig)
    def my_formatting_function(
        chunk: str, item: dict[str, Any], config: dict[str, Any]
    ) -> str:
        # Custom formatting logic
        return formatted_text
    ```
    """

    def decorator(f: FormatterFunc) -> FormatterFunc:
        registration_name = name if name is not None else f.__name__
        registered_formatters[registration_name] = f
        
        # Store the config model if provided
        if config_model is not None:
            formatter_config_models[registration_name] = config_model
            
        return f

    if func is not None:
        return decorator(func)

    return decorator


class ChunkValueConfig(BaseModel):
    """Configuration for chunk value formatter (no parameters needed)"""
    pass

@formatter(name="chunk_value", config_model=ChunkValueConfig)
def chunk_value_formatter(
    chunk: str, item: dict[str, Any], config: dict[str, Any]
) -> str:
    """
    Default implementation of the chunk value formatter using the decorator pattern.
    Simply returns the chunk as-is.
    """
    return chunk


class PythonTemplateConfig(BaseModel):
    """Configuration for Python template formatter"""
    template: str

@formatter(name="python_template", config_model=PythonTemplateConfig)
def python_template_formatter(
    chunk: str, item: dict[str, Any], config: dict[str, Any]
) -> str:
    """
    Default implementation of the Python template formatter using the decorator pattern.
    Uses string.Template to format the chunk with item data.
    """
    template_str = config["template"]
    template = Template(template_str)
    return template.substitute(chunk=chunk, **item)

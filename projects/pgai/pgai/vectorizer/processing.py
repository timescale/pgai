from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal, overload

from annotated_types import Gt, Le
from pydantic import BaseModel


class ProcessingDefault(BaseModel):
    """
    A model representing the default processing configuration.

    This model defines configuration parameters such as batch size,
    concurrency, and log level for a processing system.

    Attributes:
        implementation (Literal["default"]): The literal identifier for this
            implementation.
        batch_size (Annotated[int, Gt(gt=0), Le(le=2048)]): The
            size of batches to process, constrained to be greater than 0 and less
            than or equal to 2048. Default is 50.
        concurrency (Annotated[int, Gt(gt=0), Le(le=10)]): The number of
            concurrent tasks allowed, constrained to be greater than 0 and less
            than or equal to 10. Default is 1.
        log_level (Literal["CRITICAL", "FATAL", "ERROR", "WARN",
            "WARNING", "INFO", "DEBUG"]): The log level for logging output.
            Default is "INFO".
    """

    implementation: Literal["default"]
    batch_size: Annotated[int, Gt(gt=0), Le(le=2048)] = 50
    concurrency: Annotated[int, Gt(gt=0), Le(le=10)] = 1
    log_level: Literal[
        "CRITICAL",
        "FATAL",
        "ERROR",
        "WARN",
        "WARNING",
        "INFO",
        "DEBUG",
    ] = "INFO"


# Type definition for processor functions
ProcessorFunc = Callable[
    [dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]
]

# Global registry for processor functions
registered_processors: dict[str, ProcessorFunc] = dict()


@overload
def processor(func: ProcessorFunc) -> ProcessorFunc: ...


@overload
def processor(
    *, name: str | None = None
) -> Callable[[ProcessorFunc], ProcessorFunc]: ...


def processor(
    func: ProcessorFunc | None = None,
    *,  # enforce keyword-only arguments
    name: str | None = None,
) -> ProcessorFunc | Callable[[ProcessorFunc], ProcessorFunc]:
    """
    Decorator to register processor functions in the global registry.
    
    A processor function takes a configuration dictionary and returns a processed configuration.
    This allows for custom validation, transformation, or defaulting of configuration values.
    
    Example:
    ```python
    @processor(name="my_custom_processor")
    def my_processor_function(config: dict[str, Any]) -> dict[str, Any]:
        # Validate, transform, or add defaults to config
        return processed_config
    ```
    """

    def decorator(f: ProcessorFunc) -> ProcessorFunc:
        registration_name = name if name is not None else f.__name__
        registered_processors[registration_name] = f
        return f

    if func is not None:
        return decorator(func)

    return decorator


@processor(name="default")
def default_processor(config: dict[str, Any]) -> dict[str, Any]:
    """
    Default processor implementation using the decorator pattern.
    Validates and applies defaults to the processing configuration.
    """
    # Start with provided config or empty dict
    result = config.copy() if config else {}
    
    # Apply defaults if not provided
    if "batch_size" not in result:
        result["batch_size"] = 50
    
    if "concurrency" not in result:
        result["concurrency"] = 1
    
    if "log_level" not in result:
        result["log_level"] = "INFO"
    
    # Validate batch_size
    batch_size = result["batch_size"]
    if not isinstance(batch_size, int) or batch_size <= 0 or batch_size > 2048:
        raise ValueError("batch_size must be between 1 and 2048")
    
    # Validate concurrency
    concurrency = result["concurrency"]
    if not isinstance(concurrency, int) or concurrency <= 0 or concurrency > 10:
        raise ValueError("concurrency must be between 1 and 10")
    
    # Validate log_level
    valid_log_levels = [
        "CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"
    ]
    log_level = result["log_level"]
    if log_level not in valid_log_levels:
        raise ValueError(f"log_level must be one of {', '.join(valid_log_levels)}")
    
    return result

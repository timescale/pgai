from typing import Annotated, Literal

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

from typing import Annotated, Literal

from annotated_types import Gt, Le
from pydantic import BaseModel


class ProcessingDefault(BaseModel):
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

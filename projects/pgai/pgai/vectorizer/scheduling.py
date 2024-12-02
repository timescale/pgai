import datetime
from typing import Literal

from pydantic import BaseModel


class TimescaleScheduling(BaseModel):
    """
    TimescaleDB scheduling configuration.

    Attributes:
        interval: The interval at which to run the scheduling.
        retention_policy: The retention policy to use.
    """

    implementation: Literal["timescaledb"]
    schedule_interval: datetime.timedelta | None = None
    initial_start: str | None = None
    job_id: int | None = None
    fixed_schedule: bool
    timezone: str | None = None


class NoScheduling(BaseModel):
    """
    No scheduling configuration.
    """

    implementation: Literal["none"]

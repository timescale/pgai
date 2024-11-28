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
    schedule_interval: datetime.timedelta
    initial_start: str
    job_id: int
    fixed_schedule: bool
    timezone: str

class NoScheduling(BaseModel):
    """
    No scheduling configuration.
    """
    
    implementation: Literal["none"]
from typing import Literal

from pydantic import BaseModel


class TimescaleScheduling(BaseModel):
    """
    TimescaleDB scheduling configuration.

    Attributes:
        interval: The interval at which to run the scheduling.
        retention_policy: The retention policy to use.
    """
    
    implementation: Literal["timescale"]
    schedule_interval: str
    initial_start: str
    fixed_schedule: bool
    timezone: str

class NoScheduling(BaseModel):
    """
    No scheduling configuration.
    """
    
    implementation: Literal["none"]
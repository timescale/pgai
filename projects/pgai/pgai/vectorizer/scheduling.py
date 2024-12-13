from typing import Literal

from pydantic import BaseModel

from pgai.vectorizer.base import BaseTimescaleScheduling


class TimescaleScheduling(BaseTimescaleScheduling):
    """
    TimescaleDB scheduling configuration.

    Attributes:
        interval: The interval at which to run the scheduling.
        retention_policy: The retention policy to use.
    """

    implementation: Literal["timescaledb"]


class NoScheduling(BaseModel):
    """
    No scheduling configuration.
    """

    implementation: Literal["none"]

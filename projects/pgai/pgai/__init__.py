__version__ = "0.10.2"

from pgai._install.install import ainstall, install
from pgai.logger import get_logger, set_level

from .tracing import configure_tracing

configure_tracing()

__all__ = ["ainstall", "install", "get_logger", "set_level"]

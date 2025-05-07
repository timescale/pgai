__version__ = "0.10.2"

from pgai._install.install import ainstall, install

from .tracing import configure_tracing

configure_tracing()

__all__ = ["ainstall", "install"]

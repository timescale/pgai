import os

from ddtrace.trace import tracer


def configure_tracing():
    # Disable tracer by default
    if os.getenv("DD_TRACE_ENABLED", "false").lower() == "true":
        tracer.enabled = True
    else:
        tracer.enabled = False

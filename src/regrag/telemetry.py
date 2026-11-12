"""OpenTelemetry tracing exported to Application Insights.

Spans carry backend, counts, scores, support labels, token usage and latency. The
question text is not recorded unless REGRAG_LOG_QUESTIONS=true.
"""
from contextlib import contextmanager

from opentelemetry import trace

from regrag.config import Settings

_configured = False
tracer = trace.get_tracer("regrag")


def configure(settings: Settings) -> bool:
    """Enable Azure Monitor export when a connection string is configured."""
    global _configured
    if _configured or not settings.appinsights_connection_string:
        return _configured
    from azure.monitor.opentelemetry import configure_azure_monitor

    from regrag.azure_clients import credential
    # Local authentication is disabled on the Application Insights resource, so
    # telemetry is sent with the managed identity (Monitoring Metrics Publisher).
    configure_azure_monitor(connection_string=settings.appinsights_connection_string,
                            credential=credential(), logger_name="regrag",
                            enable_live_metrics=False)
    _configured = True
    return True


@contextmanager
def span(name: str, **attributes):
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(f"regrag.{key}", value)
        yield current

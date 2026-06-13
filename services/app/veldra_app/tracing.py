"""OpenTelemetry GenAI tracing, wired from day one (export is optional).

If OTEL_EXPORTER_OTLP_ENDPOINT is set, spans are exported over OTLP/HTTP;
otherwise a tracer provider is still installed so spans are created (and visible
to any in-process processor) without requiring a collector.
"""

from __future__ import annotations

import functools

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from veldra_app.config import get_settings

_initialized = False


def setup_tracing() -> None:
    global _initialized
    if _initialized:
        return
    s = get_settings()
    provider = TracerProvider(resource=Resource.create({"service.name": s.otel_service_name}))
    if s.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=s.otel_exporter_otlp_endpoint))
        )
    trace.set_tracer_provider(provider)
    _initialized = True


@functools.lru_cache
def get_tracer():
    setup_tracing()
    return trace.get_tracer("veldra")

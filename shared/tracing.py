import os
from opentelemetry import trace, propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

try:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
except ImportError:
    RequestsInstrumentor = None

try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
except Exception:
    HTTPXClientInstrumentor = None

try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
except Exception:
    SQLAlchemyInstrumentor = None

try:
    from opentelemetry.instrumentation.pika import PikaInstrumentor
except Exception:
    PikaInstrumentor = None

from opentelemetry.sdk.resources import SERVICE_NAME, Resource

def init_tracing(service_name: str):
    """Initialize OpenTelemetry tracing for a service using OTLP exporter."""
    
    # Create resource with service name
    resource = Resource.create({SERVICE_NAME: service_name})
    
    # Create OTLP exporter pointing to OpenTelemetry Collector
    # This allows all services and Traefik to send traces to the same collector
    # Using longer timeout to allow for collector startup
    otlp_exporter = OTLPSpanExporter(
        endpoint="otel-collector:4317",
        insecure=True,
        timeout=30,  # 30 second timeout for collector startup
    )
    
    # Create tracer provider and add batch processor
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set the global tracer provider
    trace.set_tracer_provider(trace_provider)
    
    # Set propagator to W3C Trace Context standard
    # This ensures compatibility with Traefik and other services
    propagate.set_global_textmap(TraceContextTextMapPropagator())


def instrument_app(app):
    """Instrument FastAPI app and HTTP clients for distributed tracing."""
    # FastAPIInstrumentor will use the global propagator to:
    # 1. Extract trace context from incoming request headers
    # 2. Create spans for incoming requests
    FastAPIInstrumentor.instrument_app(app)

    # Instrument outgoing HTTP requests to propagate trace context
    if RequestsInstrumentor is not None:
        try:
            RequestsInstrumentor().instrument()
        except Exception:
            pass
    
    if HTTPXClientInstrumentor is not None:
        try:
            HTTPXClientInstrumentor().instrument()
        except Exception:
            pass

    if SQLAlchemyInstrumentor is not None:
        try:
            SQLAlchemyInstrumentor().instrument()
        except Exception:
            pass
    
    # Instrument RabbitMQ for message-based tracing (consumer/producer)
    if PikaInstrumentor is not None:
        try:
            PikaInstrumentor().instrument()
        except Exception:
            pass

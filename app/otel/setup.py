"""Bootstrap OpenTelemetry TracerProvider and MeterProvider."""

import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import Settings

logger = logging.getLogger(__name__)


def build_resource(settings: Settings) -> Resource:
    return Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: settings.otel_service_version,
            "deployment.environment": "demo",
            "db.system": "oracle",
        }
    )


def setup_tracing(settings: Settings) -> TracerProvider:
    resource = build_resource(settings)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logger.info("TracerProvider configured → %s", settings.otel_exporter_otlp_endpoint)
    return provider


def setup_metrics(settings: Settings) -> MeterProvider:
    resource = build_resource(settings)
    exporter = OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5_000)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    logger.info("MeterProvider configured (5s interval) → %s", settings.otel_exporter_otlp_endpoint)
    return provider


def setup_telemetry(settings: Settings) -> tuple[TracerProvider, MeterProvider]:
    tracer_provider = setup_tracing(settings)
    meter_provider = setup_metrics(settings)
    return tracer_provider, meter_provider


def shutdown_telemetry(tracer_provider: TracerProvider, meter_provider: MeterProvider) -> None:
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger.info("OTel providers shut down cleanly")

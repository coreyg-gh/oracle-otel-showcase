"""Shared pytest fixtures.

All tests run without a live Oracle database or OTel Collector.
Connections and exporters are fully mocked.
"""

import array
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


@pytest.fixture(scope="session", autouse=True)
def in_memory_otel():
    """Configure in-memory OTel providers for the test session."""
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    yield {"spans": span_exporter, "metrics": metric_reader}

    tracer_provider.shutdown()
    meter_provider.shutdown()


@pytest.fixture
def mock_connection():
    """A mock oracledb connection with a working cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone = MagicMock(return_value=(1,))
    cursor.fetchall = MagicMock(return_value=[])
    conn.cursor = MagicMock(return_value=cursor)
    conn.commit = MagicMock()
    return conn, cursor


@pytest.fixture
def sample_embedding():
    """A unit-normalised float32 numpy vector (small dims for speed)."""
    vec = np.random.randn(8).astype(np.float32)
    return vec / np.linalg.norm(vec)

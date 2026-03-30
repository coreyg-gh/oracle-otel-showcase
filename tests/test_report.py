"""Unit tests for the report generator (Prometheus + Tempo HTTP mocked)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses as responses_lib


# ── PrometheusClient ────────────────────────────────────────────────────────

@responses_lib.activate
def test_prometheus_client_query_instant_success():
    from report.prometheus_client import PrometheusClient

    responses_lib.add(
        responses_lib.GET,
        "http://prometheus:9090/api/v1/query",
        json={
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {"metric": {"operation": "insert"}, "value": [1700000000, "42.5"]}
                ],
            },
        },
    )

    client = PrometheusClient("http://prometheus:9090")
    result = client.query_instant("oracle_otel_oracle_db_operations_total")

    assert len(result) == 1
    assert result[0]["metric"]["operation"] == "insert"


@responses_lib.activate
def test_prometheus_client_scalar_value_returns_float():
    from report.prometheus_client import PrometheusClient

    responses_lib.add(
        responses_lib.GET,
        "http://prometheus:9090/api/v1/query",
        json={
            "status": "success",
            "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1700000000, "99.9"]}]},
        },
    )

    client = PrometheusClient("http://prometheus:9090")
    value = client.scalar_value("some_metric")

    assert isinstance(value, float)
    assert abs(value - 99.9) < 0.001


@responses_lib.activate
def test_prometheus_client_scalar_value_default_on_empty():
    from report.prometheus_client import PrometheusClient

    responses_lib.add(
        responses_lib.GET,
        "http://prometheus:9090/api/v1/query",
        json={"status": "success", "data": {"resultType": "vector", "result": []}},
    )

    client = PrometheusClient("http://prometheus:9090")
    value = client.scalar_value("empty_metric", default=7.7)

    assert abs(value - 7.7) < 0.001


# ── TempoClient ─────────────────────────────────────────────────────────────

@responses_lib.activate
def test_tempo_client_search_returns_traces():
    from report.tempo_client import TempoClient

    responses_lib.add(
        responses_lib.GET,
        "http://tempo:3200/api/search",
        json={
            "traces": [
                {
                    "traceID": "abc123def456789012345678901234567890",
                    "rootSpanName": "crud.cycle",
                    "durationMs": 150,
                    "spanCount": 5,
                }
            ]
        },
    )

    client = TempoClient("http://tempo:3200")
    traces = client.search(
        "oracle-otel-showcase",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert len(traces) == 1
    assert traces[0]["rootSpanName"] == "crud.cycle"


@responses_lib.activate
def test_tempo_client_search_returns_empty_on_error():
    from report.tempo_client import TempoClient

    responses_lib.add(
        responses_lib.GET,
        "http://tempo:3200/api/search",
        status=500,
    )

    client = TempoClient("http://tempo:3200")
    traces = client.search(
        "oracle-otel-showcase",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert traces == []


# ── Report generator ────────────────────────────────────────────────────────

@responses_lib.activate
def test_generate_report_creates_html_and_md(tmp_path):
    """Full generator integration test with all HTTP calls mocked."""
    from report import generator as gen

    # Mock all Prometheus instant queries
    instant_response = {
        "status": "success",
        "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1700000000, "100"]}]},
    }
    ops_response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"operation": "insert"}, "value": [1700000000, "30"]},
                {"metric": {"operation": "select"}, "value": [1700000000, "40"]},
            ],
        },
    }
    range_response = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"operation": "insert"},
                    "values": [[1700000000, "5.0"], [1700000060, "6.5"]],
                }
            ],
        },
    }
    tempo_response = {
        "traces": [
            {
                "traceID": "aaabbbccc111222333444555666777888999",
                "rootSpanName": "crud.cycle",
                "durationMs": 250,
                "spanCount": 4,
            }
        ]
    }

    # Register all expected HTTP calls
    prom_url = "http://prometheus:9090"
    tempo_url = "http://tempo:3200"

    for _ in range(10):  # instant queries
        responses_lib.add(responses_lib.GET, f"{prom_url}/api/v1/query", json=instant_response)
    responses_lib.add(responses_lib.GET, f"{prom_url}/api/v1/query", json=ops_response)
    responses_lib.add(responses_lib.GET, f"{prom_url}/api/v1/query_range", json=range_response)
    responses_lib.add(responses_lib.GET, f"{tempo_url}/api/search", json=tempo_response)

    with (
        patch("app.config.settings.prometheus_url", prom_url),
        patch("app.config.settings.tempo_url", tempo_url),
        patch("app.config.settings.otel_service_name", "oracle-otel-showcase"),
    ):
        html_file = gen.generate_report(output_dir=str(tmp_path), lookback_minutes=5)

    assert html_file.exists()
    assert html_file.suffix == ".html"
    html_content = html_file.read_text()
    assert "Oracle OpenTelemetry Showcase" in html_content
    assert "oracle-otel-showcase" in html_content

    # Markdown file should also exist
    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    md_content = md_files[0].read_text()
    assert "Oracle OpenTelemetry Showcase" in md_content

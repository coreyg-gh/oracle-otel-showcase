"""Report generator — queries Prometheus and Tempo and renders HTML + Markdown.

Usage:
    python -m report.generator

Or via Docker Compose:
    docker compose --profile report up report-generator
"""

import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jinja2

from app.config import settings
from report.prometheus_client import PrometheusClient
from report.tempo_client import TempoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus metric name prefix produced by OTel Collector's `namespace: oracle_otel`
_NS = "oracle_otel"

PROMQL = {
    "total_operations": f"sum(increase({_NS}_oracle_db_operations_total[{{lookback}}m]))",
    "total_errors": f"sum(increase({_NS}_oracle_db_errors_total[{{lookback}}m]))",
    "error_rate_pct": (
        f"sum(rate({_NS}_oracle_db_errors_total[{{lookback}}m])) "
        f"/ sum(rate({_NS}_oracle_db_operations_total[{{lookback}}m])) * 100"
    ),
    "query_p50_all": (
        f"histogram_quantile(0.50, sum(rate({_NS}_oracle_query_duration_milliseconds_bucket[{{lookback}}m])) by (le))"
    ),
    "query_p95_all": (
        f"histogram_quantile(0.95, sum(rate({_NS}_oracle_query_duration_milliseconds_bucket[{{lookback}}m])) by (le))"
    ),
    "query_p99_all": (
        f"histogram_quantile(0.99, sum(rate({_NS}_oracle_query_duration_milliseconds_bucket[{{lookback}}m])) by (le))"
    ),
    "operations_by_type": f"sum by (operation) (increase({_NS}_oracle_db_operations_total[{{lookback}}m]))",
    "pool_max_busy": f"max_over_time({_NS}_oracle_pool_busy_connections[{{lookback}}m])",
    "avg_vector_similarity": (
        f"histogram_quantile(0.50, sum(rate({_NS}_oracle_vector_similarity_score_bucket[{{lookback}}m])) by (le))"
    ),
    # Range query for chart (p95 over time)
    "query_p95_range": (
        f"histogram_quantile(0.95, sum(rate({_NS}_oracle_query_duration_milliseconds_bucket[1m])) by (le, operation))"
    ),
}


def _fmt(query_template: str, lookback: int) -> str:
    return query_template.format(lookback=lookback)


def collect_metrics(prom: PrometheusClient, lookback: int) -> dict:
    """Fetch all instant metric values from Prometheus."""
    return {
        "total_operations": prom.scalar_value(_fmt(PROMQL["total_operations"], lookback)),
        "total_errors": prom.scalar_value(_fmt(PROMQL["total_errors"], lookback)),
        "error_rate_pct": prom.scalar_value(_fmt(PROMQL["error_rate_pct"], lookback)),
        "query_p50_ms": prom.scalar_value(_fmt(PROMQL["query_p50_all"], lookback)),
        "query_p95_ms": prom.scalar_value(_fmt(PROMQL["query_p95_all"], lookback)),
        "query_p99_ms": prom.scalar_value(_fmt(PROMQL["query_p99_all"], lookback)),
        "pool_max_busy": prom.scalar_value(_fmt(PROMQL["pool_max_busy"], lookback)),
        "avg_vector_similarity": prom.scalar_value(_fmt(PROMQL["avg_vector_similarity"], lookback)),
        "operations_by_type": prom.query_instant(_fmt(PROMQL["operations_by_type"], lookback)),
    }


def collect_latency_range(prom: PrometheusClient, start: datetime, end: datetime) -> list[dict]:
    """Fetch p95 query latency time series for the chart."""
    return prom.query_range(PROMQL["query_p95_range"], start, end, step="30s")


def collect_slow_traces(tempo: TempoClient, start: datetime, end: datetime) -> list[dict]:
    """Fetch the 10 slowest traces for the service."""
    return tempo.search_traceql(
        '{resource.service.name="oracle-otel-showcase" && duration > 50ms}',
        start,
        end,
        limit=10,
    )


def _format_duration_ms(ns: str | int | float | None) -> str:
    """Format Tempo trace duration (nanoseconds string) to human-readable ms."""
    try:
        ns_val = int(ns)
        return f"{ns_val / 1_000_000:.1f} ms"
    except (TypeError, ValueError):
        return "—"


def generate_report(output_dir: str | None = None, lookback_minutes: int | None = None) -> Path:
    output_dir = output_dir or settings.report_output_dir
    lookback = lookback_minutes or settings.report_lookback_minutes

    end = datetime.now(UTC)
    start = end - timedelta(minutes=lookback)

    logger.info(
        "Generating report: last %d minutes (%s → %s)", lookback, start.isoformat(), end.isoformat()
    )

    prom = PrometheusClient(settings.prometheus_url)
    tempo = TempoClient(settings.tempo_url)

    metrics_data = collect_metrics(prom, lookback)
    latency_range = collect_latency_range(prom, start, end)
    slow_traces = collect_slow_traces(tempo, start, end)

    # Build Chart.js-friendly time series data
    chart_datasets = []
    for series in latency_range:
        op = series.get("metric", {}).get("operation", "all")
        points = [{"x": int(v[0]) * 1000, "y": round(float(v[1]), 2)} for v in series["values"]]
        chart_datasets.append({"label": op, "data": points})

    # Flatten operations_by_type into a simple dict
    ops_by_type = {}
    for item in metrics_data.get("operations_by_type", []):
        op_name = item.get("metric", {}).get("operation", "unknown")
        try:
            ops_by_type[op_name] = round(float(item["value"][1]))
        except (KeyError, ValueError, IndexError):
            pass

    template_context = {
        "generated_at": end.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "lookback_minutes": lookback,
        "service_name": settings.otel_service_name,
        "metrics": metrics_data,
        "ops_by_type": ops_by_type,
        "chart_datasets": chart_datasets,
        "slow_traces": slow_traces,
        "format_duration_ms": _format_duration_ms,
    }

    templates_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)), autoescape=True)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    timestamp = end.strftime("%Y%m%dT%H%M%S")

    # HTML report
    html_template = env.get_template("report.html.j2")
    html_content = html_template.render(**template_context)
    html_file = out_path / f"report_{timestamp}.html"
    html_file.write_text(html_content, encoding="utf-8")
    logger.info("HTML report written → %s", html_file)

    # Markdown report (autoescape off for MD)
    md_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)), autoescape=False
    )
    md_template = md_env.get_template("report.md.j2")
    md_content = md_template.render(**template_context)
    md_file = out_path / f"report_{timestamp}.md"
    md_file.write_text(md_content, encoding="utf-8")
    logger.info("Markdown report written → %s", md_file)

    return html_file


if __name__ == "__main__":
    output_file = generate_report()
    print(f"Report generated: {output_file}", file=sys.stdout)

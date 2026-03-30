"""Custom OTel metric instruments for Oracle observability."""

from opentelemetry import metrics

_meter = metrics.get_meter("oracle.otel.showcase", version="1.0.0")

# Connection pool gauges — updated via observable callbacks registered at startup
pool_size_gauge = _meter.create_observable_gauge(
    name="oracle.pool.size",
    description="Total connections in the Oracle connection pool",
    unit="connections",
)
pool_busy_gauge = _meter.create_observable_gauge(
    name="oracle.pool.busy",
    description="Oracle pool connections currently in use",
    unit="connections",
)
pool_wait_gauge = _meter.create_observable_gauge(
    name="oracle.pool.wait_count",
    description="Sessions waiting to acquire a connection from the pool",
    unit="sessions",
)

# Query latency histogram — labeled by `operation`
query_duration_histogram = _meter.create_histogram(
    name="oracle.query.duration",
    description="Execution time of Oracle database queries",
    unit="ms",
)

# Vector search similarity — labeled by `distance_metric`
vector_similarity_histogram = _meter.create_histogram(
    name="oracle.vector.similarity_score",
    description="Cosine similarity score returned by Oracle Vector Search (0=orthogonal, 1=identical)",
    unit="1",
)

# Error and operation counters
db_error_counter = _meter.create_counter(
    name="oracle.db.errors",
    description="Count of Oracle database errors by error type",
    unit="errors",
)
db_operation_counter = _meter.create_counter(
    name="oracle.db.operations",
    description="Count of Oracle database operations by type",
    unit="operations",
)

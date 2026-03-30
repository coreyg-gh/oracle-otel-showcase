"""Oracle connection pool factory with OTel observable gauge callbacks."""

import logging

import oracledb
from opentelemetry import metrics
from opentelemetry.sdk.trace import TracerProvider

from app.config import Settings
from app.otel import metrics as otel_metrics

logger = logging.getLogger(__name__)

_meter = metrics.get_meter("oracle.otel.showcase.pool")


def create_pool(settings: Settings) -> oracledb.ConnectionPool:
    """Create a python-oracledb connection pool in thin mode."""
    dsn = f"{settings.oracle_host}:{settings.oracle_port}/{settings.oracle_service}"
    pool = oracledb.create_pool(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=dsn,
        min=settings.oracle_pool_min,
        max=settings.oracle_pool_max,
        increment=settings.oracle_pool_increment,
    )
    logger.info("Connection pool created: %s (min=%d max=%d)", dsn, settings.oracle_pool_min, settings.oracle_pool_max)
    return pool


def register_pool_callbacks(pool: oracledb.ConnectionPool) -> None:
    """Register OTel observable gauge callbacks that read live pool statistics."""

    def _observe_pool_size(options):
        try:
            yield metrics.Observation(pool.opened)
        except Exception:
            pass

    def _observe_pool_busy(options):
        try:
            yield metrics.Observation(pool.busy)
        except Exception:
            pass

    def _observe_pool_wait(options):
        try:
            # python-oracledb does not expose a wait count directly;
            # approximate as max(0, busy - opened) when pool is saturated
            wait = max(0, pool.busy - pool.opened) if pool.opened > 0 else 0
            yield metrics.Observation(wait)
        except Exception:
            pass

    otel_metrics.create_pool_gauges(_observe_pool_size, _observe_pool_busy, _observe_pool_wait)
    logger.info("Pool observable gauge callbacks registered")


def acquire_instrumented(
    pool: oracledb.ConnectionPool,
    tracer_provider: TracerProvider,
) -> oracledb.Connection:
    """Acquire a pool connection and wrap it with OTel DBAPI instrumentation."""
    from app.otel.dbapi_patch import instrument_connection

    raw = pool.acquire()
    return instrument_connection(raw, tracer_provider)

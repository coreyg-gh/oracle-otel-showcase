"""Periodic connection pool stats logger.

The OTel observable gauge callbacks on the pool already export metrics
automatically. This module provides an additional human-readable log summary
and a SELECT workload that exercises multiple concurrent connections to
demonstrate pool behaviour under load.
"""

import logging

import oracledb
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("oracle.workload.pool", tracer_provider=None)


def log_pool_stats(pool: oracledb.ConnectionPool) -> None:
    """Log a snapshot of current pool statistics."""
    logger.info(
        "Pool stats — opened: %d, busy: %d, max: %d",
        pool.opened,
        pool.busy,
        pool.max,
    )


def run_concurrent_selects(pool: oracledb.ConnectionPool, count: int = 3) -> None:
    """Borrow *count* connections simultaneously to show pool pressure in metrics."""
    with tracer.start_as_current_span("pool.concurrent_selects") as span:
        span.set_attribute("pool.concurrent_count", count)
        connections = []
        try:
            for _ in range(count):
                conn = pool.acquire()
                connections.append(conn)
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM products")
                    cur.fetchone()
        except oracledb.DatabaseError as exc:
            span.record_exception(exc)
            logger.warning("Pool concurrent select failed: %s", exc)
        finally:
            for conn in connections:
                try:
                    pool.release(conn)
                except Exception:
                    pass

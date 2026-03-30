"""Application entry point.

1. Bootstrap OTel (TracerProvider + MeterProvider → OTel Collector)
2. Wait for Oracle to become available with retry backoff
3. Initialise database schema + seed data
4. Start async workload loops (CRUD, vector search, pool monitor)
"""

import asyncio
import logging
import signal
import sys

from app.config import settings
from app.database.connection import create_pool, register_pool_callbacks
from app.database.schema import initialise_schema
from app.otel.setup import setup_telemetry, shutdown_telemetry
from app.utils.retry import retry_on_oracle_startup
from app.workloads.runner import run_all_workloads
from app.workloads.vector_search import seed_embeddings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _create_pool_with_retry():
    return retry_on_oracle_startup(lambda: create_pool(settings))


async def main() -> None:
    logger.info("=== Oracle OpenTelemetry Showcase starting ===")

    # --- OTel bootstrap ---
    tracer_provider, meter_provider = setup_telemetry(settings)

    # --- Oracle pool (with retry for slow container startup) ---
    logger.info(
        "Connecting to Oracle %s:%d/%s...",
        settings.oracle_host,
        settings.oracle_port,
        settings.oracle_service,
    )
    pool = await asyncio.get_event_loop().run_in_executor(None, _create_pool_with_retry)
    register_pool_callbacks(pool)

    # --- Schema init ---
    logger.info("Initialising schema...")
    await asyncio.get_event_loop().run_in_executor(
        None,
        initialise_schema,
        settings,
        lambda conn, s: seed_embeddings(conn, s),
    )

    # --- Graceful shutdown ---
    loop = asyncio.get_event_loop()

    def _shutdown(sig):
        logger.info("Received %s — shutting down...", sig.name)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    # --- Run workloads ---
    logger.info("Workload runner starting. Open http://localhost:3000 to view Grafana.")
    try:
        await run_all_workloads(pool, tracer_provider, settings)
    except asyncio.CancelledError:
        logger.info("Workloads cancelled — cleaning up")
    finally:
        pool.close()
        shutdown_telemetry(tracer_provider, meter_provider)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

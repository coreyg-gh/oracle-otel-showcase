"""Async workload orchestrator.

Runs CRUD, vector search, and pool monitor workloads in continuous loops.
DB calls are dispatched to a thread-pool executor so the OTel DBAPI
instrumentation (which wraps synchronous cursors) works correctly.
"""

import asyncio
import logging

import oracledb
from opentelemetry.sdk.trace import TracerProvider

from app.config import Settings
from app.database.connection import acquire_instrumented
from app.workloads import crud, pool_monitor, vector_search

logger = logging.getLogger(__name__)


async def _run_in_executor(loop, fn, *args):
    return await loop.run_in_executor(None, fn, *args)


async def crud_loop(
    pool: oracledb.ConnectionPool,
    tracer_provider: TracerProvider,
    settings: Settings,
) -> None:
    loop = asyncio.get_event_loop()
    while True:
        try:
            conn = await loop.run_in_executor(None, acquire_instrumented, pool, tracer_provider)
            try:
                await loop.run_in_executor(None, crud.run_crud_cycle, conn)
            finally:
                await loop.run_in_executor(None, pool.release, conn._dbapi_connection)
        except Exception:
            logger.exception("CRUD loop error")
        await asyncio.sleep(settings.workload_interval_seconds)


async def vector_search_loop(
    pool: oracledb.ConnectionPool,
    tracer_provider: TracerProvider,
    settings: Settings,
) -> None:
    loop = asyncio.get_event_loop()
    while True:
        try:
            conn = await loop.run_in_executor(None, acquire_instrumented, pool, tracer_provider)
            try:
                await loop.run_in_executor(
                    None,
                    vector_search.run_vector_search_cycle,
                    conn,
                    settings.vector_dimensions,
                )
                # Occasionally insert a new vector
                if asyncio.get_event_loop().time() % 10 < settings.workload_interval_seconds:
                    await loop.run_in_executor(
                        None,
                        vector_search.run_vector_insert_cycle,
                        conn,
                        settings.vector_dimensions,
                    )
            finally:
                await loop.run_in_executor(None, pool.release, conn._dbapi_connection)
        except Exception:
            logger.exception("Vector search loop error")
        await asyncio.sleep(settings.workload_interval_seconds * 1.5)


async def pool_monitor_loop(
    pool: oracledb.ConnectionPool,
    settings: Settings,
) -> None:
    while True:
        try:
            pool_monitor.log_pool_stats(pool)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, pool_monitor.run_concurrent_selects, pool, 3)
        except Exception:
            logger.exception("Pool monitor loop error")
        await asyncio.sleep(10.0)


async def run_all_workloads(
    pool: oracledb.ConnectionPool,
    tracer_provider: TracerProvider,
    settings: Settings,
) -> None:
    logger.info("Starting all workloads (interval=%.1fs)...", settings.workload_interval_seconds)
    await asyncio.gather(
        crud_loop(pool, tracer_provider, settings),
        vector_search_loop(pool, tracer_provider, settings),
        pool_monitor_loop(pool, settings),
    )

"""Exponential backoff retry for Oracle startup connectivity."""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import oracledb

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Oracle error codes that indicate the database is not yet ready
_TRANSIENT_ORA_CODES = {
    12514,  # TNS: listener does not know of service requested in connect descriptor
    12541,  # TNS: no listener
    12528,  # TNS: listener: all appropriate instances are blocking new connections
    12537,  # TNS: connection closed
    1033,   # Oracle initialization or shutdown in progress
    1034,   # Oracle not available
}


def _is_transient(exc: oracledb.DatabaseError) -> bool:
    try:
        (error,) = exc.args
        return error.code in _TRANSIENT_ORA_CODES
    except Exception:
        return False


def retry_on_oracle_startup(
    fn: Callable[[], T],
    max_attempts: int = 30,
    initial_delay: float = 5.0,
    backoff_factor: float = 1.2,
    max_delay: float = 30.0,
) -> T:
    """Call *fn* repeatedly until it succeeds or max_attempts is exhausted.

    Retries on transient Oracle startup errors (ORA-12514, ORA-12541, etc.)
    with exponential backoff.
    """
    delay = initial_delay
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except oracledb.DatabaseError as exc:
            if _is_transient(exc) and attempt < max_attempts:
                logger.info(
                    "Oracle not ready (attempt %d/%d, %s) — retrying in %.0fs...",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                raise
    raise RuntimeError("Exhausted retry attempts waiting for Oracle")

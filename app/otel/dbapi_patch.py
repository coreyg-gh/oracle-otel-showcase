"""Wrap a python-oracledb connection with OTel DBAPI instrumentation.

opentelemetry-instrumentation-dbapi traces every cursor.execute() call,
producing child spans with db.system, db.statement, and db.name attributes.
"""

import logging

import oracledb
from opentelemetry.instrumentation.dbapi import DatabaseApiIntegration
from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)

# Attribute names on oracledb connection objects that map to OTel semantic conventions
_CONNECTION_ATTRIBUTES = {
    "database": "db_name",  # accessed via connection.db_name property
    "host": "host",
    "port": "port",
    "user": "username",
}


def instrument_connection(
    raw_connection: oracledb.Connection,
    tracer_provider: TracerProvider,
) -> oracledb.Connection:
    """Return a traced wrapper around *raw_connection*.

    The wrapper intercepts cursor.execute / executemany and emits OTel spans.
    The original connection object must still be used for pool.release().
    """
    integration = DatabaseApiIntegration(
        name="oracle-otel-showcase",
        database_system="oracle",
        connection_attributes=_CONNECTION_ATTRIBUTES,
        tracer_provider=tracer_provider,
        capture_parameters=False,
    )

    # DatabaseApiIntegration.wrapped_connection expects a callable that returns
    # the already-open connection, so we pass a lambda.
    try:
        wrapped = integration.wrapped_connection(
            connect_method=lambda *a, **k: raw_connection,
            args=(),
            kwargs={},
        )
        return wrapped
    except Exception:
        logger.warning(
            "Failed to instrument connection — using uninstrumented connection", exc_info=True
        )
        return raw_connection

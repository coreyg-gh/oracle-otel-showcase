"""Unit tests for CRUD workload (no live Oracle)."""

from unittest.mock import MagicMock


def test_random_product_name_format():
    from app.workloads.crud import _random_product_name

    name = _random_product_name()
    parts = name.split(" ")
    assert len(parts) == 3, f"Expected 3 parts, got: {name!r}"
    # Last part should be a 3-digit number
    assert parts[2].isdigit()
    assert 100 <= int(parts[2]) <= 999


def test_run_crud_cycle_calls_all_operations(mock_connection):
    conn, cursor = mock_connection

    # Simulate RETURNING id INTO :out_id bind variable
    out_id_var = MagicMock()
    out_id_var.getvalue.return_value = [42]
    cursor.bindvars = {"out_id": out_id_var}
    cursor.var = MagicMock(return_value=out_id_var)

    from app.workloads.crud import run_crud_cycle

    run_crud_cycle(conn)

    # cursor.execute should have been called at least 4 times (INSERT, SELECT, UPDATE, DELETE)
    assert cursor.execute.call_count >= 4


def test_crud_handles_db_error_gracefully(mock_connection):
    conn, cursor = mock_connection
    cursor.execute.side_effect = Exception("Simulated DB error")

    from app.workloads.crud import run_crud_cycle

    # Should not raise — errors are caught and recorded to metrics
    run_crud_cycle(conn)

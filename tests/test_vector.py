"""Unit tests for Oracle AI Vector Search workload."""

import array

import numpy as np


def test_generate_embedding_is_unit_normalised():
    from app.workloads.vector_search import generate_embedding

    vec = generate_embedding(dimensions=64)
    assert vec.shape == (64,)
    assert vec.dtype == np.float32
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"


def test_numpy_to_oracle_vector_returns_array_array():
    from app.workloads.vector_search import numpy_to_oracle_vector

    vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    result = numpy_to_oracle_vector(vec)

    assert isinstance(result, array.array), "Must be array.array for python-oracledb VECTOR binding"
    assert result.typecode == "f", "typecode 'f' maps to Oracle FLOAT32 vector type"
    assert len(result) == 3


def test_numpy_to_oracle_vector_float64_input():
    """float64 numpy arrays must be downcast to float32."""
    from app.workloads.vector_search import numpy_to_oracle_vector

    vec = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    result = numpy_to_oracle_vector(vec)

    assert result.typecode == "f"
    assert len(result) == 3


def test_vector_search_cycle_records_metrics(mock_connection):
    conn, cursor = mock_connection
    # Simulate 3 search results: (product_id, description, distance)
    cursor.fetchall.return_value = [
        (1, "Laptop Pro", 0.05),
        (2, "Headphones", 0.12),
        (3, "Smart Watch", 0.20),
    ]

    from app.workloads.vector_search import run_vector_search_cycle

    # Should complete without raising
    run_vector_search_cycle(conn, dimensions=8, top_k=3)

    # Verify the SELECT was called
    assert cursor.execute.called
    call_args = cursor.execute.call_args_list[0][0][0]
    assert "VECTOR_DISTANCE" in call_args


def test_vector_search_handles_empty_results(mock_connection):
    conn, cursor = mock_connection
    cursor.fetchall.return_value = []

    from app.workloads.vector_search import run_vector_search_cycle

    run_vector_search_cycle(conn, dimensions=8, top_k=5)
    assert cursor.execute.called


def test_vector_search_handles_error_gracefully(mock_connection):
    conn, cursor = mock_connection
    cursor.execute.side_effect = Exception("ORA-00942: table or view does not exist")

    from app.workloads.vector_search import run_vector_search_cycle

    # Must not raise — error is caught, recorded to metrics, span exception set
    run_vector_search_cycle(conn, dimensions=8)

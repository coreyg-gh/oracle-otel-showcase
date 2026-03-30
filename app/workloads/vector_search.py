"""Oracle 23ai AI Vector Search workload.

Inserts synthetic embeddings (unit-normalised random float32 vectors) and
performs approximate nearest-neighbour (ANN) searches using VECTOR_DISTANCE.

python-oracledb requires vector bind variables to be array.array('f', ...)
objects, not numpy arrays — this is handled by numpy_to_oracle_vector().
"""

import array
import logging
import random
import time

import numpy as np
from opentelemetry import trace

from app.otel import metrics as otel_metrics

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("oracle.workload.vector", tracer_provider=None)

_DESCRIPTIONS = [
    "High-performance computing device for professional workloads",
    "Ergonomic home office furniture with adjustable height",
    "Wireless audio device with active noise cancellation",
    "Smart home appliance with voice assistant integration",
    "Athletic footwear designed for trail running",
    "Professional kitchen appliance with multiple speed settings",
    "Wearable fitness tracker with heart rate monitoring",
    "Sustainable outdoor gear made from recycled materials",
    "Educational technology tool for remote learning",
    "Premium skincare product with natural ingredients",
]


def generate_embedding(dimensions: int = 1536) -> np.ndarray:
    """Generate a unit-normalised random float32 vector (synthetic demo embedding)."""
    vec = np.random.randn(dimensions).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def numpy_to_oracle_vector(embedding: np.ndarray) -> array.array:
    """Convert numpy float32 array to array.array('f') for python-oracledb VECTOR bind.

    python-oracledb does NOT accept numpy.ndarray directly for VECTOR columns.
    array.array('f', ...) maps to Oracle FLOAT32 vector type automatically.
    """
    return array.array("f", embedding.astype(np.float32).tolist())


def seed_embeddings(conn, settings) -> None:
    """Insert `vector_count_seed` synthetic embeddings tied to random products."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM products ORDER BY DBMS_RANDOM.VALUE FETCH FIRST :n ROWS ONLY", n=settings.vector_count_seed)
        product_ids = [row[0] for row in cur.fetchall()]

    if not product_ids:
        logger.warning("No products found for embedding seed — skipping")
        return

    rows = []
    for i in range(settings.vector_count_seed):
        pid = product_ids[i % len(product_ids)]
        desc = random.choice(_DESCRIPTIONS)
        emb = numpy_to_oracle_vector(generate_embedding(settings.vector_dimensions))
        rows.append((pid, desc, emb))

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO product_embeddings (product_id, description, embedding) VALUES (:1, :2, :3)",
            rows,
        )
    logger.info("Seeded %d vector embeddings", len(rows))


def run_vector_search_cycle(conn, dimensions: int = 1536, top_k: int = 5) -> None:
    """Perform one ANN search and record latency + similarity metrics."""
    with tracer.start_as_current_span("vector.search.cycle") as span:
        query_embedding = generate_embedding(dimensions)
        query_vec = numpy_to_oracle_vector(query_embedding)

        t0 = time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT
                           pe.product_id,
                           pe.description,
                           VECTOR_DISTANCE(pe.embedding, :query_vec, COSINE) AS distance
                       FROM product_embeddings pe
                       ORDER BY distance ASC
                       FETCH FIRST :top_k ROWS ONLY""",
                    query_vec=query_vec,
                    top_k=top_k,
                )
                results = cur.fetchall()

            duration_ms = (time.perf_counter() - t0) * 1000
            otel_metrics.query_duration_histogram.record(duration_ms, {"operation": "vector_search"})
            otel_metrics.db_operation_counter.add(1, {"operation": "vector_search"})

            span.set_attribute("vector.result_count", len(results))
            span.set_attribute("vector.dimensions", dimensions)
            span.set_attribute("vector.top_k", top_k)

            for _, _, distance in results:
                similarity = max(0.0, 1.0 - float(distance))
                otel_metrics.vector_similarity_histogram.record(
                    similarity,
                    {"distance_metric": "cosine"},
                )

            logger.debug("Vector search returned %d results in %.1fms", len(results), duration_ms)

        except Exception as exc:
            otel_metrics.db_error_counter.add(
                1, {"error_type": type(exc).__name__, "operation": "vector_search"}
            )
            span.record_exception(exc)
            logger.exception("Vector search failed")


def run_vector_insert_cycle(conn, dimensions: int = 1536) -> None:
    """Insert a single new embedding to keep the vector table growing."""
    with tracer.start_as_current_span("vector.insert.cycle") as span:
        t0 = time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM products ORDER BY DBMS_RANDOM.VALUE FETCH FIRST 1 ROWS ONLY")
                row = cur.fetchone()
            if not row:
                return
            product_id = row[0]
            emb = numpy_to_oracle_vector(generate_embedding(dimensions))
            desc = random.choice(_DESCRIPTIONS)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO product_embeddings (product_id, description, embedding) VALUES (:1, :2, :3)",
                    [product_id, desc, emb],
                )
            conn.commit()
            duration_ms = (time.perf_counter() - t0) * 1000
            otel_metrics.query_duration_histogram.record(duration_ms, {"operation": "vector_insert"})
            otel_metrics.db_operation_counter.add(1, {"operation": "vector_insert"})
            span.set_attribute("vector.dimensions", dimensions)
        except Exception as exc:
            otel_metrics.db_error_counter.add(
                1, {"error_type": type(exc).__name__, "operation": "vector_insert"}
            )
            span.record_exception(exc)
            logger.exception("Vector insert failed")

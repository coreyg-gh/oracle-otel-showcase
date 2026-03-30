"""Database schema initialisation.

Connects as SYSTEM to create the demo user (idempotent), then connects as
the demo user to create tables and seed data.
"""

import logging

import oracledb

from app.config import Settings

logger = logging.getLogger(__name__)

# DDL run as SYSTEM
_CREATE_USER_SQL = """
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM dba_users WHERE username = UPPER(:username);
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'CREATE USER ' || :username || ' IDENTIFIED BY ' || :password ||
            ' QUOTA UNLIMITED ON USERS';
        EXECUTE IMMEDIATE 'GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE,
            CREATE PROCEDURE, CREATE VIEW TO ' || :username;
    END IF;
END;
"""

# DDL run as demo user
_CREATE_PRODUCTS_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR2(200)   NOT NULL,
    category    VARCHAR2(100),
    price       NUMBER(10, 2),
    stock_qty   NUMBER          DEFAULT 0,
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP
)
"""

_CREATE_EMBEDDINGS_SQL = """
CREATE TABLE IF NOT EXISTS product_embeddings (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id  NUMBER          REFERENCES products(id) ON DELETE CASCADE,
    description VARCHAR2(4000),
    embedding   VECTOR(1536, FLOAT32),
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
)
"""

# HNSW vector index — created after seed data is inserted
_CREATE_VECTOR_INDEX_SQL = """
CREATE VECTOR INDEX IF NOT EXISTS product_emb_hnsw_idx
    ON product_embeddings(embedding)
    USING HNSW
    WITH TARGET ACCURACY 95
    DISTANCE COSINE
    PARAMETERS (efConstruction=100, M=16)
"""

_SEED_PRODUCTS = [
    ("Laptop Pro 15", "Electronics", 1299.99, 50),
    ("Wireless Headphones", "Electronics", 249.99, 120),
    ("Standing Desk", "Furniture", 599.00, 30),
    ("Coffee Maker", "Appliances", 89.99, 200),
    ("Running Shoes", "Footwear", 129.99, 75),
    ("Yoga Mat", "Sports", 45.00, 300),
    ("Smart Watch", "Electronics", 399.99, 60),
    ("Bookshelf Oak", "Furniture", 349.00, 20),
    ("Blender Pro", "Appliances", 149.99, 90),
    ("Hiking Boots", "Footwear", 189.99, 45),
]


def _connect_as_system(settings: Settings) -> oracledb.Connection:
    dsn = f"{settings.oracle_host}:{settings.oracle_port}/{settings.oracle_service}"
    return oracledb.connect(user="system", password=settings.oracle_system_password, dsn=dsn)


def _connect_as_demo(settings: Settings) -> oracledb.Connection:
    dsn = f"{settings.oracle_host}:{settings.oracle_port}/{settings.oracle_service}"
    return oracledb.connect(user=settings.oracle_user, password=settings.oracle_password, dsn=dsn)


def initialise_schema(settings: Settings, seed_vectors_fn=None) -> None:
    """Idempotent schema setup. Call once at application startup."""
    logger.info("Initialising database schema...")

    # Step 1: ensure demo user exists
    with _connect_as_system(settings) as sys_conn:
        with sys_conn.cursor() as cur:
            cur.execute(
                _CREATE_USER_SQL,
                username=settings.oracle_user,
                password=settings.oracle_password,
            )
        sys_conn.commit()
    logger.info("Demo user '%s' ensured", settings.oracle_user)

    # Step 2: create tables as demo user
    with _connect_as_demo(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_PRODUCTS_SQL)
            cur.execute(_CREATE_EMBEDDINGS_SQL)
        conn.commit()
    logger.info("Tables ensured")

    # Step 3: seed product rows if empty
    with _connect_as_demo(settings) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM products")
        (count,) = cur.fetchone()
        if count == 0:
            logger.info("Seeding %d products...", len(_SEED_PRODUCTS))
            cur.executemany(
                "INSERT INTO products (name, category, price, stock_qty) VALUES (:1, :2, :3, :4)",
                _SEED_PRODUCTS,
            )
            conn.commit()
            logger.info("Product seed complete")

    # Step 4: seed embeddings (requires vector data first for HNSW index)
    if seed_vectors_fn is not None:
        with _connect_as_demo(settings) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM product_embeddings")
                (emb_count,) = cur.fetchone()
            if emb_count == 0:
                logger.info("Seeding %d vector embeddings...", settings.vector_count_seed)
                seed_vectors_fn(conn, settings)
                conn.commit()

        # Step 5: create HNSW index after seed data is present
        with _connect_as_demo(settings) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(_CREATE_VECTOR_INDEX_SQL)
                conn.commit()
                logger.info("HNSW vector index ensured")
            except oracledb.DatabaseError as exc:
                # Index may already exist or data may be too small — log and continue
                logger.warning("Vector index creation skipped: %s", exc)

    logger.info("Schema initialisation complete")

from psycopg_pool import ConnectionPool

from Server.config import DATABASE_URI, POOL_MAX_SIZE, POOL_MIN_SIZE

_pool: ConnectionPool | None = None

BLOG_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS blog_jobs (
    id UUID PRIMARY KEY,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'IN-PROGRESS'
        CHECK (status IN ('IN-PROGRESS', 'COMPLETE', 'HALTED')),
    stage TEXT NOT NULL DEFAULT 'queued',
    recoverable BOOLEAN NOT NULL DEFAULT FALSE,
    research_done BOOLEAN NOT NULL DEFAULT FALSE,
    final_blog_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Backfill for databases created before the stage column existed.
BLOG_JOBS_STAGE_MIGRATION = (
    "ALTER TABLE blog_jobs ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'queued';"
)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URI:
            raise RuntimeError("DATABASE_URI is not set. Configure it in .env")
        _pool = ConnectionPool(
            DATABASE_URI,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
    return _pool


def setup_job_table() -> None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(BLOG_JOBS_SCHEMA)
            cur.execute(BLOG_JOBS_STAGE_MIGRATION)


def check_connection() -> None:
    """Raise if the database is unreachable. Used for startup/readiness checks."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

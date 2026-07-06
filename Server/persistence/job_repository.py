import uuid
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from Server.persistence.database import setup_job_table


class DBRepositoryError(Exception):
    """Raised when a database operation fails.

    Wraps the underlying ``psycopg`` error and carries the operation name plus
    contextual metadata (e.g. the job id) so callers can log which operation
    failed and for what job without digging into the driver exception.
    """

    def __init__(self, operation: str, metadata: dict[str, Any], original: Exception) -> None:
        self.operation = operation
        self.metadata = metadata
        self.original = original
        super().__init__(f"DB {operation} failed ({metadata}): {original}")


@contextmanager
def _guard(operation: str, **metadata: Any):
    """Convert any ``psycopg`` error inside the block into a ``RepositoryError``."""
    try:
        yield
    except psycopg.Error as exc:
        raise DBRepositoryError(operation, metadata, exc) from exc

JobStatus = str
JOB_IN_PROGRESS = "IN-PROGRESS"
JOB_COMPLETE = "COMPLETE"
JOB_HALTED = "HALTED"
JOB_FAILED = "FAILED"

# Fine-grained progress stages, surfaced to the client while a job runs.
STAGE_QUEUED = "queued"
STAGE_GENERATING_QUERIES = "generating_queries"
STAGE_RESEARCHING = "researching"
STAGE_PLANNING = "planning"
STAGE_WRITING_SECTIONS = "writing_sections"
STAGE_SYNTHESIZING = "synthesizing"
STAGE_COMPLETE = "complete"
STAGE_HALTED = "halted"
STAGE_FAILED = "failed"

_SELECT_COLUMNS = (
    "id, topic, status, stage, recoverable, research_done, "
    "final_blog_path, created_at, updated_at"
)


def _row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "topic": row[1],
        "status": row[2],
        "stage": row[3],
        "recoverable": row[4],
        "research_done": row[5],
        "final_blog_path": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


class JobRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        setup_job_table()

    def create_job(self, topic: str) -> str:
        job_id = str(uuid.uuid4())
        with _guard("create_job", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO blog_jobs (id, topic, status, stage, recoverable, research_done)
                        VALUES (%s, %s, %s, %s, FALSE, FALSE)
                        """,
                        (job_id, topic, JOB_IN_PROGRESS, STAGE_QUEUED),
                    )
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with _guard("get_job", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM blog_jobs WHERE id = %s",
                        (job_id,),
                    )
                    row = cur.fetchone()
        if row is None:
            return None
        return _row_to_dict(row)

    def list_jobs(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with _guard("list_jobs", limit=limit, offset=offset):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM blog_jobs
                        WHERE status <> %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (JOB_FAILED, limit, offset),
                    )
                    rows = cur.fetchall()
        return [_row_to_dict(row) for row in rows]

    def count_jobs(self) -> int:
        with _guard("count_jobs"):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM blog_jobs WHERE status <> %s",
                        (JOB_FAILED,),
                    )
                    row = cur.fetchone()
        return int(row[0]) if row else 0

    def update_stage(self, job_id: str, stage: str) -> None:
        with _guard("update_stage", job_id=job_id, stage=stage):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE blog_jobs
                        SET stage = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (stage, job_id),
                    )

    def mark_research_done(self, job_id: str) -> None:
        with _guard("mark_research_done", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE blog_jobs
                        SET research_done = TRUE, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (job_id,),
                    )

    def mark_complete(self, job_id: str, final_blog_path: str | None) -> None:
        with _guard("mark_complete", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE blog_jobs
                        SET status = %s,
                            stage = %s,
                            recoverable = FALSE,
                            final_blog_path = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (JOB_COMPLETE, STAGE_COMPLETE, final_blog_path, job_id),
                    )

    def mark_halted(self, job_id: str) -> None:
        with _guard("mark_halted", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE blog_jobs
                        SET status = %s,
                            stage = %s,
                            recoverable = TRUE,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (JOB_HALTED, STAGE_HALTED, job_id),
                    )

    def mark_failed(self, job_id: str) -> None:
        with _guard("mark_failed", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE blog_jobs
                        SET status = %s,
                            stage = %s,
                            recoverable = FALSE,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (JOB_FAILED, STAGE_FAILED, job_id),
                    )

    def mark_in_progress(self, job_id: str) -> None:
        with _guard("mark_in_progress", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE blog_jobs
                        SET status = %s,
                            stage = %s,
                            recoverable = FALSE,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (JOB_IN_PROGRESS, STAGE_QUEUED, job_id),
                    )

    def delete_job(self, job_id: str) -> None:
        with _guard("delete_job", job_id=job_id):
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM blog_jobs WHERE id = %s", (job_id,))

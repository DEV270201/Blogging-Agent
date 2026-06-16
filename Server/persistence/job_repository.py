import uuid
from typing import Any

from psycopg_pool import ConnectionPool

from Server.persistence.database import setup_job_table

JobStatus = str
JOB_IN_PROGRESS = "IN-PROGRESS"
JOB_COMPLETE = "COMPLETE"
JOB_HALTED = "HALTED"

# Fine-grained progress stages, surfaced to the client while a job runs.
STAGE_QUEUED = "queued"
STAGE_GENERATING_QUERIES = "generating_queries"
STAGE_RESEARCHING = "researching"
STAGE_PLANNING = "planning"
STAGE_WRITING_SECTIONS = "writing_sections"
STAGE_SYNTHESIZING = "synthesizing"
STAGE_COMPLETE = "complete"
STAGE_HALTED = "halted"

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
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_SELECT_COLUMNS}
                    FROM blog_jobs
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()
        return [_row_to_dict(row) for row in rows]

    def count_jobs(self) -> int:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM blog_jobs")
                row = cur.fetchone()
        return int(row[0]) if row else 0

    def update_stage(self, job_id: str, stage: str) -> None:
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

    def mark_in_progress(self, job_id: str) -> None:
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
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM blog_jobs WHERE id = %s", (job_id,))

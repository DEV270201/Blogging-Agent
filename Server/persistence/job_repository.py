import uuid
from typing import Any

from psycopg_pool import ConnectionPool

from Server.persistence.database import setup_job_table

JobStatus = str
JOB_IN_PROGRESS = "IN-PROGRESS"
JOB_COMPLETE = "COMPLETE"
JOB_HALTED = "HALTED"


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
                    INSERT INTO blog_jobs (id, topic, status, recoverable, research_done)
                    VALUES (%s, %s, %s, FALSE, FALSE)
                    """,
                    (job_id, topic, JOB_IN_PROGRESS),
                )
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, topic, status, recoverable, research_done,
                           final_blog_path, created_at, updated_at
                    FROM blog_jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": str(row[0]),
            "topic": row[1],
            "status": row[2],
            "recoverable": row[3],
            "research_done": row[4],
            "final_blog_path": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

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
                        recoverable = FALSE,
                        final_blog_path = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (JOB_COMPLETE, final_blog_path, job_id),
                )

    def mark_halted(self, job_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE blog_jobs
                    SET status = %s,
                        recoverable = TRUE,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (JOB_HALTED, job_id),
                )

    def mark_in_progress(self, job_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE blog_jobs
                    SET status = %s,
                        recoverable = FALSE,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (JOB_IN_PROGRESS, job_id),
                )

    def delete_job(self, job_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM blog_jobs WHERE id = %s", (job_id,))

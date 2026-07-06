import logging
from pathlib import Path
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from Server.graph import build_blog_agent
from Server.nodes.synthesizer import blog_output_path
from Server.persistence.checkpointer import delete_checkpoint_thread, get_checkpointer
from Server.persistence.database import get_pool
from Server.persistence.job_repository import (
    JOB_HALTED,
    STAGE_GENERATING_QUERIES,
    STAGE_PLANNING,
    STAGE_RESEARCHING,
    STAGE_SYNTHESIZING,
    STAGE_WRITING_SECTIONS,
    JobRepository,
)

logger = logging.getLogger("blog_agent.service")

_service: "BlogJobService | None" = None


class JobNotFoundError(Exception):
    """Raised when a job id does not exist."""


class JobNotResumableError(Exception):
    """Raised when a retry is requested for a job that cannot be resumed."""


class BlogJobService:
    def __init__(self, agent: CompiledStateGraph, job_repo: JobRepository) -> None:
        self._agent = agent
        self._job_repo = job_repo

    # -- creation / execution -------------------------------------------------

    def create(self, topic: str) -> str:
        """Register a new job and return its id immediately (no generation yet)."""
        return self._job_repo.create_job(topic)

    def run(self, topic: str) -> str:
        """Create and run a job synchronously. Convenient for CLI/one-off use."""
        job_id = self.create(topic)
        self.execute(job_id, topic)
        return job_id

    def execute(self, job_id: str, topic: str) -> None:
        """Run the graph for an already-created job. Intended for background workers."""
        config = {"configurable": {"thread_id": job_id}}
        try:
            self._execute_graph({"topic": topic}, config, job_id)
            final_blog_path = self._resolve_blog_path(config)
            self._job_repo.mark_complete(job_id, final_blog_path)
        except Exception:
            self._handle_failure(job_id, config)
            raise

    def retry(self, job_id: str) -> str:
        """Resume a halted, recoverable job from its last checkpoint."""
        job = self._job_repo.get_job(job_id)
        # if job is None:
        #     raise JobNotFoundError(f"Job {job_id} not found")
        # if job["status"] != JOB_HALTED or not job["recoverable"]:
        #     raise JobNotResumableError(f"Job {job_id} cannot be resumed")

        config = {"configurable": {"thread_id": job_id}}
        self._job_repo.mark_in_progress(job_id)
        try:
            self._execute_graph(None, config, job_id)
            final_blog_path = self._resolve_blog_path(config)
            self._job_repo.mark_complete(job_id, final_blog_path)
            return job_id
        except Exception:
            self._handle_failure(job_id, config)
            raise

    # -- reads ----------------------------------------------------------------

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._job_repo.get_job(job_id)

    def list_jobs(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        jobs = self._job_repo.list_jobs(limit, offset)
        total = self._job_repo.count_jobs()
        return jobs, total

    def get_blog_content(self, job_id: str) -> dict[str, Any] | None:
        """Return the generated blog for a job, or None if the job does not exist.

        The returned dict has ``content`` set to None when the blog is not ready yet.
        """
        job = self._job_repo.get_job(job_id)
        if job is None:
            return None

        config = {"configurable": {"thread_id": job_id}}
        state = self._agent.get_state(config)
        plan = state.values.get("plan")
        title = self._plan_title(plan)

        content: str | None = None
        path = job.get("final_blog_path")
        if path:
            file_path = Path(path)
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
        if content is None:
            content = state.values.get("final_blog")

        return {"content": content, "title": title, "path": path}

    # -- internals ------------------------------------------------------------

    def _execute_graph(
        self,
        input_state: dict[str, str] | None,
        config: dict[str, Any],
        job_id: str,
    ) -> None:
        # Seed the starting stage. On resume (input_state is None) skip ahead if
        # research already finished so the client does not briefly see an earlier stage.
        initial_stage = STAGE_GENERATING_QUERIES
        if input_state is None:
            job = self._job_repo.get_job(job_id)
            if job is not None and job["research_done"]:
                initial_stage = STAGE_PLANNING
        self._job_repo.update_stage(job_id, initial_stage)

        for chunk in self._agent.stream(input_state, config, stream_mode="updates"):
            if "queries_generator" in chunk:
                self._job_repo.update_stage(job_id, STAGE_RESEARCHING)
            if "research_node" in chunk:
                self._job_repo.mark_research_done(job_id)
                self._job_repo.update_stage(job_id, STAGE_PLANNING)
            if "orchestrator" in chunk:
                self._job_repo.update_stage(job_id, STAGE_WRITING_SECTIONS)
            if "synthesizer" in chunk:
                self._job_repo.update_stage(job_id, STAGE_SYNTHESIZING)

    def _resolve_blog_path(self, config: dict[str, Any]) -> str | None:
        state = self._agent.get_state(config)
        plan = state.values.get("plan")
        if plan is None:
            return None
        title = self._plan_title(plan)
        if title is None:
            return None
        return str(blog_output_path(title))

    @staticmethod
    def _plan_title(plan: Any) -> str | None:
        if plan is None:
            return None
        if hasattr(plan, "blog_title"):
            return plan.blog_title
        if isinstance(plan, dict):
            return plan.get("blog_title")
        return None

    def _handle_failure(self, job_id: str, config: dict[str, Any]) -> None:
        # Runs while handling an already-failed run. Guard against a second failure
        # here (e.g. the DB is what went down) so cleanup errors are logged rather
        # than masking the original exception the caller is about to re-raise.
        try:
            job = self._job_repo.get_job(job_id)
            state = self._agent.get_state(config)
            research_done = (
                job is not None and job["research_done"]
            ) or state.values.get("evidence") is not None

            if research_done and job is not None:
                if not job["research_done"]:
                    self._job_repo.mark_research_done(job_id)
                self._job_repo.mark_halted(job_id)
            else:
                delete_checkpoint_thread(job_id)
                if job is not None:
                    self._job_repo.delete_job(job_id)
        except Exception:
            logger.exception("Failed to record failure state for job %s", job_id)


def get_blog_job_service() -> BlogJobService:
    global _service
    if _service is None:
        pool = get_pool()
        checkpointer = get_checkpointer()
        agent = build_blog_agent(checkpointer)
        _service = BlogJobService(agent, JobRepository(pool))
    return _service

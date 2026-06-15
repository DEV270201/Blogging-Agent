from typing import Any

from langgraph.graph.state import CompiledStateGraph

from Server.graph import build_blog_agent
from Server.nodes.synthesizer import blog_output_path
from Server.persistence.checkpointer import delete_checkpoint_thread, get_checkpointer
from Server.persistence.database import get_pool
from Server.persistence.job_repository import (
    JOB_HALTED,
    JobRepository,
)

_service: "BlogJobService | None" = None


class BlogJobService:
    def __init__(self, agent: CompiledStateGraph, job_repo: JobRepository) -> None:
        self._agent = agent
        self._job_repo = job_repo

    def run(self, topic: str) -> str:
        job_id = self._job_repo.create_job(topic)
        config = {"configurable": {"thread_id": job_id}}
        try:
            self._execute_graph({"topic": topic}, config, job_id)
            final_blog_path = self._resolve_blog_path(config)
            self._job_repo.mark_complete(job_id, final_blog_path)
            return job_id
        except Exception:
            self._handle_failure(job_id, config)
            raise

    def retry(self, job_id: str) -> str:
        job = self._job_repo.get_job(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        if job["status"] != JOB_HALTED or not job["recoverable"]:
            raise ValueError(f"Job {job_id} cannot be resumed")

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

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._job_repo.get_job(job_id)

    def _execute_graph(
        self,
        input_state: dict[str, str] | None,
        config: dict[str, Any],
        job_id: str,
    ) -> None:
        for chunk in self._agent.stream(
            input_state,
            config,
            stream_mode="updates",
        ):
            if "research_node" in chunk:
                self._job_repo.mark_research_done(job_id)

    def _resolve_blog_path(self, config: dict[str, Any]) -> str | None:
        state = self._agent.get_state(config)
        plan = state.values.get("plan")
        if plan is None:
            return None
        title = plan.blog_title if hasattr(plan, "blog_title") else plan["blog_title"]
        return str(blog_output_path(title))

    def _handle_failure(self, job_id: str, config: dict[str, Any]) -> None:
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


def get_blog_job_service() -> BlogJobService:
    global _service
    if _service is None:
        pool = get_pool()
        checkpointer = get_checkpointer()
        agent = build_blog_agent(checkpointer)
        _service = BlogJobService(agent, JobRepository(pool))
    return _service

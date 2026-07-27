import logging
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from Server.config import JOB_HEARTBEAT_INTERVAL_SECONDS
from Server.graph import build_blog_agent
from Server.nodes.synthesizer import blog_output_path
from Server.persistence.checkpointer import delete_checkpoint_thread, get_checkpointer
from Server.persistence.database import get_pool
from Server.persistence.job_repository import (
    JOB_AWAITING_INPUT,
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

# When a run fails, recording its terminal status also needs the DB — which may
# be exactly what went down. Retry the recording with exponential backoff so the
# job stops being a zombie once the DB recovers within this window (~60s total).
_FAILURE_RECORD_MAX_ATTEMPTS = 6
_FAILURE_RECORD_BASE_DELAY_S = 2.0
_FAILURE_RECORD_MAX_DELAY_S = 16.0


class JobNotFoundError(Exception):
    """Raised when a job id does not exist."""


class JobNotResumableError(Exception):
    """Raised when a retry is requested for a job that cannot be resumed."""


class BlogJobService:
    def __init__(self, agent: CompiledStateGraph, job_repo: JobRepository) -> None:
        self._agent = agent
        self._job_repo = job_repo
        # Identifies this process as the owner of jobs it runs. A fresh id each
        # start is fine: a dead process's jobs are reclaimed by lease expiry, not
        # by matching an old id.
        self._instance_id = str(uuid.uuid4())

    @property
    def instance_id(self) -> str:
        return self._instance_id

    # -- creation / execution -------------------------------------------------

    def create(self, topic: str) -> str:
        """ Register a new job and return its id immediately (no generation yet)."""
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
            self._job_repo.claim_job(job_id, self._instance_id)
            with self._heartbeat(job_id):
                interrupted = self._execute_graph({"topic": topic}, config, job_id)
            self._finalize(job_id, config, interrupted)
        except Exception:
            self._handle_failure(job_id, config)
            raise

    def prepare_retry(self, job_id: str) -> None:
        """Flip a halted job to in-progress synchronously, in the request thread.

        Called before the background retry is submitted so a client that polls
        immediately sees the IN-PROGRESS switch right away instead of briefly
        reading the stale HALTED status (which would abort its polling).
        """
        self._job_repo.mark_in_progress(job_id)

    def retry(self, job_id: str) -> str:
        """Resume a halted, recoverable job from its last checkpoint.

        Assumes the job was already flipped to IN-PROGRESS via ``prepare_retry``.
        A halted job may be sitting on the research-review interrupt (e.g. it
        crashed in the pause window); resuming with ``None`` re-hits the
        interrupt, and ``_finalize`` sends it back to AWAITING_INPUT rather than
        completing a blog-less job.
        """
        config = {"configurable": {"thread_id": job_id}}
        try:
            self._job_repo.claim_job(job_id, self._instance_id)
            with self._heartbeat(job_id):
                interrupted = self._execute_graph(None, config, job_id)
            self._finalize(job_id, config, interrupted)
            return job_id
        except Exception:
            self._handle_failure(job_id, config)
            raise

    def prepare_decision(self, job_id: str) -> None:
        """Flip an awaiting-input job to in-progress synchronously, in the request
        thread — mirrors ``prepare_retry`` so a client polling right after the
        decision call never reads the stale AWAITING_INPUT status."""
        self._job_repo.mark_in_progress(job_id)

    def submit_decision(self, job_id: str, decision: str) -> str:
        """Resume a paused job with the user's research-review decision.

        Assumes the job was already flipped to IN-PROGRESS via
        ``prepare_decision``. ``decision`` is "proceed" or "redo"; a "redo" that
        still yields weak coverage re-interrupts and returns to AWAITING_INPUT.
        """
        config = {"configurable": {"thread_id": job_id}}
        try:
            self._job_repo.claim_job(job_id, self._instance_id)
            with self._heartbeat(job_id):
                interrupted = self._execute_graph(
                    Command(resume=decision), config, job_id
                )
            self._finalize(job_id, config, interrupted)
            return job_id
        except Exception:
            self._handle_failure(job_id, config)
            raise

    def restore_awaiting_input(self, job_id: str) -> None:
        """Revert a job back to AWAITING_INPUT (used when the executor rejects a
        decision task after ``prepare_decision`` already flipped it to IN-PROGRESS)."""
        self._job_repo.mark_awaiting_input(job_id)

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

    def get_pending_review(self, job_id: str) -> dict[str, Any] | None:
        """Return the pending research-review payload for a paused job.

        Returns ``None`` if the job does not exist, or ``{"pending": False}`` if
        it is not awaiting input. When paused, returns
        ``{"pending": True, "payload": <interrupt value>}`` read from the
        checkpointed interrupt.
        """
        job = self._job_repo.get_job(job_id)
        if job is None:
            return None
        if job["status"] != JOB_AWAITING_INPUT:
            return {"pending": False}

        config = {"configurable": {"thread_id": job_id}}
        snapshot = self._agent.get_state(config)
        for task in snapshot.tasks:
            interrupts = getattr(task, "interrupts", None) or ()
            if interrupts:
                return {"pending": True, "payload": interrupts[0].value}
        return {"pending": False}

    # -- reconciliation -------------------------------------------------------

    def reclaim_expired_leases(self, lease_timeout_seconds: int) -> tuple[int, int]:
        """Reconcile orphaned jobs (expired lease). Safe to run on any instance."""
        halted, failed = self._job_repo.reclaim_expired_leases(lease_timeout_seconds)
        if halted or failed:
            logger.info(
                "Reclaimed orphaned jobs: %s halted, %s failed", halted, failed
            )
        return halted, failed

    def reclaim_owner_jobs(self, owner_id: str) -> tuple[int, int]:
        """Reconcile this instance's own in-flight jobs (used on graceful shutdown)."""
        halted, failed = self._job_repo.reclaim_owner_jobs(owner_id)
        if halted or failed:
            logger.info(
                "Reconciled own in-flight jobs on shutdown: %s halted, %s failed",
                halted,
                failed,
            )
        return halted, failed

    def mark_interrupted(self, job_id: str) -> None:
        """Reconcile a single job that was flipped to IN-PROGRESS but never started
        running (e.g. the executor rejected the task). Recoverable if research was
        already done, otherwise failed — mirrors ``_handle_failure``."""
        job = self._job_repo.get_job(job_id)
        if job is None:
            return
        if job["research_done"]:
            self._job_repo.mark_halted(job_id)
        else:
            self._job_repo.mark_failed(job_id)

    # -- internals ------------------------------------------------------------

    @contextmanager
    def _heartbeat(self, job_id: str) -> Iterator[None]:
        """Renew a running job's lease on a background daemon thread.

        A single graph node can block the worker thread for minutes, so the
        worker cannot renew its own lease mid-node. This companion thread bumps
        the heartbeat every ``JOB_HEARTBEAT_INTERVAL_SECONDS`` independently, and
        is stopped and joined when the ``with`` block exits.
        """
        stop = threading.Event()

        def _beat() -> None:
            while not stop.wait(JOB_HEARTBEAT_INTERVAL_SECONDS):
                try:
                    logger.info(f"Heartbeat sending for JOB ID: {job_id}")
                    self._job_repo.mark_heartbeat(job_id)
                except Exception:
                    logger.warning(
                        "Heartbeat failed for job %s", job_id, exc_info=True
                    )

        thread = threading.Thread(
            target=_beat, name=f"hb-{job_id}", daemon=True
        )
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=2)

    def _execute_graph(
        self,
        input_state: dict[str, str] | Command | None,
        config: dict[str, Any],
        job_id: str,
    ) -> bool:
        """Stream the graph, mapping node updates to job stages. Returns True if
        the run paused on a human-in-the-loop interrupt (research review)."""
        # Seed the starting stage so the client never briefly sees a stale one.
        #  - fresh run: starts at query generation.
        #  - "redo" decision: loops the graph BACK to queries_generator, so it
        #    also starts at query generation (research_done stays True in the DB
        #    but the graph is genuinely re-researching).
        #  - proceed / retry: research already finished, continue from planning.
        is_fresh = isinstance(input_state, dict)
        resume_value = (
            input_state.resume if isinstance(input_state, Command) else None
        )
        if is_fresh or resume_value == "redo":
            initial_stage = STAGE_GENERATING_QUERIES
        else:
            job = self._job_repo.get_job(job_id)
            initial_stage = (
                STAGE_PLANNING
                if job is not None and job["research_done"]
                else STAGE_GENERATING_QUERIES
            )
        self._job_repo.update_stage(job_id, initial_stage)
        print(f"Initial stage: {initial_stage}")

        # How many sections (parallel workers) to expect, so we can tell when
        # drafting is done and the synthesizer takes over. On a resume the plan
        # already exists in the checkpoint, so read it once up front (a plain read
        # before the stream — never mid-stream, which would re-enter the
        # checkpointer). On a fresh run it's captured from the orchestrator update
        # below; a "redo" that re-plans also refreshes it there.
        is_resume = not is_fresh
        expected_workers: int | None = (
            self._plan_task_count(config) if is_resume else None
        )
        workers_seen = 0
        interrupted = False
        for chunk in self._agent.stream(input_state, config, stream_mode="updates"):
            if "queries_generator" in chunk:
                self._job_repo.update_stage(job_id, STAGE_RESEARCHING)
            if "research_node" in chunk:
                self._job_repo.mark_research_done(job_id)
                self._job_repo.update_stage(job_id, STAGE_PLANNING)
            # Freshly (re)built plan — refresh the expected section count from it.
            if "orchestrator" in chunk:
                count = self._task_count_from_plan(
                    (chunk["orchestrator"] or {}).get("plan")
                )
                if count:
                    expected_workers = count
            # The review gate returning "proceed" is where drafting begins — the
            # workers fan out immediately after. Set writing_sections here (not on
            # a worker update, which fires only *after* a section finishes).
            # "redo" loops back instead, so it must not flip the stage forward.
            if "review_gate" in chunk:
                if (chunk["review_gate"] or {}).get("research_decision") == "proceed":
                    self._job_repo.update_stage(job_id, STAGE_WRITING_SECTIONS)
            # Workers run in parallel: one "worker" update per section. Once every
            # expected section is written, the synthesizer is what runs next.
            if "worker" in chunk:
                workers_seen += 1
                if expected_workers and workers_seen >= expected_workers:
                    self._job_repo.update_stage(job_id, STAGE_SYNTHESIZING)
            # Fallback: if the section count couldn't be resolved, at least flip to
            # synthesizing when the synthesizer reports (mark_complete follows).
            if "synthesizer" in chunk and not expected_workers:
                self._job_repo.update_stage(job_id, STAGE_SYNTHESIZING)
            if "__interrupt__" in chunk:
                # The graph paused at the research-review gate; the stream ends
                # right after this chunk. Caller flips the job to AWAITING_INPUT.
                interrupted = True
        return interrupted

    def _finalize(self, job_id: str, config: dict[str, Any], interrupted: bool) -> None:
        """Single completion path shared by execute/retry/submit_decision so no
        run can mark a job COMPLETE when it actually paused on an interrupt."""
        if interrupted:
            self._job_repo.mark_awaiting_input(job_id)
            return
        final_blog_path = self._resolve_blog_path(config)
        self._job_repo.mark_complete(job_id, final_blog_path)

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

    def _plan_task_count(self, config: dict[str, Any]) -> int | None:
        """Section (parallel-worker) count from the checkpointed plan. Called once
        before a resume stream — a plain read, never mid-stream (which would
        re-enter the checkpointer)."""
        try:
            plan = self._agent.get_state(config).values.get("plan")
        except Exception:
            return None
        return self._task_count_from_plan(plan)

    @staticmethod
    def _task_count_from_plan(plan: Any) -> int | None:
        """Number of sections in a plan, whether it's a live Plan object or a
        dict reloaded from a checkpoint."""
        if plan is None:
            return None
        tasks = getattr(plan, "tasks", None)
        if tasks is None and isinstance(plan, dict):
            tasks = plan.get("tasks")
        return len(tasks) if tasks else None

    def _handle_failure(self, job_id: str, config: dict[str, Any]) -> None:
        # Runs while handling an already-failed run. Recording the terminal status
        # also needs the DB (get_job / get_state / mark_*), which may be exactly what
        # went down. Retry with backoff so the job is flipped to FAILED/HALTED once the
        # DB recovers; if it never does, log and let the caller re-raise the original
        # exception. The steps are idempotent, so re-running after a partial write is safe.
        delay = _FAILURE_RECORD_BASE_DELAY_S
        last_exc: Exception | None = None
        for attempt in range(1, _FAILURE_RECORD_MAX_ATTEMPTS + 1):
            try:
                self._record_status_during_failure(job_id, config)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < _FAILURE_RECORD_MAX_ATTEMPTS:
                    logger.warning(
                        "Attempt %d/%d to record state for job %s failed: %s; "
                        "retrying in %.0fs",
                        attempt,
                        _FAILURE_RECORD_MAX_ATTEMPTS,
                        job_id,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, _FAILURE_RECORD_MAX_DELAY_S)
        logger.error(
            "Failed to record state for job %s after %d attempts",
            job_id,
            _FAILURE_RECORD_MAX_ATTEMPTS,
            exc_info=last_exc,
        )

    def _record_status_during_failure(self, job_id: str, config: dict[str, Any]) -> None:
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
            # No reusable research and the job won't be retried, so drop the
            # partial checkpoint but keep the job record as FAILED so the client
            # polling it learns the run failed instead of seeing it vanish.
            delete_checkpoint_thread(job_id)
            if job is not None:
                self._job_repo.mark_failed(job_id)


def get_blog_job_service() -> BlogJobService:
    global _service
    if _service is None:
        pool = get_pool()
        checkpointer = get_checkpointer()
        agent = build_blog_agent(checkpointer)
        _service = BlogJobService(agent, JobRepository(pool))
    return _service

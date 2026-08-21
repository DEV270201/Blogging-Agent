"""Unit tests for BlogJobService.

All external dependencies (graph agent, job repository) are replaced with
MagicMocks so these tests run fully offline and without a database.
"""

from unittest.mock import MagicMock, call

import pytest

from langgraph.types import Command

from Server.services.blog_job_service import BlogJobService
from Server.persistence.job_repository import (
    JOB_AWAITING_INPUT,
    STAGE_GENERATING_QUERIES,
    STAGE_PLANNING,
    STAGE_RESEARCHING,
    STAGE_SYNTHESIZING,
    STAGE_WRITING_SECTIONS,
)
from Server.state import Bullet, Plan, Task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_plan_obj(num_tasks=1) -> Plan:
    tasks = [
        Task(
            id=i,
            title=f"Section {i}",
            description="d",
            goal="g",
            bullets=[
                Bullet(text="b1", bullet_type="prose"),
                Bullet(text="b2", bullet_type="prose"),
            ],
            target_words=150,
        )
        for i in range(num_tasks)
    ]
    return Plan(
        blog_title="Test Blog",
        blog_description="desc",
        evidence_coverage="sufficient",
        research_note="",
        tasks=tasks,
        audience="developers",
    )


def make_state_snapshot(plan=None, final_blog=None, evidence=None):
    snapshot = MagicMock()
    snapshot.values = {
        "plan": plan,
        "final_blog": final_blog,
        "evidence": evidence,
    }
    snapshot.tasks = []
    return snapshot


# ---------------------------------------------------------------------------
# create / execute
# ---------------------------------------------------------------------------


class TestCreate:
    def test_delegates_to_repo(self, service, mock_job_repo):
        mock_job_repo.create_job.return_value = "job-abc"
        result = service.create("Test topic")
        mock_job_repo.create_job.assert_called_once_with("Test topic")
        assert result == "job-abc"


class TestExecute:
    def test_claims_job_before_streaming(self, service, mock_agent, mock_job_repo, mocker):
        mocker.patch("Server.services.blog_job_service.delete_checkpoint_thread")
        mock_agent.stream.return_value = iter([])
        mock_agent.get_state.return_value = make_state_snapshot()
        mock_job_repo.get_job.return_value = {"research_done": False, "status": "IN-PROGRESS"}

        service.execute("job-1", "topic")
        mock_job_repo.claim_job.assert_called_once_with("job-1", service.instance_id)

    def test_marks_complete_when_stream_finishes_without_interrupt(
        self, service, mock_agent, mock_job_repo, mocker
    ):
        plan = make_plan_obj()
        mocker.patch(
            "Server.services.blog_job_service.blog_output_path",
            return_value="/blogs/test.md",
        )
        mock_agent.stream.return_value = iter([])
        mock_agent.get_state.return_value = make_state_snapshot(plan=plan)
        mock_job_repo.get_job.return_value = {"research_done": False, "status": "IN-PROGRESS"}

        service.execute("job-1", "topic")
        mock_job_repo.mark_complete.assert_called_once()
        mock_job_repo.mark_awaiting_input.assert_not_called()

    def test_marks_awaiting_input_when_interrupt_detected(
        self, service, mock_agent, mock_job_repo, mocker
    ):
        """Critical: a paused job must never be marked COMPLETE."""
        mock_agent.stream.return_value = iter([{"__interrupt__": []}])
        mock_agent.get_state.return_value = make_state_snapshot()
        mock_job_repo.get_job.return_value = {"research_done": False, "status": "IN-PROGRESS"}

        service.execute("job-1", "topic")
        mock_job_repo.mark_awaiting_input.assert_called_once_with("job-1")
        mock_job_repo.mark_complete.assert_not_called()

    def test_marks_halted_on_failure_when_research_done(
        self, service, mock_agent, mock_job_repo, mocker
    ):
        mocker.patch("Server.services.blog_job_service.time.sleep")
        mocker.patch("Server.services.blog_job_service.delete_checkpoint_thread")
        mock_agent.stream.side_effect = RuntimeError("LLM error")
        mock_job_repo.get_job.return_value = {"research_done": True, "status": "IN-PROGRESS"}
        mock_agent.get_state.return_value = make_state_snapshot()

        with pytest.raises(RuntimeError):
            service.execute("job-1", "topic")

        mock_job_repo.mark_halted.assert_called_once_with("job-1")
        mock_job_repo.mark_failed.assert_not_called()

    def test_marks_failed_on_failure_when_no_research(
        self, service, mock_agent, mock_job_repo, mocker
    ):
        mocker.patch("Server.services.blog_job_service.time.sleep")
        mock_delete = mocker.patch(
            "Server.services.blog_job_service.delete_checkpoint_thread"
        )
        mock_agent.stream.side_effect = RuntimeError("LLM error")
        mock_job_repo.get_job.return_value = {"research_done": False, "status": "IN-PROGRESS"}
        mock_agent.get_state.return_value = make_state_snapshot(evidence=None)

        with pytest.raises(RuntimeError):
            service.execute("job-1", "topic")

        mock_job_repo.mark_failed.assert_called_once_with("job-1")
        mock_delete.assert_called_once()
        mock_job_repo.mark_halted.assert_not_called()

    def test_thread_id_equals_job_id_in_stream_config(
        self, service, mock_agent, mock_job_repo, mocker
    ):
        """Linchpin invariant: thread_id == job_id ties checkpoint to DB row."""
        mock_agent.stream.return_value = iter([])
        mock_agent.get_state.return_value = make_state_snapshot()
        mock_job_repo.get_job.return_value = {"research_done": False, "status": "IN-PROGRESS"}

        service.execute("my-job-id", "topic")
        _, stream_call_args, _ = mock_agent.stream.mock_calls[0]
        config = stream_call_args[1]
        assert config["configurable"]["thread_id"] == "my-job-id"


# ---------------------------------------------------------------------------
# prepare_retry / retry
# ---------------------------------------------------------------------------


class TestRetry:
    def test_prepare_retry_calls_mark_in_progress(self, service, mock_job_repo):
        service.prepare_retry("job-1")
        mock_job_repo.mark_in_progress.assert_called_once_with("job-1")

    def test_retry_streams_with_none_input(self, service, mock_agent, mock_job_repo, mocker):
        mocker.patch(
            "Server.services.blog_job_service.blog_output_path",
            return_value="/blogs/test.md",
        )
        mock_agent.stream.return_value = iter([])
        mock_agent.get_state.return_value = make_state_snapshot(plan=make_plan_obj())
        mock_job_repo.get_job.return_value = {"research_done": True, "status": "IN-PROGRESS"}

        service.retry("job-1")
        _, stream_call_args, _ = mock_agent.stream.mock_calls[0]
        assert stream_call_args[0] is None  # input_state is None for retry

    def test_retry_returns_to_awaiting_input_if_still_interrupted(
        self, service, mock_agent, mock_job_repo
    ):
        mock_agent.stream.return_value = iter([{"__interrupt__": []}])
        mock_agent.get_state.return_value = make_state_snapshot()
        mock_job_repo.get_job.return_value = {"research_done": True, "status": "IN-PROGRESS"}

        service.retry("job-1")
        mock_job_repo.mark_awaiting_input.assert_called_once_with("job-1")


# ---------------------------------------------------------------------------
# prepare_decision / submit_decision
# ---------------------------------------------------------------------------


class TestDecision:
    def test_prepare_decision_calls_mark_in_progress(self, service, mock_job_repo):
        service.prepare_decision("job-1")
        mock_job_repo.mark_in_progress.assert_called_once_with("job-1")

    def test_submit_decision_streams_with_command(
        self, service, mock_agent, mock_job_repo, mocker
    ):
        mocker.patch(
            "Server.services.blog_job_service.blog_output_path",
            return_value="/blogs/test.md",
        )
        mock_agent.stream.return_value = iter([])
        mock_agent.get_state.return_value = make_state_snapshot(plan=make_plan_obj())
        mock_job_repo.get_job.return_value = {"research_done": True, "status": "IN-PROGRESS"}

        service.submit_decision("job-1", "proceed")
        _, stream_call_args, _ = mock_agent.stream.mock_calls[0]
        input_state = stream_call_args[0]
        assert isinstance(input_state, Command)
        assert input_state.resume == "proceed"

    def test_restore_awaiting_input_calls_repo(self, service, mock_job_repo):
        service.restore_awaiting_input("job-1")
        mock_job_repo.mark_awaiting_input.assert_called_once_with("job-1")


# ---------------------------------------------------------------------------
# mark_interrupted
# ---------------------------------------------------------------------------


class TestMarkInterrupted:
    def test_halts_when_research_done(self, service, mock_job_repo):
        mock_job_repo.get_job.return_value = {"research_done": True}
        service.mark_interrupted("job-1")
        mock_job_repo.mark_halted.assert_called_once_with("job-1")
        mock_job_repo.mark_failed.assert_not_called()

    def test_fails_when_no_research(self, service, mock_job_repo):
        mock_job_repo.get_job.return_value = {"research_done": False}
        service.mark_interrupted("job-1")
        mock_job_repo.mark_failed.assert_called_once_with("job-1")
        mock_job_repo.mark_halted.assert_not_called()

    def test_noop_when_job_missing(self, service, mock_job_repo):
        mock_job_repo.get_job.return_value = None
        service.mark_interrupted("job-1")
        mock_job_repo.mark_halted.assert_not_called()
        mock_job_repo.mark_failed.assert_not_called()


# ---------------------------------------------------------------------------
# Static helpers: _plan_title, _task_count_from_plan
# ---------------------------------------------------------------------------


class TestPlanHelpers:
    def test_plan_title_from_pydantic_object(self):
        plan = make_plan_obj()
        assert BlogJobService._plan_title(plan) == "Test Blog"

    def test_plan_title_from_dict(self):
        plan_dict = {"blog_title": "Dict Blog"}
        assert BlogJobService._plan_title(plan_dict) == "Dict Blog"

    def test_plan_title_from_none(self):
        assert BlogJobService._plan_title(None) is None

    def test_task_count_from_pydantic_plan(self):
        plan = make_plan_obj(num_tasks=3)
        assert BlogJobService._task_count_from_plan(plan) == 3

    def test_task_count_from_dict_plan(self):
        plan_dict = {"tasks": [{"id": 1}, {"id": 2}]}
        assert BlogJobService._task_count_from_plan(plan_dict) == 2

    def test_task_count_from_none(self):
        assert BlogJobService._task_count_from_plan(None) is None


# ---------------------------------------------------------------------------
# _execute_graph stage mapping
# ---------------------------------------------------------------------------


class TestExecuteGraphStageMapping:
    """Verify that node updates trigger the correct stage DB calls."""

    def _run(self, service, mock_agent, mock_job_repo, chunks, is_fresh=True):
        mock_agent.stream.return_value = iter(chunks)
        mock_job_repo.get_job.return_value = {
            "research_done": False, "status": "IN-PROGRESS"
        }
        input_state = {"topic": "t"} if is_fresh else None
        config = {"configurable": {"thread_id": "job-1"}}
        return service._execute_graph(input_state, config, "job-1")

    def test_queries_generator_chunk_sets_researching(
        self, service, mock_agent, mock_job_repo
    ):
        self._run(service, mock_agent, mock_job_repo, [{"queries_generator": {}}])
        mock_job_repo.update_stage.assert_any_call("job-1", STAGE_RESEARCHING)

    def test_research_node_chunk_marks_research_done_and_sets_planning(
        self, service, mock_agent, mock_job_repo
    ):
        self._run(service, mock_agent, mock_job_repo, [{"research_node": {}}])
        mock_job_repo.mark_research_done.assert_called_once_with("job-1")
        mock_job_repo.update_stage.assert_any_call("job-1", STAGE_PLANNING)

    def test_review_gate_proceed_sets_writing_sections(
        self, service, mock_agent, mock_job_repo
    ):
        chunk = {"review_gate": {"research_decision": "proceed"}}
        self._run(service, mock_agent, mock_job_repo, [chunk])
        mock_job_repo.update_stage.assert_any_call("job-1", STAGE_WRITING_SECTIONS)

    def test_review_gate_redo_does_not_set_writing_sections(
        self, service, mock_agent, mock_job_repo
    ):
        chunk = {"review_gate": {"research_decision": "redo"}}
        self._run(service, mock_agent, mock_job_repo, [chunk])
        stage_calls = [c.args for c in mock_job_repo.update_stage.call_args_list]
        assert (STAGE_WRITING_SECTIONS,) not in [
            (c[1],) for c in stage_calls
        ]

    def test_worker_chunks_set_synthesizing_when_all_complete(
        self, service, mock_agent, mock_job_repo
    ):
        plan = make_plan_obj(num_tasks=2)
        chunks = [
            {"orchestrator": {"plan": plan}},
            {"review_gate": {"research_decision": "proceed"}},
            {"worker": {}},
            {"worker": {}},  # second worker completes the count
        ]
        self._run(service, mock_agent, mock_job_repo, chunks)
        mock_job_repo.update_stage.assert_any_call("job-1", STAGE_SYNTHESIZING)

    def test_interrupt_chunk_returns_true(
        self, service, mock_agent, mock_job_repo
    ):
        interrupted = self._run(
            service, mock_agent, mock_job_repo, [{"__interrupt__": []}]
        )
        assert interrupted is True

    def test_normal_completion_returns_false(
        self, service, mock_agent, mock_job_repo
    ):
        interrupted = self._run(service, mock_agent, mock_job_repo, [])
        assert interrupted is False

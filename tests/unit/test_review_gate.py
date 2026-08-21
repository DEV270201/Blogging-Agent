from unittest.mock import MagicMock

import pytest

from Server.nodes.review_gate import _attr, _sections, review_gate, route_after_review
from Server.state import Bullet, Plan, Task


def make_plan_obj():
    return Plan(
        blog_title="Test Blog",
        blog_description="desc",
        evidence_coverage="partial",
        research_note="needs more sources",
        tasks=[
            Task(
                id=1,
                title="Section One",
                description="desc",
                goal="goal",
                bullets=[
                    Bullet(text="b1", bullet_type="prose"),
                    Bullet(text="b2", bullet_type="prose"),
                ],
                target_words=150,
            )
        ],
        audience="developers",
    )


def make_plan_dict():
    return {
        "blog_title": "Test Blog",
        "evidence_coverage": "partial",
        "research_note": "needs more sources",
        "tasks": [{"title": "Section One", "goal": "goal"}],
    }


class TestAttr:
    def test_reads_from_pydantic_object(self):
        plan = make_plan_obj()
        assert _attr(plan, "blog_title") == "Test Blog"

    def test_reads_from_plain_dict(self):
        plan = make_plan_dict()
        assert _attr(plan, "blog_title") == "Test Blog"

    def test_returns_default_when_obj_is_none(self):
        assert _attr(None, "blog_title", "fallback") == "fallback"

    def test_returns_default_on_missing_key_in_dict(self):
        assert _attr({}, "nonexistent", "default") == "default"

    def test_returns_default_on_missing_attr_in_object(self):
        class Obj:
            pass
        assert _attr(Obj(), "missing", "default") == "default"


class TestSections:
    def test_sections_from_pydantic_plan(self):
        plan = make_plan_obj()
        result = _sections(plan)
        assert result == [{"title": "Section One", "goal": "goal"}]

    def test_sections_from_dict_plan(self):
        plan = make_plan_dict()
        result = _sections(plan)
        assert result == [{"title": "Section One", "goal": "goal"}]

    def test_sections_from_empty_tasks(self):
        assert _sections({"tasks": []}) == []

    def test_sections_from_none_plan(self):
        assert _sections(None) == []


class TestReviewGate:
    def _state(self, coverage, attempts=0, evidence=None):
        plan = make_plan_obj()
        # Override coverage
        object.__setattr__(plan, "evidence_coverage", coverage)
        return {
            "plan": plan,
            "evidence": {"evidence": evidence or []},
            "research_attempts": attempts,
        }

    def test_proceeds_on_sufficient_coverage_without_interrupt(self, mocker):
        mock_interrupt = mocker.patch("Server.nodes.review_gate.interrupt")
        state = self._state("sufficient")
        result = review_gate(state)
        assert result == {"research_decision": "proceed"}
        mock_interrupt.assert_not_called()

    def test_proceeds_without_interrupt_when_at_retry_cap(self, mocker):
        from Server.config import RESEARCH_RETRY_CAP

        mock_interrupt = mocker.patch("Server.nodes.review_gate.interrupt")
        state = self._state("partial", attempts=RESEARCH_RETRY_CAP)
        result = review_gate(state)
        assert result == {"research_decision": "proceed"}
        mock_interrupt.assert_not_called()

    def test_interrupts_on_partial_coverage_under_cap(self, mocker):
        mock_interrupt = mocker.patch(
            "Server.nodes.review_gate.interrupt", return_value="proceed"
        )
        state = self._state("partial", attempts=0)
        result = review_gate(state)
        mock_interrupt.assert_called_once()
        assert result == {"research_decision": "proceed"}

    def test_interrupts_on_insufficient_coverage(self, mocker):
        mock_interrupt = mocker.patch(
            "Server.nodes.review_gate.interrupt", return_value="proceed"
        )
        state = self._state("insufficient", attempts=0)
        review_gate(state)
        mock_interrupt.assert_called_once()

    def test_redo_increments_research_attempts(self, mocker):
        mocker.patch("Server.nodes.review_gate.interrupt", return_value="redo")
        state = self._state("partial", attempts=0)
        result = review_gate(state)
        assert result == {"research_decision": "redo", "research_attempts": 1}

    def test_redo_increments_from_nonzero(self, mocker):
        mocker.patch("Server.nodes.review_gate.interrupt", return_value="redo")
        state = self._state("partial", attempts=1)
        result = review_gate(state)
        assert result["research_attempts"] == 2

    def test_interrupt_payload_includes_coverage_and_counts(self, mocker):
        mock_interrupt = mocker.patch(
            "Server.nodes.review_gate.interrupt", return_value="proceed"
        )
        evidence = [{"title": "src", "url": "http://example.com"}]
        state = self._state("partial", attempts=1, evidence=evidence)
        review_gate(state)
        payload = mock_interrupt.call_args[0][0]
        assert payload["coverage"] == "partial"
        assert payload["evidence_count"] == 1
        assert payload["attempts"] == 1

    def test_plan_dict_is_handled_on_checkpoint_reload(self, mocker):
        """After a checkpoint reload, Plan may be a plain dict — _attr must handle it."""
        mocker.patch(
            "Server.nodes.review_gate.interrupt", return_value="proceed"
        )
        plan_dict = make_plan_dict()
        state = {
            "plan": plan_dict,
            "evidence": {"evidence": []},
            "research_attempts": 0,
        }
        result = review_gate(state)
        assert result["research_decision"] == "proceed"


class TestRouteAfterReview:
    def test_redo_returns_queries_generator(self):
        state = {"research_decision": "redo", "plan": make_plan_obj(), "topic": "t", "evidence": {"evidence": []}}
        result = route_after_review(state)
        assert result == "queries_generator"

    def test_proceed_calls_fanout(self, mocker):
        mock_fanout = mocker.patch("Server.nodes.review_gate.fanout", return_value=["send1"])
        state = {"research_decision": "proceed", "plan": make_plan_obj(), "topic": "t", "evidence": {"evidence": []}}
        result = route_after_review(state)
        mock_fanout.assert_called_once_with(state)
        assert result == ["send1"]

import pytest
from pydantic import ValidationError

from Server.state import (
    Bullet,
    EvidencePack,
    Plan,
    QueriesGeneratorDecision,
    Task,
)


def make_bullet(**kwargs):
    defaults = {"text": "Some bullet text", "bullet_type": "prose"}
    return {**defaults, **kwargs}


def make_task(**kwargs):
    defaults = {
        "id": 1,
        "title": "Section title",
        "description": "What this section covers",
        "goal": "Reader understands X",
        "bullets": [make_bullet(), make_bullet()],
        "target_words": 150,
    }
    return {**defaults, **kwargs}


def make_plan(**kwargs):
    defaults = {
        "blog_title": "Test Blog",
        "blog_description": "A test blog description",
        "evidence_coverage": "sufficient",
        "research_note": "",
        "tasks": [make_task()],
        "audience": "developers",
    }
    return {**defaults, **kwargs}


class TestBullet:
    def test_valid_bullet_types(self):
        for bt in ("cited_fact", "prose", "pattern", "code_example", "verify"):
            b = Bullet(text="text", bullet_type=bt)
            assert b.bullet_type == bt

    def test_invalid_bullet_type_raises(self):
        with pytest.raises(ValidationError):
            Bullet(text="text", bullet_type="opinion")


class TestTask:
    def test_min_two_bullets(self):
        t = Task(**make_task())
        assert len(t.bullets) == 2

    def test_fewer_than_two_bullets_raises(self):
        with pytest.raises(ValidationError):
            Task(**make_task(bullets=[make_bullet()]))

    def test_more_than_five_bullets_raises(self):
        with pytest.raises(ValidationError):
            Task(**make_task(bullets=[make_bullet()] * 6))

    def test_exactly_five_bullets_is_valid(self):
        t = Task(**make_task(bullets=[make_bullet()] * 5))
        assert len(t.bullets) == 5


class TestPlan:
    def test_valid_plan(self):
        p = Plan(**make_plan())
        assert p.blog_title == "Test Blog"

    def test_min_one_task(self):
        p = Plan(**make_plan(tasks=[make_task()]))
        assert len(p.tasks) == 1

    def test_zero_tasks_raises(self):
        with pytest.raises(ValidationError):
            Plan(**make_plan(tasks=[]))

    def test_more_than_four_tasks_raises(self):
        with pytest.raises(ValidationError):
            Plan(**make_plan(tasks=[make_task(id=i) for i in range(5)]))

    def test_exactly_four_tasks_is_valid(self):
        p = Plan(**make_plan(tasks=[make_task(id=i) for i in range(4)]))
        assert len(p.tasks) == 4

    def test_valid_coverage_literals(self):
        for cov in ("sufficient", "partial", "insufficient"):
            p = Plan(**make_plan(evidence_coverage=cov))
            assert p.evidence_coverage == cov

    def test_invalid_coverage_raises(self):
        with pytest.raises(ValidationError):
            Plan(**make_plan(evidence_coverage="unknown"))


class TestQueriesGeneratorDecision:
    def test_min_three_queries(self):
        q = QueriesGeneratorDecision(queries=["a", "b", "c"])
        assert len(q.queries) == 3

    def test_fewer_than_three_raises(self):
        with pytest.raises(ValidationError):
            QueriesGeneratorDecision(queries=["a", "b"])

    def test_more_than_five_raises(self):
        with pytest.raises(ValidationError):
            QueriesGeneratorDecision(queries=["a", "b", "c", "d", "e", "f"])

    def test_exactly_five_is_valid(self):
        q = QueriesGeneratorDecision(queries=["a", "b", "c", "d", "e"])
        assert len(q.queries) == 5


class TestEvidencePack:
    def test_defaults_to_empty_list(self):
        ep = EvidencePack()
        assert ep.evidence == []

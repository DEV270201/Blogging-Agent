from langgraph.types import Send

from Server.nodes.fanout import fanout
from Server.state import Bullet, Plan, Task


def make_plan(num_tasks: int) -> Plan:
    tasks = [
        Task(
            id=i,
            title=f"Section {i}",
            description="desc",
            goal="goal",
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


def make_state(num_tasks: int) -> dict:
    return {
        "plan": make_plan(num_tasks),
        "topic": "Test topic",
        "evidence": {"evidence": [{"title": "src", "url": "http://example.com"}]},
    }


class TestFanout:
    def test_creates_one_send_per_task(self):
        state = make_state(3)
        result = fanout(state)
        assert len(result) == 3

    def test_send_targets_worker_node(self):
        state = make_state(2)
        result = fanout(state)
        for send in result:
            assert isinstance(send, Send)
            assert send.node == "worker"

    def test_send_payload_contains_task_as_dict(self):
        state = make_state(1)
        result = fanout(state)
        payload = result[0].arg
        assert "task" in payload
        assert isinstance(payload["task"], dict)
        assert payload["task"]["title"] == "Section 0"

    def test_send_payload_contains_topic(self):
        state = make_state(1)
        result = fanout(state)
        assert result[0].arg["topic"] == "Test topic"

    def test_send_payload_contains_plan_as_dict(self):
        state = make_state(1)
        result = fanout(state)
        plan_payload = result[0].arg["plan"]
        assert isinstance(plan_payload, dict)
        assert plan_payload["blog_title"] == "Test Blog"

    def test_send_payload_contains_evidence_list(self):
        state = make_state(1)
        result = fanout(state)
        evidence = result[0].arg["evidence"]
        assert isinstance(evidence, list)
        assert evidence[0]["url"] == "http://example.com"

    def test_number_of_sends_matches_plan_tasks(self):
        for n in (1, 2, 4):
            state = make_state(n)
            assert len(fanout(state)) == n

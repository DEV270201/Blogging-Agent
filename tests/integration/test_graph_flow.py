"""Integration tests for the LangGraph agent graph.

Uses MemorySaver (in-process checkpointer) and mocked LLMs/Tavily/file-IO
so no external services are required. Tests verify graph wiring and the
critical thread_id == job_id invariant.
"""

import pytest

from Server.state import Bullet, EvidenceItem, EvidencePack, Plan, Task


def make_plan(coverage="sufficient", num_tasks=1) -> Plan:
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
            target_words=100,
        )
        for i in range(num_tasks)
    ]
    return Plan(
        blog_title="Test Blog",
        blog_description="desc",
        evidence_coverage=coverage,
        research_note="" if coverage == "sufficient" else "limited sources",
        tasks=tasks,
        audience="developers",
    )


@pytest.fixture
def memory_agent(mocker, tmp_path):
    """Real graph with MemorySaver and all external calls mocked."""
    from langgraph.checkpoint.memory import MemorySaver

    from Server.graph import build_blog_agent
    from Server.state import QueriesGeneratorDecision

    # queries_generator
    mock_q_llm = mocker.patch("Server.nodes.queries_generator.llm")
    mock_q_llm.with_structured_output.return_value.invoke.return_value = (
        QueriesGeneratorDecision(queries=["q1", "q2", "q3"])
    )

    # research_node: patch the internal search helper and the LLM
    mocker.patch(
        "Server.nodes.research._search_all_queries",
        return_value=[
            {"title": "Source 1", "url": "http://a.com", "snippet": "s", "published_at": None, "source": None},
            {"title": "Source 2", "url": "http://b.com", "snippet": "s", "published_at": None, "source": None},
            {"title": "Source 3", "url": "http://c.com", "snippet": "s", "published_at": None, "source": None},
        ],
    )
    mock_r_llm = mocker.patch("Server.nodes.research.llm")
    mock_r_llm.with_structured_output.return_value.invoke.return_value = EvidencePack(
        evidence=[
            EvidenceItem(title="Source 1", url="http://a.com"),
            EvidenceItem(title="Source 2", url="http://b.com"),
            EvidenceItem(title="Source 3", url="http://c.com"),
        ]
    )

    # orchestrator
    mock_o_llm = mocker.patch("Server.nodes.orchestrator.llm")
    mock_o_llm.with_structured_output.return_value.invoke.return_value = make_plan(
        coverage="sufficient", num_tasks=1
    )

    # worker
    mock_w_llm = mocker.patch("Server.nodes.worker.llm")
    worker_msg = mocker.MagicMock()
    worker_msg.content = "## Section 0\n\nGenerated content."
    mock_w_llm.invoke.return_value = worker_msg

    # synthesizer file write
    mocker.patch(
        "Server.nodes.synthesizer.blog_output_path",
        return_value=tmp_path / "test_blog.md",
    )

    return build_blog_agent(MemorySaver())


class TestGraphCompilation:
    def test_graph_compiles_with_memory_saver(self, memory_agent):
        assert memory_agent is not None

    def test_graph_has_expected_node_names(self, memory_agent):
        node_names = set(memory_agent.get_graph().nodes.keys())
        expected = {
            "queries_generator",
            "research_node",
            "orchestrator",
            "review_gate",
            "worker",
            "synthesizer",
        }
        assert expected.issubset(node_names)


class TestHappyPath:
    def test_completes_and_produces_final_blog(self, memory_agent):
        job_id = "test-job-happy"
        config = {"configurable": {"thread_id": job_id}}
        chunks = list(memory_agent.stream({"topic": "Test topic"}, config, stream_mode="updates"))
        final_state = memory_agent.get_state(config)
        assert final_state.values.get("final_blog") is not None

    def test_thread_id_equals_job_id_in_checkpoint(self, memory_agent):
        """Linchpin: the config thread_id ties the checkpoint to the DB row."""
        job_id = "linchpin-job-id"
        config = {"configurable": {"thread_id": job_id}}
        list(memory_agent.stream({"topic": "Test topic"}, config, stream_mode="updates"))
        state = memory_agent.get_state(config)
        # State must be retrievable by the same job_id
        assert state.values.get("final_blog") is not None

    def test_sections_accumulated_for_single_task(self, memory_agent):
        job_id = "sections-job"
        config = {"configurable": {"thread_id": job_id}}
        list(memory_agent.stream({"topic": "Test topic"}, config, stream_mode="updates"))
        state = memory_agent.get_state(config)
        sections = state.values.get("sections", [])
        assert len(sections) == 1


class TestInterruptPath:
    def test_interrupts_on_partial_coverage(self, mocker, tmp_path):
        """When the orchestrator returns partial coverage, the gate pauses the graph."""
        from langgraph.checkpoint.memory import MemorySaver
        from Server.graph import build_blog_agent
        from Server.state import QueriesGeneratorDecision

        mock_q_llm = mocker.patch("Server.nodes.queries_generator.llm")
        mock_q_llm.with_structured_output.return_value.invoke.return_value = (
            QueriesGeneratorDecision(queries=["q1", "q2", "q3"])
        )
        mocker.patch("Server.nodes.research._search_all_queries", return_value=[])
        mock_r_llm = mocker.patch("Server.nodes.research.llm")
        mock_r_llm.with_structured_output.return_value.invoke.return_value = EvidencePack()

        mock_o_llm = mocker.patch("Server.nodes.orchestrator.llm")
        mock_o_llm.with_structured_output.return_value.invoke.return_value = make_plan(
            coverage="partial", num_tasks=1
        )
        mocker.patch(
            "Server.nodes.synthesizer.blog_output_path",
            return_value=tmp_path / "test.md",
        )

        agent = build_blog_agent(MemorySaver())
        job_id = "interrupt-job"
        config = {"configurable": {"thread_id": job_id}}
        chunks = list(agent.stream({"topic": "Test"}, config, stream_mode="updates"))
        interrupt_chunks = [c for c in chunks if "__interrupt__" in c]
        assert len(interrupt_chunks) == 1

    def test_resume_with_proceed_completes_blog(self, mocker, tmp_path):
        """After an interrupt, resuming with 'proceed' should complete the blog."""
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.types import Command
        from Server.graph import build_blog_agent
        from Server.state import QueriesGeneratorDecision

        mock_q_llm = mocker.patch("Server.nodes.queries_generator.llm")
        mock_q_llm.with_structured_output.return_value.invoke.return_value = (
            QueriesGeneratorDecision(queries=["q1", "q2", "q3"])
        )
        mocker.patch("Server.nodes.research._search_all_queries", return_value=[])
        mock_r_llm = mocker.patch("Server.nodes.research.llm")
        mock_r_llm.with_structured_output.return_value.invoke.return_value = EvidencePack()

        mock_o_llm = mocker.patch("Server.nodes.orchestrator.llm")
        mock_o_llm.with_structured_output.return_value.invoke.return_value = make_plan(
            coverage="partial", num_tasks=1
        )
        mock_w_llm = mocker.patch("Server.nodes.worker.llm")
        msg = mocker.MagicMock()
        msg.content = "## Section\n\nContent."
        mock_w_llm.invoke.return_value = msg
        mocker.patch(
            "Server.nodes.synthesizer.blog_output_path",
            return_value=tmp_path / "test.md",
        )

        agent = build_blog_agent(MemorySaver())
        job_id = "resume-job"
        config = {"configurable": {"thread_id": job_id}}

        # First run — pauses at interrupt
        list(agent.stream({"topic": "Test"}, config, stream_mode="updates"))
        # Resume with proceed
        list(agent.stream(Command(resume="proceed"), config, stream_mode="updates"))

        state = agent.get_state(config)
        assert state.values.get("final_blog") is not None

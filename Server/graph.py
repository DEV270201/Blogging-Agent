from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from Server.nodes import (
    fanout,
    orchestrator,
    queries_generator,
    research_node,
    synthesizer,
    worker,
)
from Server.state import BlogState

TRANSIENT_RETRY = RetryPolicy(
    max_attempts=2,
    initial_interval=1.0,
    backoff_factor=2.0,
)
SYNTHESIZER_RETRY = RetryPolicy(max_attempts=2, initial_interval=1.0)


def build_blog_agent(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(BlogState)
    graph.add_node("queries_generator", queries_generator, retry=TRANSIENT_RETRY)
    graph.add_node("research_node", research_node, retry=TRANSIENT_RETRY)
    graph.add_node("orchestrator", orchestrator, retry=TRANSIENT_RETRY)
    graph.add_node("worker", worker, retry=TRANSIENT_RETRY)
    graph.add_node("synthesizer", synthesizer, retry=SYNTHESIZER_RETRY)
    graph.add_edge(START, "queries_generator")
    graph.add_edge("queries_generator", "research_node")
    graph.add_edge("research_node", "orchestrator")
    graph.add_conditional_edges("orchestrator", fanout, ["worker"])
    graph.add_edge("worker", "synthesizer")
    graph.add_edge("synthesizer", END)
    return graph.compile(checkpointer=checkpointer)

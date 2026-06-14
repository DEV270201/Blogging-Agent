from langgraph.graph import START, StateGraph, END
from Server.state import BlogState
from Server.nodes import orchestrator, worker, synthesizer, fanout


def build_blog_agent():
    graph = StateGraph(BlogState)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("worker", worker)
    graph.add_node("synthesizer", synthesizer)
    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", fanout, ["worker"])
    graph.add_edge("worker", "synthesizer")
    graph.add_edge("synthesizer", END)
    return graph.compile()


blog_agent = build_blog_agent()

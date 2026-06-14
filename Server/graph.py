from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from Server.checkpointer import checkpointer
from Server.nodes import chat_node, manage_memory
from Server.state import ChatState
from Server.tools import tools


def build_chatbot():
    graph = StateGraph(ChatState)
    graph.add_node("manage_memory", manage_memory)
    graph.add_node("tools", ToolNode(tools=tools))
    graph.add_node("chat_node", chat_node)
    graph.add_edge(START, "manage_memory")
    graph.add_edge("manage_memory", "chat_node")
    graph.add_conditional_edges("chat_node", tools_condition)
    graph.add_edge("tools", "chat_node")
    return graph.compile(checkpointer=checkpointer)


chatbot = build_chatbot()

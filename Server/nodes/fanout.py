from langgraph.types import Send
from Server.state import BlogState

def fanout(state: BlogState):
    print(f"Fanning out tasks......")
    return [
        Send("worker", {
            "task": task,
            "topic": state["topic"],
            "plan": state["plan"],
        }) for task in state["plan"].tasks
    ]


from langgraph.types import Send
from Server.state import BlogState

def fanout(state: BlogState):
    print(f"Fanning out tasks......")
    return [
        Send("worker", {
            "task": task.model_dump(),
            "topic": state["topic"],
            "plan": state["plan"].model_dump(),
            "evidence": [e.model_dump() for e in state.get("evidence", {}).get("evidence", [])],
        }) for task in state["plan"].tasks
    ]


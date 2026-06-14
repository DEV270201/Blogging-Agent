from langchain_core.messages import SystemMessage, HumanMessage
from Server.model import llm
from Server.state import BlogState, Plan


def orchestrator(state: BlogState) -> BlogState:
    print(f"Orchestrating tasks......")
    plan = llm.with_structured_output(Plan).invoke([
        SystemMessage(
            content=""" You are a smart assistant that generates an outline for writing a blog post.
            Create a plan with 3-4 sections that would be appropriate for the blog post on the given topic.
            """
            ),
            HumanMessage(
                content=f"Please generate a plan for the blog post on the topic: {state['topic']}"
            )
    ])

    print(f"Plan: {plan}")
    return {"plan": plan}
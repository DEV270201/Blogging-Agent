from langchain_core.messages import SystemMessage, HumanMessage
from Server.model import llm
from Server.state import BlogState


def worker(payload: dict) -> BlogState:
    print(f"Working on task......")
    task = payload["task"]
    topic = payload["topic"]
    plan = payload["plan"]

    blog_title = plan.blog_title
    blog_description = plan.blog_description
    section_title = task.title
    section_description = task.description

    section_md = llm.invoke([
        SystemMessage(
            content=f"""You are a smart assistant that writes a section of a blog post.
            Write the section in clean and concise Markdown format.
            The section should be written in a way that is easy to understand and follow.
            """
        ),
        HumanMessage(
            content=f"""
            Blog: {blog_title}\n
            Topic: {topic}\n\n
            Section: {section_title}\n
            Brief: {section_description}\n\n
            write only about the section you are provided with in Markdown format.
            Do not include any other text or formatting.
            """
        )
    ]).content.strip()
    
    print(f"Section: {section_md}")
    print("--------------------------------")

    return {"sections": [section_md]}


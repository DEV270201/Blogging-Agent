from langchain_core.messages import SystemMessage, HumanMessage
from Server.model import llm
from Server.state import BlogState, EvidenceItem


def worker(payload: dict) -> BlogState:
    print(f"Working on task......")
    task = payload["task"]
    topic = payload["topic"]
    plan = payload["plan"]
    evidence = [EvidenceItem(**e) for e in payload["evidence"]]
    blog_title = plan["blog_title"]
    blog_description = plan["blog_description"]
    section_title = task["title"]
    section_description = task["description"]
    goal = task["goal"]
    bullets = task["bullets"]
    target_words = task["target_words"]
    audience = plan["audience"]

    evidence_str = "\n".join([f"{e['title']}\n{e['url']}\n{e['snippet']}" for e in evidence])

    section_md = llm.invoke([
        SystemMessage(
            content=f"""
            You are a senior technical writer and developer advocate. Write ONE section of a technical blog post in Markdown.\n\n
            The Research Evidence Pack is provided to you. Use appropriate evidence from the pack to make the section more accurate and informative.\n\n
            Hard constraints:\n
            - Make sure you frame the section in a way that a non-technical reader can also understand and learn from it.
            - Follow the provided Goal and cover ALL Bullets in order (do not skip or merge bullets).\n
            - Stay close to the Target words (±10%).\n
            - Output ONLY the section content in Markdown (no blog title H1, no extra commentary).\n\n
            Technical quality bar:\n
            - Be precise and implementation-oriented (developers should be able to understand and apply it).\n
            - Prefer concrete details over abstractions: APIs, data structures, protocols, and exact terms.\n
            - When relevant, include at least one of:\n
              * a small code snippet (minimal, correct, and idiomatic)\n
              * a tiny example input/output\n
              * a checklist of steps\n
              * a flow or an architecture diagram described in text (e.g., 'Flow: A -> B -> C') and include short description of the diagram in the text.\n
            - Explain trade-offs briefly (performance, cost, complexity, reliability).\n
            - When giving multiple approaches, explain the trade-offs between them.
            - Call out edge cases / failure modes and what to do about them.\n
            - When relevant, include scenarios and examples to make it more engaging and understandable.
            - If you mention a best practice, add the 'why' in one sentence.\n\n
            - Include citations to the evidence sources in the text where appropriate.
            - DO NOT INVENT ANY NEW INFORMATION. Only use the information from the evidence.
            Markdown style:\n
            - Start with a '## <Section Title>' heading.\n
            - Use short paragraphs, bullet lists where helpful, and code fences for code.\n
            - Avoid fluff. Avoid marketing language.\n
            - Highlight important points in bold.
            - Use emojis to make the text more engaging.
            - If you include code, keep it focused on the bullet being addressed.\n
            """
        ),
        HumanMessage(
            content=f"""
            Blog: {blog_title}\n
            Topic: {topic}\n
            Goal: {goal}\n
            Bullets: {bullets}\n
            Target words: {target_words}\n
            Audience: {audience}\n
            Section: {section_title}\n
            Brief: {section_description}\n\n
            Research Evidence: {evidence_str}\n\n
            write only about the section you are provided with in Markdown format.
            Do not include any other text or formatting.
            """
        )
    ]).content.strip()
    
    print(f"Section: {section_md}")
    print("--------------------------------")

    return {"sections": [section_md]}


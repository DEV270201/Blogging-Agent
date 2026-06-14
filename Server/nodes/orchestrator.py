from langchain_core.messages import SystemMessage, HumanMessage
from Server.model import llm
from Server.state import BlogState, Plan


def orchestrator(state: BlogState) -> BlogState:
    print(f"Orchestrating tasks......")
    evidence = state.get("evidence", {}).get("evidence", []) or []
    evidence_str = "\n".join([f"{e['title']}\n{e['url']}\n{e['snippet']}" for e in evidence])
    print(f"Evidence: {evidence_str}")
    print("================================================")
    plan = llm.with_structured_output(Plan).invoke([
        SystemMessage(
            content=""" You are a senior technical writer and developer advocate. Your job is to produce a highly actionable outline for a technical blog post.\n\n
                    Hard requirements:\n
                    - Create 3-4 well-focused sections (tasks) that fits a technical blog post based on the given topic.\n
                    - Each section must include:\n
                      1) goal (1 sentence: what the reader can do/understand after the section)\n
                      2) 3–5 bullets that are concrete, specific, and non-overlapping (about what to cover, how to cover etc)\n
                      3) target word count (120–450)\n
                    Make it technical (not generic information) but easy to understand:\n
                    - Assume the reader can be on the technical side or not technical side; use correct terminology and easy to understand language.\n
                    - In case of design/engineering problems, Prefer this structure: problem → intuition → approach → implementation → 
                    trade-offs → testing/observability.\n
                    - Explicitly include at least ONE of the following somewhere in the sections as bullets wherever required\n
                      * a minimal working example (MWE) or code sketch\n
                      * edge cases / failure modes\n
                      * performance/cost considerations\n
                      * security/privacy considerations (if relevant)\n
                      * debugging tips / observability (logs, metrics, traces)\n
                    - Avoid vague bullets. Every bullet should state what to build/compare/measure/verify.\n\n
                    Ordering guidance:\n
                    - Build core concepts before advanced details.\n
                    - Include one section for common mistakes and how to avoid them if required.\n
                    - End with a practical summary/checklist and next steps.\n\n
                    - The Research Evidence Pack is provided to you. Use it to make the plan more accurate and informative.
                    - If evidence is empty or insufficient, create a plan that transparently says "insufficient sources"
                      and includes only what can be supported.
                    - DO NOT INVENT ANY NEW INFORMATION. Only use the information from the evidence.
                    Output must strictly match the Plan schema.
            """
            ),
            HumanMessage(
                content=f"Please generate a plan for the blog post on the topic: {state['topic']}\n\n RESEARCH EVIDENCE====:\n {evidence_str}"
            )
    ])

    print(f"Plan: {plan}")
    return {"plan": plan}
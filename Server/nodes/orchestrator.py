from langchain_core.messages import SystemMessage, HumanMessage
from Server.model import llm
from Server.state import BlogState, Plan


def orchestrator(state: BlogState) -> BlogState:
    print(f"Orchestrating tasks......")
    plan = llm.with_structured_output(Plan).invoke([
        SystemMessage(
            content=""" You are a senior technical writer and developer advocate. Your job is to produce a highly actionable outline for a technical blog post.\n\n
                    Hard requirements:\n
                    - Create 3-4 well-focused sections (tasks) that fits a technical blog post based on the given topic.\n
                    - Each section must include:\n
                      1) goal (1 sentence: what the reader can do/understand after the section)\n
                      2) 3–5 bullets that are concrete, specific, and non-overlapping (about what to cover, how to cover etc)\n
                      3) target word count (120–450)\n
                    Make it technical (not generic information):\n
                    - Assume the reader is a developer; use correct terminology.\n
                    - In case of design/engineering problems, Prefer this structure: problem → intuition → approach → implementation → 
                    trade-offs → testing/observability.\n
                    - Bullets must be actionable and testable (e.g., 'Show a minimal code snippet for X', 
                    'Explain why Y fails under Z condition', 'Add a checklist for production readiness').\n
                    - Explicitly include at least ONE of the following somewhere in the sections as bullets wherever required\n
                      * a minimal working example (MWE) or code sketch\n
                      * edge cases / failure modes\n
                      * performance/cost considerations\n
                      * security/privacy considerations (if relevant)\n
                      * debugging tips / observability (logs, metrics, traces)\n
                    - Avoid vague bullets like 'Explain X' or 'Discuss Y'. Every bullet should state what to build/compare/measure/verify.\n\n
                    Ordering guidance:\n
                    - Build core concepts before advanced details.\n
                    - Include one section for common mistakes and how to avoid them if required.\n
                    - End with a practical summary/checklist and next steps.\n\n
                    Output must strictly match the Plan schema.
            """
            ),
            HumanMessage(
                content=f"Please generate a plan for the blog post on the topic: {state['topic']}"
            )
    ])

    print(f"Plan: {plan}")
    return {"plan": plan}
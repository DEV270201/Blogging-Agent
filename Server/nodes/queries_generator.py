from langchain_core.messages import HumanMessage, SystemMessage

from Server.model import llm
from Server.state import BlogState, QueriesGeneratorDecision

QUERIES_GENERATOR_SYSTEM = """You are a search engine module for a technical blog planner.
Decide what search queries are needed so the blog can be accurate, citable, and safe to publish.

RULES FOR GENERATING SEARCH QUERIES:
- Output exactly 3–5 high-signal search queries (never more than 5).
- Queries should be scoped (avoid generic queries like just "AI" or "LLM").
- Queries should be non-overlapping and specific to the topic.
- If the topic names a framework, library, cloud provider, or product, include queries aimed at:
  * official documentation
  * official blog / release notes
  * production or deployment guides from the vendor or maintainers
- Prefer queries that return verifiable facts (APIs, config, deployment steps, limits).
- Include a comparison query only if the topic explicitly requires comparing tools or vendors.
- If the user asked for "last week/this week/latest", reflect that constraint IN THE QUERIES.
"""

MAX_SEARCH_QUERIES = 5


def queries_generator(state: BlogState) -> BlogState:
    print("Generating search queries......")
    topic = state["topic"]
    decision = llm.with_structured_output(QueriesGeneratorDecision).invoke(
        [
            SystemMessage(content=QUERIES_GENERATOR_SYSTEM),
            HumanMessage(
                content=f"Topic: {topic}\nGenerate search queries for a citable technical blog on this topic."
            ),
        ]
    )

    queries = decision.queries[:MAX_SEARCH_QUERIES]
    print(f"Search queries: {queries}")

    return {"search_queries": queries}

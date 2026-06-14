from langchain_core.messages import SystemMessage, HumanMessage
from Server.model import llm
from Server.state import BlogState, QueriesGeneratorDecision

QUERIES_GENERATOR_SYSTEM = """You are a search engine module for a technical blog planner.
Decide what kind of search queries are needed to write the blog post on the given topic so the reader can find the blog useful and informative.

RULES FOR GENERATING SEARCH QUERIES:    
- Output 3–10 high-signal search queries.
- Queries should be scoped (avoid generic queries like just "AI" or "LLM"). 
- Queries should be non-overlapping and specific/related to the topic.
- If user asked for "last week/this week/latest", reflect that constraint IN THE QUERIES.
"""

def queries_generator(state: BlogState) -> BlogState:
    print(f"Generating search queries......")
    topic = state["topic"]
    queries_generator = llm.with_structured_output(QueriesGeneratorDecision)
    queries = queries_generator.invoke(
        [
            SystemMessage(content=QUERIES_GENERATOR_SYSTEM),
            HumanMessage(content=f"Topic: {topic}\nPlease generate search queries for the blog post on the topic."),
        ]
    )

    print(f"Search queries: {queries.queries}")

    return {"search_queries": queries.queries}

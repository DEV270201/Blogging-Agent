import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage, SystemMessage

from Server.model import llm
from Server.state import BlogState, EvidencePack

MAX_RESULTS_PER_QUERY = 3

RESEARCH_SYSTEM = """You are a research synthesizer for technical writing.

Given raw web search results, produce a list of EvidenceItem objects.

Rules:
- Prefer relevant + authoritative sources in this order:
  1) official documentation and vendor/maintainer blogs
  2) reputable technical outlets and engineering blogs
  3) community posts (only if nothing better exists)
- Snippets must contain only facts present in the raw result — do NOT infer or extrapolate.
- If a published date is explicitly present in the result payload, keep it as YYYY-MM-DD; otherwise use None.
- Summarize long snippets to under 200 words while preserving the factual claim(s).
- Do NOT invent titles, URLs, dates, or claims not supported by the raw results.
- If a result is irrelevant or too vague, omit it rather than guessing.
"""


# def _trim_snippet(text: str, max_words: int = MAX_SNIPPET_WORDS) -> str:
#     if not text:
#         return ""
#     words = text.split()
#     if len(words) <= max_words:
#         return text
#     return " ".join(words[:max_words]) + "..."


def _tavily_search(query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> List[dict]:
    tool = TavilySearch(max_results=max_results)
    results = tool.invoke({"query": query})
    print(f"Tavily results for {query!r}: {len(results.get('results', []) or [])} hits")

    normalized: list[dict] = []
    for r in results.get("results", []) or []:
        normalized.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or "",
                "published_at": r.get("published_date") or r.get("published_at") or None,
                "source": r.get("source") or None,
            }
        )
    
    print(f"Normalized results: {normalized}")
    print("================================================")
    return normalized


def _search_all_queries(queries: list[str]) -> list[dict]:
    raw_results: list[dict] = []
    if not queries:
        return raw_results

    with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as executor:
        futures = {executor.submit(_tavily_search, q): q for q in queries}
        for future in as_completed(futures):
            try:
                raw_results.extend(future.result())
            except Exception as exc:
                query = futures[future]
                print(f"Tavily search failed for {query!r}: {exc}")

    return raw_results


def research_node(state: BlogState) -> BlogState:
    print("Researching......")
    queries = state.get("search_queries", []) or []
    raw_results = _search_all_queries(queries)

    empty_pack = {"evidence": []}
    if not raw_results:
        return {"evidence": empty_pack}

    dedup: dict[str, dict] = {}
    for item in raw_results:
        if item["url"]:
            dedup[item["url"]] = item

    if not dedup:
        return {"evidence": empty_pack}

    pack = llm.with_structured_output(EvidencePack).invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(
                content=(
                    "Raw search results (deduplicated by URL):\n"
                    f"DATA====:\n{json.dumps(list(dedup.values()), indent=2)}"
                )
            ),
        ]
    )

    print("================================================")
    print(f"Evidence pack: {len(pack.evidence)} items")
    print("================================================")

    return {"evidence": pack.model_dump()}

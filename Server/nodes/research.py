def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    
    tool = TavilySearchResults(max_results=max_results)
    results = tool.invoke({"query": query})
    print(f"Raw results: {results}")
    results = results.get("results", [])
    normalized: list[dict] = []
    for r in results or []:
        normalized.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or "",
                "published_at": r.get("published_date") or r.get("published_at") or None,
                "source": r.get("source") or None,
            }
        )
    print("================================================")
    print(f"Normalized results: {normalized}")
    print("================================================")
    return normalized


RESEARCH_SYSTEM = """You are a research synthesizer for technical writing.

Given raw web search results, produce a list of EvidenceItem objects.

Rules:
- Prefer relevant + authoritative sources (company blogs, docs, reputable outlets).
- If a published date is explicitly present in the result payload, keep it as YYYY-MM-DD and if None then let it be None.
- If the Snippets are too long then make them shorter by removing the unnecessary content. Make sure the snippets are under 200 words.
- Do NOT INVENT ANY INFORMATION. Only use the information from the snippets.
"""

def research_node(state: BlogState) -> BlogState:
    print(f"Researching......")
    # take the search queries from state
    queries = (state.get("search_queries", []) or [])
    max_results = 3

    raw_results: list[dict] = []

    for q in queries:
        raw_results.extend(_tavily_search(q, max_results=max_results))

    if not raw_results:
        return {"evidence": []}

    # Deduplicate by URL and make sure it is not empty
    dedup = {}
    for e in raw_results:
        if e["url"]:
            dedup[e["url"]] = e

    extractor = llm.with_structured_output(EvidencePack)
    pack = extractor.invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"This is the raw results from the search queries:\n DATA====:\n {json.dumps(dedup, indent=4)}"),
        ]
    )
    
    print("================================================")
    print(f"Evidence pack: {pack.evidence}")
    print("================================================")

    return {"evidence": pack.model_dump()}
from langchain_core.messages import HumanMessage, SystemMessage

from Server.model import llm
from Server.state import BlogState, Plan

ORCHESTRATOR_SYSTEM = """You are a senior technical writer and developer advocate.
Produce an actionable, trustworthy outline for a technical blog post.

Hard requirements:
- Create 1–4 well-focused sections (tasks) based on evidence coverage (see below).
- Each section must include:
  1) goal (1 sentence: what the reader can do/understand after the section)
  2) 2–5 bullets, each with a bullet_type (see schema)
  3) target word count (80–450; use 80–200 when evidence is insufficient)

Evidence-first planning (CRITICAL):
- A Research Evidence Pack is provided. Assess coverage hint before planning:
  * sufficient — enough authoritative sources for framework/API/production claims
  * partial — some sources, but not every section can be fully cited
  * insufficient — empty or too weak for product-specific factual claims

- Set evidence_coverage and research_note on the Plan:
  * sufficient: evidence_coverage="sufficient", research_note="" (empty string)
  * partial: evidence_coverage="partial", research_note explains what is well-sourced vs general guidance
  * insufficient: evidence_coverage="insufficient", research_note warns that framework-specific claims are omitted

- Section count by coverage:
  * sufficient → 3–4 sections, target_words 150–450 per section
  * partial → 2–3 sections, target_words 120–300 per section
  * insufficient → 1–2 sections, target_words 80–200 per section

- blog_description must honestly reflect coverage (do not oversell depth).

Bullet types (assign one per bullet):
- cited_fact: product/framework/API/production claim — ONLY if evidence supports it
- prose: conceptual explanation, no code required
- pattern: general software engineering guidance (retries, observability, testing mindset)
- code_example: implementation walkthrough — ONLY if evidence contains the code OR mark as generic pattern context
- verify: tell the reader what to confirm in official docs (use when evidence lacks a specific fact)

Rules:
- Do NOT plan cited_fact or code_example bullets for framework-specific facts absent from evidence.
- Replace unsupported factual bullets with verify or pattern bullets.
- Include edge cases, trade-offs, or observability as prose/pattern bullets where appropriate — not code in every section.
- Avoid vague bullets. Every bullet should state what to explain, compare, measure, or verify.
- Build core concepts before advanced details; end with a practical summary when coverage allows.
- Assume a mixed audience (technical and non-technical); plan for clear, accessible explanations.

Output must strictly match the Plan schema.
"""


def _coverage_hint(evidence_count: int) -> str:
    if evidence_count == 0:
        return "insufficient"
    if evidence_count < 3:
        return "partial"
    return "sufficient"


def orchestrator(state: BlogState) -> BlogState:
    print("Orchestrating tasks......")
    evidence = state.get("evidence", {}).get("evidence", []) or []
    evidence_count = len(evidence)
    evidence_str = "\n\n".join(
        f"Title: {e['title']}\nURL: {e['url']}\nSnippet: {e.get('snippet') or ''}"
        for e in evidence
    )
    hint = _coverage_hint(evidence_count)

    print(f"Evidence items: {evidence_count} ({hint})")
    print("================================================")

    plan = llm.with_structured_output(Plan).invoke(
        [
            SystemMessage(content=ORCHESTRATOR_SYSTEM),
            HumanMessage(
                content=(
                    f"Topic: {state['topic']}\n"
                    f"Evidence items: {evidence_count}\n"
                    f"Coverage hint: {hint}\n\n"
                    f"RESEARCH EVIDENCE====:\n{evidence_str or '(none)'}"
                )
            ),
        ]
    )

    print(f"Plan: {plan}")
    return {"plan": plan}

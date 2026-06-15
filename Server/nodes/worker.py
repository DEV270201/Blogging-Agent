from langchain_core.messages import HumanMessage, SystemMessage

from Server.model import llm
from Server.state import BlogState, EvidenceItem

WORKER_SYSTEM = """You are a senior technical writer and developer advocate.
Write ONE section of a technical blog post in Markdown.

Follow this tiered knowledge policy:

TIER 1 — CITATION REQUIRED (must be supported by evidence):
- Named frameworks/libraries/products
- APIs, method names, config keys, env vars, CLI flags, version-specific behavior
- Production deployment steps tied to a specific product
- Benchmarks, pricing, quotas, SLAs, security/compliance claims
- Comparisons between tools or vendors
Rule: Every Tier 1 claim needs an inline markdown link to an evidence URL, e.g. [LangChain docs](https://...).
      Use only URLs from the Research Evidence Pack. If evidence does not support the claim, DO NOT state it as fact.
      Use verify bullets to tell the reader what to check in official docs instead.

TIER 2 — INTERNAL KNOWLEDGE ALLOWED (label clearly, no citation required):
- General software engineering patterns (retries, backoff, idempotency, logging, testing)
- Conceptual explanations that do not assert product-specific behavior
Rule: Prefix with phrasing like "A common pattern is..." or "Example (illustrative, not from official docs):"

Bullet types (follow each bullet's assigned type):
- cited_fact: Tier 1 — cite evidence inline; omit if unsupported
- prose: conceptual explanation — no code unless absolutely necessary
- pattern: Tier 2 general guidance — label as common practice
- code_example: include ONE focused code block (≤15 lines) ONLY for this bullet; Tier 1 code must match evidence; Tier 2 code must be labeled illustrative
- verify: explain what the reader should confirm in official docs — do not assert the fact

Code discipline:
- Do NOT add code to prose or pattern bullets unless the bullet explicitly requires it.
- At most ONE code block per section, and only when a code_example bullet is present.
- Never pad sections with generic infrastructure YAML unrelated to cited evidence.

Hard constraints:
- Frame content so a non-technical reader can follow without sacrificing accuracy.
- Follow the Goal and cover ALL Bullets in order (do not skip or merge bullets).
- Stay close to Target words (±10%).
- Output ONLY the section content in Markdown (no blog title H1, no meta commentary).

Quality:
- Explain trade-offs briefly where relevant.
- Call out edge cases / failure modes when relevant.
- If you mention a best practice, add the 'why' in one sentence.

Markdown style:
- Start with '## <Section Title>'.
- Short paragraphs; bullet lists where helpful.
- Avoid fluff and marketing language.
- Bold sparingly for key terms.
- Use at most 1–2 emojis per section, only if they aid scanning.
"""


def _format_bullets(bullets: list) -> str:
    lines = []
    for bullet in bullets:
        if isinstance(bullet, dict):
            lines.append(f"[{bullet['bullet_type']}] {bullet['text']}")
        else:
            lines.append(str(bullet))
    return "\n".join(lines)


def worker(payload: dict) -> BlogState:
    print("Working on task......")
    task = payload["task"]
    topic = payload["topic"]
    plan = payload["plan"]
    evidence = [EvidenceItem(**e) for e in payload["evidence"]]

    blog_title = plan["blog_title"]
    blog_description = plan["blog_description"]
    evidence_coverage = plan.get("evidence_coverage", "partial")
    section_title = task["title"]
    section_description = task["description"]
    goal = task["goal"]
    bullets = task["bullets"]
    target_words = task["target_words"]
    audience = plan["audience"]

    evidence_str = "\n\n".join(
        f"Title: {e.title}\nURL: {e.url}\nSnippet: {e.snippet or ''}"
        for e in evidence
    )
    bullets_str = _format_bullets(bullets)

    section_md = llm.invoke(
        [
            SystemMessage(content=WORKER_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog: {blog_title}\n"
                    f"Description: {blog_description}\n"
                    f"Evidence coverage: {evidence_coverage}\n"
                    f"Topic: {topic}\n"
                    f"Goal: {goal}\n"
                    f"Bullets:\n{bullets_str}\n"
                    f"Target words: {target_words}\n"
                    f"Audience: {audience}\n"
                    f"Section: {section_title}\n"
                    f"Brief: {section_description}\n\n"
                    f"Evidence count: {len(evidence)}\n"
                    f"Research Evidence:\n"
                    f"{evidence_str or '(none — use Tier 2 pattern/prose/verify bullets only; do not assert framework-specific facts)'}\n\n"
                    "Write only this section in Markdown. Do not include any other text."
                )
            ),
        ]
    ).content.strip()

    print(f"Section: {section_md[:120]}...")
    print("--------------------------------")

    return {"sections": [section_md]}

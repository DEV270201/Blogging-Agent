import re
from pathlib import Path

from Server.config import BLOGS_DIR
from Server.state import BlogState, Plan


def _safe_filename(title: str) -> str:
    slug = title.lower().replace(" ", "_")
    slug = re.sub(r'[<>:"/\\|?*]', "", slug)
    return slug[:200] + ".md"


def blog_output_path(title: str) -> Path:
    return BLOGS_DIR / _safe_filename(title)


def _research_banner(plan: Plan) -> str:
    note = (plan.research_note or "").strip()
    coverage = plan.evidence_coverage

    if coverage == "sufficient" and not note:
        return ""

    if note:
        label = coverage.replace("_", " ")
        return f"> **Research note ({label} coverage):** {note}\n\n"

    if coverage == "insufficient":
        return (
            "> **Research note (insufficient coverage):** "
            "External sources were limited for this topic. "
            "Framework-specific details are omitted unless cited below.\n\n"
        )

    if coverage == "partial":
        return (
            "> **Research note (partial coverage):** "
            "Some sections rely on general engineering guidance. "
            "Product-specific claims are cited where possible.\n\n"
        )

    return ""


def synthesizer(state: BlogState) -> BlogState:
    print("Synthesizing blog......")

    plan = state["plan"]
    title = plan.blog_title
    banner = _research_banner(plan)
    body = "\n\n".join(state["sections"]).strip()

    final_md = f"# {title}\n\n{banner}{body}\n"

    output_path = blog_output_path(title)
    output_path.write_text(final_md, encoding="utf-8")

    return {"final_blog": final_md}

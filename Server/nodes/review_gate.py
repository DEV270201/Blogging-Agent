"""Human-in-the-loop review gate.

Sits between the orchestrator (which builds the Plan) and the worker fan-out
(which drafts the sections). When the orchestrator judges research coverage as
weak (``partial``/``insufficient``) the gate interrupts the graph and surfaces
the plan to the user, who chooses to proceed with limited information or to
re-research (loop back to ``queries_generator``). ``sufficient`` coverage — or
having exhausted ``RESEARCH_RETRY_CAP`` re-research rounds — proceeds without
asking.

The gate node re-executes from the top on resume, so everything before
``interrupt()`` is a pure read of the plan/evidence and is safe to run twice.
``research_attempts`` is incremented exactly once per confirmed "redo".
"""

from langgraph.types import interrupt

from Server.config import RESEARCH_RETRY_CAP
from Server.nodes.fanout import fanout
from Server.state import BlogState


def _attr(obj, name, default=None):
    """Read a field from a Plan/Task that may be a Pydantic object (live) or a
    plain dict (after being reloaded from the checkpoint)."""
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


def _sections(plan) -> list[dict]:
    tasks = _attr(plan, "tasks", []) or []
    return [
        {"title": _attr(t, "title", ""), "goal": _attr(t, "goal", "")}
        for t in tasks
    ]


def review_gate(state: BlogState) -> BlogState:
    plan = state["plan"]
    coverage = _attr(plan, "evidence_coverage")
    attempts = state.get("research_attempts", 0)

    print(f"Review gate: coverage={coverage}, attempts={attempts}")

    # Strong enough coverage, or we have already re-researched up to the cap:
    # proceed straight to drafting without bothering the user.
    if coverage == "sufficient" or attempts >= RESEARCH_RETRY_CAP:
        return {"research_decision": "proceed"}

    evidence = state.get("evidence", {}).get("evidence", []) or []
    decision = interrupt(
        {
            "type": "research_review",
            "coverage": coverage,
            "title": _attr(plan, "blog_title", ""),
            "sections": _sections(plan),
            "research_note": _attr(plan, "research_note", "") or "",
            "evidence_count": len(evidence),
            "attempts": attempts,
            "max_attempts": RESEARCH_RETRY_CAP,
            "sources": [
                {"title": e.get("title", ""), "url": e.get("url", "")}
                for e in evidence
            ],
        }
    )

    if decision == "redo":
        return {"research_decision": "redo", "research_attempts": attempts + 1}
    return {"research_decision": "proceed"}


def route_after_review(state: BlogState):
    """On "redo" loop back for fresh queries + research + re-plan; otherwise
    fan out to the workers using the existing Send-based fan-out."""
    if state.get("research_decision") == "redo":
        return "queries_generator"
    return fanout(state)

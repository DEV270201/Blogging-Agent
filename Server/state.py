from typing import Annotated, Literal, Optional, TypedDict
import operator

from pydantic import BaseModel, Field

BulletType = Literal["cited_fact", "prose", "pattern", "code_example", "verify"]
EvidenceCoverage = Literal["sufficient", "partial", "insufficient"]


class Bullet(BaseModel):
    text: str = Field(..., description="What to cover in this bullet point.")
    bullet_type: BulletType = Field(
        ...,
        description=(
            "cited_fact: product/framework claim requiring a source; "
            "prose: conceptual explanation without code; "
            "pattern: general engineering guidance; "
            "code_example: implementation walkthrough; "
            "verify: tell the reader what to confirm in official docs."
        ),
    )


class Task(BaseModel):
    id: int = Field(..., description="The id of the task")
    title: str = Field(..., description="The title of the task")
    description: str = Field(
        ...,
        description="What this section covers and how it fits the blog.",
    )
    goal: str = Field(
        ...,
        description="One sentence describing what the reader should be able to do/understand after this section.",
    )
    bullets: list[Bullet] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="2–5 concrete, non-overlapping subpoints with an assigned bullet_type.",
    )
    target_words: int = Field(
        ...,
        description="Target word count for this section (80–450). Use lower end when evidence is weak.",
    )


class Plan(BaseModel):
    blog_title: str = Field(..., description="The title of the blog")
    blog_description: str = Field(
        ...,
        description="Description of the blog; must reflect evidence coverage honestly.",
    )
    evidence_coverage: EvidenceCoverage = Field(
        ...,
        description="sufficient | partial | insufficient — based on the Research Evidence Pack.",
    )
    research_note: str = Field(
        ...,
        description=(
            "Short reader-facing disclaimer about source coverage. "
            "Use empty string when evidence_coverage is sufficient."
        ),
    )
    tasks: list[Task] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="3–4 sections. Use 1–2 when evidence is insufficient.",
    )
    audience: str = Field(..., description="Who this blog is for.")


class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[str] = None


class EvidencePack(BaseModel):
    evidence: list[EvidenceItem] = Field(default_factory=list)


class QueriesGeneratorDecision(BaseModel):
    queries: list[str] = Field(
        default_factory=list,
        min_length=3,
        max_length=5,
        description="3–5 high-signal search queries.",
    )


class BlogState(TypedDict):
    plan: Plan
    topic: str
    search_queries: list[str]
    evidence: EvidencePack
    sections: Annotated[list[str], operator.add]
    final_blog: str

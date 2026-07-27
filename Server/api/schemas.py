"""Request/response models for the blog agent HTTP API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CreateJobRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="What the blog should be about.",
    )

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("topic must be at least 10 non-whitespace characters")
        return cleaned


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str
    stage: str


class JobStatusResponse(BaseModel):
    id: str
    topic: str
    status: str
    stage: str
    recoverable: bool
    research_done: bool
    final_blog_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]
    total: int
    limit: int
    offset: int


class BlogContentResponse(BaseModel):
    job_id: str
    title: Optional[str] = None
    content: str
    final_blog_path: Optional[str] = None


class DecisionRequest(BaseModel):
    decision: Literal["proceed", "redo"] = Field(
        ...,
        description="'proceed' to draft with current research, 'redo' to re-research.",
    )


class ReviewSection(BaseModel):
    title: str = ""
    goal: str = ""


class ReviewSource(BaseModel):
    title: str = ""
    url: str = ""


class ResearchReviewResponse(BaseModel):
    """The pending human-in-the-loop review for a job paused after planning."""

    job_id: str
    pending: bool = Field(
        ..., description="True when the job is awaiting a research-review decision."
    )
    coverage: Optional[str] = Field(
        None, description="'partial' | 'insufficient' — why the agent paused."
    )
    title: Optional[str] = None
    sections: list[ReviewSection] = Field(default_factory=list)
    research_note: str = ""
    evidence_count: int = 0
    attempts: int = 0
    max_attempts: int = 0
    sources: list[ReviewSource] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = Field(..., description="'ok' when the service is ready to serve.")
    database: str = Field(..., description="'connected' or 'unavailable'.")


class ErrorResponse(BaseModel):
    detail: str

"""Request/response models for the blog agent HTTP API."""

from datetime import datetime
from typing import Optional

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


class HealthResponse(BaseModel):
    status: str = Field(..., description="'ok' when the service is ready to serve.")
    database: str = Field(..., description="'connected' or 'unavailable'.")


class ErrorResponse(BaseModel):
    detail: str

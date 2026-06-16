"""FastAPI server exposing the LangGraph blog agent to the React client.

Run with:
    uv run uvicorn Server.api.app:app --reload
or:
    uv run python -m Server.api.app
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from Server.config import API_HOST, API_MAX_WORKERS, API_PORT, CORS_ORIGINS
from Server.persistence.database import check_connection, close_pool
from Server.persistence.job_repository import JOB_HALTED
from Server.services.blog_job_service import (
    BlogJobService,
    get_blog_job_service,
)
from Server.api.schemas import (
    BlogContentResponse,
    CreateJobRequest,
    HealthResponse,
    JobCreatedResponse,
    JobListResponse,
    JobStatusResponse,
)

logger = logging.getLogger("blog_agent.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify the database is reachable and wire up the service before serving traffic."""
    logging.basicConfig(level=logging.INFO)

    # Building the service initializes the connection pool, runs the checkpointer
    # setup and creates the blog_jobs table. check_connection() then proves the DB
    # is actually reachable — if either step fails the app fails to start and never
    # accepts requests.
    service = get_blog_job_service()
    check_connection()
    logger.info("Database connected and schema ready.")

    app.state.service = service
    app.state.executor = ThreadPoolExecutor(
        max_workers=API_MAX_WORKERS,
        thread_name_prefix="blog-job",
    )
    logger.info("Blog agent API ready (max_workers=%s).", API_MAX_WORKERS)

    try:
        yield
    finally:
        app.state.executor.shutdown(wait=False, cancel_futures=True)
        close_pool()
        logger.info("Blog agent API shut down.")


app = FastAPI(
    title="Blog Agent API",
    description="HTTP API over a LangGraph agent that researches and writes technical blogs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- dependencies ------------------------------------------------------------


def get_service() -> BlogJobService:
    return app.state.service


def get_executor() -> ThreadPoolExecutor:
    return app.state.executor


def _run_job_in_background(service: BlogJobService, job_id: str, topic: str) -> None:
    """Execute a fresh job, logging (not raising) failures since this runs detached.

    Failure state is already recorded in the database by the service, so the client
    learns about it via the status endpoint.
    """
    try:
        service.execute(job_id, topic)
    except Exception:
        logger.exception("Blog generation failed for job %s", job_id)


def _retry_job_in_background(service: BlogJobService, job_id: str) -> None:
    try:
        service.retry(job_id)
    except Exception:
        logger.exception("Blog retry failed for job %s", job_id)


# --- routes ------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    try:
        check_connection()
        return HealthResponse(status="ok", database="connected")
    except Exception:
        logger.exception("Health check failed: database unreachable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )


@app.post(
    "/jobs",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
)
def create_job(
    request: CreateJobRequest,
    service: BlogJobService = Depends(get_service),
    executor: ThreadPoolExecutor = Depends(get_executor),
) -> JobCreatedResponse:
    """Start generating a blog. Returns immediately with a job id to poll."""
    job_id = service.create(request.topic)
    executor.submit(_run_job_in_background, service, job_id, request.topic)
    job = service.get_job(job_id)
    return JobCreatedResponse(
        job_id=job_id,
        status=job["status"],
        stage=job["stage"],
    )


@app.get("/jobs", response_model=JobListResponse, tags=["jobs"])
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: BlogJobService = Depends(get_service),
) -> JobListResponse:
    """List jobs newest-first for a dashboard view."""
    jobs, total = service.list_jobs(limit, offset)
    return JobListResponse(
        jobs=[JobStatusResponse(**job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["jobs"])
def get_job_status(
    job_id: UUID,
    service: BlogJobService = Depends(get_service),
) -> JobStatusResponse:
    """Poll the current status and stage of a job."""
    job = service.get_job(str(job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(**job)


@app.get("/jobs/{job_id}/blog", response_model=BlogContentResponse, tags=["jobs"])
def get_job_blog(
    job_id: UUID,
    service: BlogJobService = Depends(get_service),
) -> BlogContentResponse:
    """Fetch the generated Markdown once a job is complete."""
    result = service.get_blog_content(str(job_id))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not result["content"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Blog is not ready yet",
        )
    return BlogContentResponse(
        job_id=str(job_id),
        title=result["title"],
        content=result["content"],
        final_blog_path=result["path"],
    )


@app.post(
    "/jobs/{job_id}/retry",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
)
def retry_job(
    job_id: UUID,
    service: BlogJobService = Depends(get_service),
    executor: ThreadPoolExecutor = Depends(get_executor),
) -> JobCreatedResponse:
    """Resume a halted, recoverable job from its last checkpoint."""
    job_id_str = str(job_id)
    job = service.get_job(job_id_str)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job["status"] != JOB_HALTED or not job["recoverable"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job is not in a resumable state",
        )

    executor.submit(_retry_job_in_background, service, job_id_str)
    return JobCreatedResponse(
        job_id=job_id_str,
        status=job["status"],
        stage=job["stage"],
    )


def main() -> None:
    import uvicorn

    uvicorn.run("Server.api.app:app", host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    main()

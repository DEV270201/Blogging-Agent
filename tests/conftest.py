"""Shared pytest fixtures for backend tests.

Nothing here touches a real database, LLM, or filesystem — all external
dependencies are replaced with MagicMocks so tests run fully offline.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from Server.persistence.job_repository import JobRepository
from Server.services.blog_job_service import BlogJobService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DATETIME = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


def make_job(overrides: dict | None = None) -> dict:
    """Return a minimal valid job dict, with optional field overrides."""
    base = {
        "id": "test-job-id",
        "topic": "A valid blog topic here",
        "status": "IN-PROGRESS",
        "stage": "queued",
        "recoverable": False,
        "research_done": False,
        "final_blog_path": None,
        "created_at": SAMPLE_DATETIME,
        "updated_at": SAMPLE_DATETIME,
    }
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Database / repository mocks
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cursor():
    cur = MagicMock()
    cur.rowcount = 0
    return cur


@pytest.fixture
def mock_pool(mock_cursor):
    """Psycopg pool mock that wires up the nested context-manager pattern used
    by JobRepository:  with pool.connection() as conn: with conn.cursor() as cur:
    """
    pool = MagicMock()
    conn = MagicMock()
    # conn.cursor() -> context manager -> mock_cursor
    conn.cursor.return_value.__enter__.return_value = mock_cursor
    # pool.connection() -> context manager -> conn
    pool.connection.return_value.__enter__.return_value = conn
    return pool


@pytest.fixture
def job_repo(mock_pool, mocker):
    """Real JobRepository backed by a mocked pool (no real DB calls)."""
    mocker.patch("Server.persistence.job_repository.setup_job_table")
    return JobRepository(mock_pool)


# ---------------------------------------------------------------------------
# Agent mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_agent():
    """MagicMock standing in for a compiled LangGraph StateGraph.

    Configure .stream.return_value and .get_state.return_value per test.
    """
    agent = MagicMock()
    # Default: stream produces no chunks (empty run), get_state returns empty values.
    agent.stream.return_value = iter([])
    state_snapshot = MagicMock()
    state_snapshot.values = {}
    state_snapshot.tasks = []
    agent.get_state.return_value = state_snapshot
    return agent


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_job_repo():
    """Full MagicMock of JobRepository — used by service-layer tests."""
    repo = MagicMock(spec=JobRepository)
    repo.get_job.return_value = make_job()
    return repo


@pytest.fixture
def service(mock_agent, mock_job_repo):
    """Real BlogJobService with mocked agent and mocked repository."""
    return BlogJobService(agent=mock_agent, job_repo=mock_job_repo)


# ---------------------------------------------------------------------------
# API / HTTP fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_service():
    """Full MagicMock of BlogJobService — used by API integration tests."""
    svc = MagicMock(spec=BlogJobService)
    svc.instance_id = "test-instance-id"
    svc.get_job.return_value = make_job()
    svc.list_jobs.return_value = ([], 0)
    return svc


@pytest.fixture
def mock_executor():
    """MagicMock ThreadPoolExecutor — submit succeeds by default."""
    from concurrent.futures import ThreadPoolExecutor

    executor = MagicMock(spec=ThreadPoolExecutor)
    executor.submit.return_value = MagicMock()
    return executor


@pytest.fixture
def app_client(mocker, mock_service, mock_executor):
    """FastAPI TestClient with all external dependencies mocked.

    The lifespan is short-circuited by patching get_blog_job_service and
    check_connection. Routes receive mock_service and mock_executor via
    dependency overrides.
    """
    from fastapi.testclient import TestClient

    from Server.api.app import app, get_executor, get_service

    mocker.patch("Server.api.app.get_blog_job_service", return_value=mock_service)
    mocker.patch("Server.api.app.check_connection")

    app.dependency_overrides[get_service] = lambda: mock_service
    app.dependency_overrides[get_executor] = lambda: mock_executor

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()

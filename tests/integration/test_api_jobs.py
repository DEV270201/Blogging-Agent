"""Integration tests for all job-related HTTP routes.

Uses FastAPI TestClient with mock service and executor — no real DB or LLM.
"""

from datetime import datetime, timezone

import pytest

from Server.persistence.job_repository import DBRepositoryError, JOB_AWAITING_INPUT, JOB_HALTED

SAMPLE_DT = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


def sample_job(**overrides):
    base = {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "topic": "A valid blog topic here",
        "status": "IN-PROGRESS",
        "stage": "queued",
        "recoverable": False,
        "research_done": False,
        "final_blog_path": None,
        "created_at": SAMPLE_DT,
        "updated_at": SAMPLE_DT,
    }
    return {**base, **overrides}


VALID_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
VALID_TOPIC = "A valid blog topic here for testing"


# ---------------------------------------------------------------------------
# POST /jobs
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_returns_202_on_valid_topic(self, app_client, mock_service, mock_executor):
        mock_service.create.return_value = VALID_JOB_ID
        mock_service.get_job.return_value = sample_job()
        response = app_client.post("/jobs", json={"topic": VALID_TOPIC})
        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == VALID_JOB_ID
        assert "status" in data
        assert "stage" in data

    def test_returns_422_on_short_topic(self, app_client):
        response = app_client.post("/jobs", json={"topic": "short"})
        assert response.status_code == 422

    def test_returns_422_on_whitespace_only_topic(self, app_client):
        response = app_client.post("/jobs", json={"topic": "         "})
        assert response.status_code == 422

    def test_returns_503_when_executor_rejected(self, app_client, mock_service, mock_executor):
        mock_service.create.return_value = VALID_JOB_ID
        mock_executor.submit.side_effect = RuntimeError("executor shutting down")
        response = app_client.post("/jobs", json={"topic": VALID_TOPIC})
        assert response.status_code == 503
        mock_service.mark_interrupted.assert_called_once_with(VALID_JOB_ID)

    def test_submit_called_with_job_id(self, app_client, mock_service, mock_executor):
        mock_service.create.return_value = VALID_JOB_ID
        mock_service.get_job.return_value = sample_job()
        app_client.post("/jobs", json={"topic": VALID_TOPIC})
        assert mock_executor.submit.called


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_returns_200_with_job_list(self, app_client, mock_service):
        mock_service.list_jobs.return_value = ([sample_job()], 1)
        response = app_client.get("/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["jobs"]) == 1

    def test_passes_limit_and_offset_to_service(self, app_client, mock_service):
        mock_service.list_jobs.return_value = ([], 0)
        app_client.get("/jobs?limit=5&offset=10")
        mock_service.list_jobs.assert_called_once_with(5, 10)


# ---------------------------------------------------------------------------
# GET /jobs/{id}
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    def test_returns_200_when_found(self, app_client, mock_service):
        mock_service.get_job.return_value = sample_job()
        response = app_client.get(f"/jobs/{VALID_JOB_ID}")
        assert response.status_code == 200
        assert response.json()["id"] == VALID_JOB_ID

    def test_returns_404_when_not_found(self, app_client, mock_service):
        mock_service.get_job.return_value = None
        response = app_client.get(f"/jobs/{VALID_JOB_ID}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs/{id}/blog
# ---------------------------------------------------------------------------


class TestGetJobBlog:
    def test_returns_200_with_content(self, app_client, mock_service):
        mock_service.get_blog_content.return_value = {
            "content": "# Test Blog\n\nContent here.",
            "title": "Test Blog",
            "path": "/blogs/test_blog.md",
        }
        response = app_client.get(f"/jobs/{VALID_JOB_ID}/blog")
        assert response.status_code == 200
        assert "content" in response.json()

    def test_returns_404_when_job_not_found(self, app_client, mock_service):
        mock_service.get_blog_content.return_value = None
        response = app_client.get(f"/jobs/{VALID_JOB_ID}/blog")
        assert response.status_code == 404

    def test_returns_409_when_blog_not_ready(self, app_client, mock_service):
        mock_service.get_blog_content.return_value = {
            "content": None,
            "title": None,
            "path": None,
        }
        response = app_client.get(f"/jobs/{VALID_JOB_ID}/blog")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /jobs/{id}/retry
# ---------------------------------------------------------------------------


class TestRetryJob:
    def test_returns_202_for_halted_recoverable_job(
        self, app_client, mock_service, mock_executor
    ):
        mock_service.get_job.side_effect = [
            sample_job(status=JOB_HALTED, recoverable=True),
            sample_job(status="IN-PROGRESS"),
        ]
        response = app_client.post(f"/jobs/{VALID_JOB_ID}/retry")
        assert response.status_code == 202

    def test_returns_404_when_job_not_found(self, app_client, mock_service):
        mock_service.get_job.return_value = None
        response = app_client.post(f"/jobs/{VALID_JOB_ID}/retry")
        assert response.status_code == 404

    def test_returns_409_when_not_halted(self, app_client, mock_service):
        mock_service.get_job.return_value = sample_job(status="COMPLETE")
        response = app_client.post(f"/jobs/{VALID_JOB_ID}/retry")
        assert response.status_code == 409

    def test_returns_409_when_halted_but_not_recoverable(self, app_client, mock_service):
        mock_service.get_job.return_value = sample_job(status=JOB_HALTED, recoverable=False)
        response = app_client.post(f"/jobs/{VALID_JOB_ID}/retry")
        assert response.status_code == 409

    def test_prepare_retry_called_before_executor_submit(
        self, app_client, mock_service, mock_executor
    ):
        """Status must flip synchronously before background submit to prevent race."""
        call_order = []
        mock_service.prepare_retry.side_effect = lambda *_: call_order.append("prepare")
        mock_executor.submit.side_effect = lambda *_: call_order.append("submit")
        mock_service.get_job.side_effect = [
            sample_job(status=JOB_HALTED, recoverable=True),
            sample_job(status="IN-PROGRESS"),
        ]
        app_client.post(f"/jobs/{VALID_JOB_ID}/retry")
        assert call_order == ["prepare", "submit"]

    def test_returns_503_and_rolls_back_when_executor_rejected(
        self, app_client, mock_service, mock_executor
    ):
        mock_service.get_job.return_value = sample_job(status=JOB_HALTED, recoverable=True)
        mock_executor.submit.side_effect = RuntimeError("shutting down")
        response = app_client.post(f"/jobs/{VALID_JOB_ID}/retry")
        assert response.status_code == 503
        mock_service.mark_interrupted.assert_called_once_with(VALID_JOB_ID)


# ---------------------------------------------------------------------------
# GET /jobs/{id}/review
# ---------------------------------------------------------------------------


class TestGetJobReview:
    def test_returns_200_with_pending_true_when_awaiting(
        self, app_client, mock_service
    ):
        mock_service.get_pending_review.return_value = {
            "pending": True,
            "payload": {
                "type": "research_review",
                "coverage": "partial",
                "title": "Test Blog",
                "sections": [],
                "research_note": "limited",
                "evidence_count": 2,
                "attempts": 0,
                "max_attempts": 2,
                "sources": [],
            },
        }
        response = app_client.get(f"/jobs/{VALID_JOB_ID}/review")
        assert response.status_code == 200
        data = response.json()
        assert data["pending"] is True
        assert data["coverage"] == "partial"

    def test_returns_200_with_pending_false_when_not_awaiting(
        self, app_client, mock_service
    ):
        mock_service.get_pending_review.return_value = {"pending": False}
        response = app_client.get(f"/jobs/{VALID_JOB_ID}/review")
        assert response.status_code == 200
        assert response.json()["pending"] is False

    def test_returns_404_when_job_not_found(self, app_client, mock_service):
        mock_service.get_pending_review.return_value = None
        response = app_client.get(f"/jobs/{VALID_JOB_ID}/review")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /jobs/{id}/decision
# ---------------------------------------------------------------------------


class TestSubmitDecision:
    def test_returns_202_on_proceed(self, app_client, mock_service, mock_executor):
        mock_service.get_job.side_effect = [
            sample_job(status=JOB_AWAITING_INPUT),
            sample_job(status="IN-PROGRESS"),
        ]
        response = app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "proceed"}
        )
        assert response.status_code == 202

    def test_returns_202_on_redo(self, app_client, mock_service, mock_executor):
        mock_service.get_job.side_effect = [
            sample_job(status=JOB_AWAITING_INPUT),
            sample_job(status="IN-PROGRESS"),
        ]
        response = app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "redo"}
        )
        assert response.status_code == 202

    def test_returns_422_on_invalid_decision(self, app_client, mock_service):
        mock_service.get_job.return_value = sample_job(status=JOB_AWAITING_INPUT)
        response = app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "maybe"}
        )
        assert response.status_code == 422

    def test_returns_404_when_job_not_found(self, app_client, mock_service):
        mock_service.get_job.return_value = None
        response = app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "proceed"}
        )
        assert response.status_code == 404

    def test_returns_409_when_not_awaiting_input(self, app_client, mock_service):
        mock_service.get_job.return_value = sample_job(status="IN-PROGRESS")
        response = app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "proceed"}
        )
        assert response.status_code == 409

    def test_prepare_decision_called_before_executor_submit(
        self, app_client, mock_service, mock_executor
    ):
        """Status must flip synchronously before background submit."""
        call_order = []
        mock_service.prepare_decision.side_effect = lambda *_: call_order.append("prepare")
        mock_executor.submit.side_effect = lambda *_: call_order.append("submit")
        mock_service.get_job.side_effect = [
            sample_job(status=JOB_AWAITING_INPUT),
            sample_job(status="IN-PROGRESS"),
        ]
        app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "proceed"}
        )
        assert call_order == ["prepare", "submit"]

    def test_returns_503_and_restores_awaiting_input_when_executor_rejected(
        self, app_client, mock_service, mock_executor
    ):
        mock_service.get_job.return_value = sample_job(status=JOB_AWAITING_INPUT)
        mock_executor.submit.side_effect = RuntimeError("shutting down")
        response = app_client.post(
            f"/jobs/{VALID_JOB_ID}/decision", json={"decision": "proceed"}
        )
        assert response.status_code == 503
        mock_service.restore_awaiting_input.assert_called_once_with(VALID_JOB_ID)


# ---------------------------------------------------------------------------
# DB error handler
# ---------------------------------------------------------------------------


class TestDBErrorHandling:
    def test_db_repository_error_returns_503(self, app_client, mock_service):
        mock_service.get_job.side_effect = DBRepositoryError(
            "get_job", {"job_id": VALID_JOB_ID}, Exception("connection lost")
        )
        response = app_client.get(f"/jobs/{VALID_JOB_ID}")
        assert response.status_code == 503
        assert "detail" in response.json()

import uuid

import psycopg
import pytest

from Server.persistence.job_repository import (
    DBRepositoryError,
    JOB_AWAITING_INPUT,
    JOB_COMPLETE,
    JOB_FAILED,
    JOB_HALTED,
    JOB_IN_PROGRESS,
    STAGE_COMPLETE,
    STAGE_FAILED,
    STAGE_HALTED,
    STAGE_QUEUED,
    JobRepository,
)


class TestCreateJob:
    def test_executes_insert_and_returns_uuid(self, job_repo, mock_cursor):
        result = job_repo.create_job("Test topic")
        assert mock_cursor.execute.called
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO blog_jobs" in sql
        assert params[1] == "Test topic"
        assert params[2] == JOB_IN_PROGRESS
        # Result must be a valid UUID
        uuid.UUID(result)

    def test_initial_status_is_in_progress(self, job_repo, mock_cursor):
        job_repo.create_job("topic")
        _, params = mock_cursor.execute.call_args[0]
        assert params[2] == JOB_IN_PROGRESS

    def test_initial_stage_is_queued(self, job_repo, mock_cursor):
        job_repo.create_job("topic")
        _, params = mock_cursor.execute.call_args[0]
        assert params[3] == STAGE_QUEUED


class TestGetJob:
    def test_returns_none_when_row_not_found(self, job_repo, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = job_repo.get_job("nonexistent")
        assert result is None

    def test_returns_dict_with_expected_keys(self, job_repo, mock_cursor):
        from datetime import datetime, timezone

        now = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
        mock_cursor.fetchone.return_value = (
            "job-id", "topic", "IN-PROGRESS", "queued",
            False, False, None, now, now,
        )
        result = job_repo.get_job("job-id")
        assert result is not None
        assert result["id"] == "job-id"
        assert result["status"] == "IN-PROGRESS"
        assert result["research_done"] is False


class TestListJobs:
    def test_excludes_failed_jobs_in_sql(self, job_repo, mock_cursor):
        mock_cursor.fetchall.return_value = []
        job_repo.list_jobs(limit=10, offset=0)
        sql, params = mock_cursor.execute.call_args[0]
        assert "WHERE status <> %s" in sql
        assert params[0] == JOB_FAILED


class TestCountJobs:
    def test_excludes_failed_in_sql(self, job_repo, mock_cursor):
        mock_cursor.fetchone.return_value = (5,)
        count = job_repo.count_jobs()
        sql, params = mock_cursor.execute.call_args[0]
        assert "WHERE status <> %s" in sql
        assert params[0] == JOB_FAILED
        assert count == 5


class TestStatusTransitions:
    def test_mark_complete_sets_correct_status(self, job_repo, mock_cursor):
        job_repo.mark_complete("job-1", "/path/to/blog.md")
        sql, params = mock_cursor.execute.call_args[0]
        assert params[0] == JOB_COMPLETE
        assert params[1] == STAGE_COMPLETE
        assert params[2] == "/path/to/blog.md"

    def test_mark_halted_sets_recoverable_true(self, job_repo, mock_cursor):
        job_repo.mark_halted("job-1")
        sql, params = mock_cursor.execute.call_args[0]
        assert params[0] == JOB_HALTED
        assert "recoverable = TRUE" in sql

    def test_mark_failed_sets_recoverable_false(self, job_repo, mock_cursor):
        job_repo.mark_failed("job-1")
        sql, params = mock_cursor.execute.call_args[0]
        assert params[0] == JOB_FAILED
        assert "recoverable = FALSE" in sql

    def test_mark_awaiting_input_sets_status_and_nulls_owner_id(self, job_repo, mock_cursor):
        """Critical invariant: AWAITING_INPUT must clear owner_id so the sweeper ignores it."""
        job_repo.mark_awaiting_input("job-1")
        sql, params = mock_cursor.execute.call_args[0]
        assert params[0] == JOB_AWAITING_INPUT
        assert "owner_id = NULL" in sql

    def test_mark_in_progress_resets_to_queued_stage(self, job_repo, mock_cursor):
        job_repo.mark_in_progress("job-1")
        sql, params = mock_cursor.execute.call_args[0]
        assert params[0] == JOB_IN_PROGRESS
        assert params[1] == STAGE_QUEUED


class TestLeaseManagement:
    def test_claim_job_stamps_owner_id(self, job_repo, mock_cursor):
        job_repo.claim_job("job-1", "worker-abc")
        sql, params = mock_cursor.execute.call_args[0]
        assert params[0] == "worker-abc"

    def test_mark_heartbeat_filters_by_in_progress_status(self, job_repo, mock_cursor):
        """Heartbeat must only update IN-PROGRESS rows — never touching other statuses."""
        job_repo.mark_heartbeat("job-1")
        sql, params = mock_cursor.execute.call_args[0]
        assert "AND status = %s" in sql
        assert params[1] == JOB_IN_PROGRESS


class TestReclaimExpiredLeases:
    def test_only_touches_in_progress_rows(self, job_repo, mock_cursor):
        """Critical invariant: sweeper must never reclaim AWAITING_INPUT or other statuses."""
        mock_cursor.rowcount = 0
        job_repo.reclaim_expired_leases(120)
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 2
        for call in calls:
            sql, params = call[0]
            assert "WHERE status = %s" in sql
            assert JOB_IN_PROGRESS in params

    def test_research_done_true_rows_become_halted(self, job_repo, mock_cursor):
        mock_cursor.rowcount = 0
        job_repo.reclaim_expired_leases(120)
        first_call_sql, first_call_params = mock_cursor.execute.call_args_list[0][0]
        assert first_call_params[0] == JOB_HALTED
        assert "research_done = TRUE" in first_call_sql

    def test_research_done_false_rows_become_failed(self, job_repo, mock_cursor):
        mock_cursor.rowcount = 0
        job_repo.reclaim_expired_leases(120)
        second_call_sql, second_call_params = mock_cursor.execute.call_args_list[1][0]
        assert second_call_params[0] == JOB_FAILED
        assert "research_done = FALSE" in second_call_sql

    def test_returns_halted_and_failed_counts(self, job_repo, mock_cursor):
        mock_cursor.rowcount = 3  # same for both calls
        halted, failed = job_repo.reclaim_expired_leases(120)
        assert halted == 3
        assert failed == 3


class TestReclaimOwnerJobs:
    def test_filters_by_owner_id(self, job_repo, mock_cursor):
        mock_cursor.rowcount = 0
        job_repo.reclaim_owner_jobs("owner-xyz")
        for call in mock_cursor.execute.call_args_list:
            _, params = call[0]
            assert "owner-xyz" in params


class TestDBRepositoryError:
    def test_wraps_psycopg_error_with_operation_and_metadata(self, job_repo, mock_cursor):
        mock_cursor.execute.side_effect = psycopg.Error("connection lost")
        with pytest.raises(DBRepositoryError) as exc_info:
            job_repo.get_job("job-1")
        err = exc_info.value
        assert err.operation == "get_job"
        assert err.metadata.get("job_id") == "job-1"
        assert isinstance(err.original, psycopg.Error)

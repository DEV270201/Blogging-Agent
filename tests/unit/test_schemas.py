import pytest
from pydantic import ValidationError

from Server.api.schemas import CreateJobRequest, DecisionRequest, HealthResponse


class TestCreateJobRequest:
    def test_valid_topic(self):
        req = CreateJobRequest(topic="This is a valid topic")
        assert req.topic == "This is a valid topic"

    def test_strips_whitespace(self):
        req = CreateJobRequest(topic="  valid topic here  ")
        assert req.topic == "valid topic here"

    def test_stripped_length_exactly_10(self):
        req = CreateJobRequest(topic="1234567890")
        assert req.topic == "1234567890"

    def test_stripped_length_below_10_raises(self):
        with pytest.raises(ValidationError):
            CreateJobRequest(topic="short")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            CreateJobRequest(topic="          ")

    def test_mixed_whitespace_trimmed_too_short_raises(self):
        # 9 real chars surrounded by spaces
        with pytest.raises(ValidationError):
            CreateJobRequest(topic="  123456789  ")

    def test_exactly_at_max_length(self):
        topic = "a" * 2000
        req = CreateJobRequest(topic=topic)
        assert len(req.topic) == 2000

    def test_exceeds_max_length_raises(self):
        with pytest.raises(ValidationError):
            CreateJobRequest(topic="a" * 2001)


class TestDecisionRequest:
    def test_proceed_is_valid(self):
        req = DecisionRequest(decision="proceed")
        assert req.decision == "proceed"

    def test_redo_is_valid(self):
        req = DecisionRequest(decision="redo")
        assert req.decision == "redo"

    def test_invalid_decision_raises(self):
        with pytest.raises(ValidationError):
            DecisionRequest(decision="skip")

    def test_empty_decision_raises(self):
        with pytest.raises(ValidationError):
            DecisionRequest(decision="")


class TestHealthResponse:
    def test_valid_ok_response(self):
        resp = HealthResponse(status="ok", database="connected")
        assert resp.status == "ok"
        assert resp.database == "connected"

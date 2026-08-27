from Server.nodes.orchestrator import _coverage_hint


class TestCoverageHint:
    def test_zero_evidence_is_insufficient(self):
        assert _coverage_hint(0) == "insufficient"

    def test_one_evidence_is_partial(self):
        assert _coverage_hint(1) == "partial"

    def test_two_evidence_is_partial(self):
        assert _coverage_hint(2) == "partial"

    def test_three_evidence_is_sufficient(self):
        assert _coverage_hint(3) == "sufficient"

    def test_large_evidence_count_is_sufficient(self):
        assert _coverage_hint(100) == "sufficient"

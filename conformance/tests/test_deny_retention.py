"""
Invariant: DENY decisions MUST be retained (sampled=true).
Probabilistic sampling MUST NOT apply to DENY spans.

Source: semantic/attributes.md §5, docs/pattern-spec.md §3.1
"""
from __future__ import annotations

import pytest

from conftest import load_trace


class TestDenyRetention:

    def test_deny_span_is_sampled(self):
        """DENY trace fixture must have sampled=true — the core DENY retention invariant."""
        trace = load_trace("deny_trace.json")
        eb_spans = [s for s in trace["spans"] if s["name"] == "eb.evaluate"]
        assert eb_spans, "no eb.evaluate span found"

        deny_spans = [s for s in eb_spans if s["attributes"].get("eb.decision") == "DENY"]
        assert deny_spans, "no DENY decision span found in deny_trace.json"

        for span in deny_spans:
            assert span["sampled"] is True, (
                f"DENY span must have sampled=true (keep-deny policy). "
                f"span_id={span['span_id']!r} has sampled={span['sampled']!r}"
            )

    def test_deny_not_sampled_fixture_would_fail(self):
        """
        Verify the 'bad' fixture (deny_not_sampled.json) would correctly
        fail our invariant check. This is a meta-test: if this fails,
        our detection logic is broken.
        """
        trace = load_trace("deny_not_sampled.json")
        eb_spans = [s for s in trace["spans"] if s["name"] == "eb.evaluate"]
        deny_spans = [s for s in eb_spans if s["attributes"].get("eb.decision") == "DENY"]

        # The bad fixture has sampled=false on a DENY span
        has_violation = any(s["sampled"] is False for s in deny_spans)
        assert has_violation, (
            "deny_not_sampled.json should have a DENY span with sampled=false "
            "(this fixture is intentionally invalid to test our detection)"
        )

    def test_ledger_commit_true_on_deny(self):
        """
        DENY spans must have eb.ledger_commit=true.
        A DENY without a ledger commit violates the boundary invariant.
        Source: docs/pattern-spec.md §3.2
        """
        trace = load_trace("deny_trace.json")
        for span in trace["spans"]:
            if span["name"] == "eb.evaluate" and span["attributes"].get("eb.decision") == "DENY":
                commit = span["attributes"].get("eb.ledger_commit")
                assert commit is True, (
                    f"DENY span must have eb.ledger_commit=true, "
                    f"got: {commit!r} (span_id={span['span_id']!r})"
                )

    def test_allow_trace_can_have_sampled_true_or_false(self):
        """
        ALLOW spans may be sampled or not (baseline policy).
        This test confirms we do NOT enforce sampled=true on ALLOW.
        """
        trace = load_trace("allow_trace.json")
        eb_spans = [s for s in trace["spans"] if s["name"] == "eb.evaluate"]
        allow_spans = [s for s in eb_spans if s["attributes"].get("eb.decision") == "ALLOW"]
        # No assertion on sampled value — ALLOW sampling is probabilistic (10% baseline)
        # This test passes as long as the fixture is well-formed
        assert allow_spans, "allow_trace.json must have at least one ALLOW span"

"""
Invariant: A conforming trace must contain exactly one eb.evaluate span.
Fragmented traces (missing eb.evaluate) indicate traceID routing failure.

Source: docs/pattern-spec.md §3.4, §4.1
"""
from __future__ import annotations

import pytest
from jsonschema import validate

from conftest import load_trace, load_schema

SCHEMA = load_schema("trace_min.schema.json")

EB_EVALUATE = "eb.evaluate"
VALID_SPAN_NAMES = {
    "eb.evaluate",
    "eb.ledger.append",
    "eb.ledger.export",
    "eb.policy.load",
}


class TestTraceIntegrity:

    def test_deny_trace_has_exactly_one_eb_evaluate(self):
        trace = load_trace("deny_trace.json")
        spans = [s for s in trace["spans"] if s["name"] == EB_EVALUATE]
        assert len(spans) == 1, (
            f"Expected exactly 1 eb.evaluate span, got {len(spans)}. "
            f"Multiple eb.evaluate spans may indicate duplicate instrumentation."
        )

    def test_allow_trace_has_exactly_one_eb_evaluate(self):
        trace = load_trace("allow_trace.json")
        spans = [s for s in trace["spans"] if s["name"] == EB_EVALUATE]
        assert len(spans) == 1, (
            f"Expected exactly 1 eb.evaluate span, got {len(spans)}."
        )

    def test_fragmented_trace_missing_eb_evaluate(self):
        """
        Verify the fragmented fixture correctly lacks eb.evaluate.
        Any production trace missing eb.evaluate would indicate traceID routing split.
        """
        trace = load_trace("fragmented_trace.json")
        spans = [s for s in trace["spans"] if s["name"] == EB_EVALUATE]
        assert len(spans) == 0, (
            "fragmented_trace.json is supposed to have 0 eb.evaluate spans "
            "(it represents a broken trace from failed traceID routing)"
        )

    def test_fragmented_trace_would_fail_integrity_check(self):
        """
        Meta-test: confirm our integrity check correctly rejects a fragmented trace.
        """
        trace = load_trace("fragmented_trace.json")
        with pytest.raises(AssertionError):
            spans = [s for s in trace["spans"] if s["name"] == EB_EVALUATE]
            assert len(spans) >= 1, (
                "trace must contain at least one eb.evaluate span. "
                "Missing eb.evaluate indicates traceID routing failure."
            )

    def test_deny_trace_has_no_duplicate_span_ids(self):
        trace = load_trace("deny_trace.json")
        span_ids = [s["span_id"] for s in trace["spans"]]
        assert len(span_ids) == len(set(span_ids)), (
            f"Duplicate span_ids found: {[x for x in span_ids if span_ids.count(x) > 1]}"
        )

    def test_allow_trace_has_no_duplicate_span_ids(self):
        trace = load_trace("allow_trace.json")
        span_ids = [s["span_id"] for s in trace["spans"]]
        assert len(span_ids) == len(set(span_ids)), (
            f"Duplicate span_ids found: {[x for x in span_ids if span_ids.count(x) > 1]}"
        )

    @pytest.mark.parametrize("fixture", ["deny_trace.json", "allow_trace.json"])
    def test_span_names_are_valid_eb_names(self, fixture: str):
        """
        All eb.* span names must be from the canonical set defined in semantic/attributes.md §3.
        Non-eb spans (e.g. http.server.request) are allowed in full traces but not in minimal fixtures.
        """
        trace = load_trace(fixture)
        for span in trace["spans"]:
            name = span["name"]
            if name.startswith("eb."):
                assert name in VALID_SPAN_NAMES, (
                    f"Unknown eb.* span name: {name!r}. "
                    f"Valid names: {sorted(VALID_SPAN_NAMES)}"
                )

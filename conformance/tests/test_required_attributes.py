"""
Invariant: Every eb.evaluate span MUST include all 4 required eb.* attributes.

Required: eb.decision, eb.reason_code, eb.ledger_commit, eb.envelope_id
Source: semantic/attributes.md §1
"""
from __future__ import annotations

import pytest
from jsonschema import validate, ValidationError

from conftest import load_trace, load_schema

SCHEMA = load_schema("trace_min.schema.json")

REQUIRED_EB_ATTRS = [
    "eb.decision",
    "eb.reason_code",
    "eb.ledger_commit",
    "eb.envelope_id",
]

VALID_DECISIONS = {"ALLOW", "DENY", "HOLD"}


def get_eb_evaluate_spans(trace: dict) -> list:
    return [s for s in trace["spans"] if s["name"] == "eb.evaluate"]


class TestRequiredAttributes:

    def test_deny_trace_validates_against_schema(self):
        trace = load_trace("deny_trace.json")
        validate(instance=trace, schema=SCHEMA)  # raises ValidationError on failure

    def test_allow_trace_validates_against_schema(self):
        trace = load_trace("allow_trace.json")
        validate(instance=trace, schema=SCHEMA)

    def test_deny_trace_has_eb_evaluate_span(self):
        trace = load_trace("deny_trace.json")
        spans = get_eb_evaluate_spans(trace)
        assert spans, "trace must contain at least one eb.evaluate span"

    def test_allow_trace_has_eb_evaluate_span(self):
        trace = load_trace("allow_trace.json")
        spans = get_eb_evaluate_spans(trace)
        assert spans, "trace must contain at least one eb.evaluate span"

    @pytest.mark.parametrize("fixture", ["deny_trace.json", "allow_trace.json"])
    def test_all_required_attributes_present(self, fixture: str):
        trace = load_trace(fixture)
        spans = get_eb_evaluate_spans(trace)
        assert spans, f"no eb.evaluate span in {fixture}"

        for span in spans:
            attrs = span["attributes"]
            missing = [k for k in REQUIRED_EB_ATTRS if k not in attrs]
            assert not missing, (
                f"missing required eb.* attributes in {fixture}: {missing}\n"
                f"present: {list(attrs.keys())}"
            )

    @pytest.mark.parametrize("fixture", ["deny_trace.json", "allow_trace.json"])
    def test_eb_decision_is_valid_value(self, fixture: str):
        trace = load_trace(fixture)
        for span in get_eb_evaluate_spans(trace):
            decision = span["attributes"].get("eb.decision")
            assert decision in VALID_DECISIONS, (
                f"eb.decision must be one of {VALID_DECISIONS}, got: {decision!r}"
            )

    @pytest.mark.parametrize("fixture", ["deny_trace.json", "allow_trace.json"])
    def test_eb_ledger_commit_is_bool(self, fixture: str):
        trace = load_trace(fixture)
        for span in get_eb_evaluate_spans(trace):
            val = span["attributes"].get("eb.ledger_commit")
            assert isinstance(val, bool), (
                f"eb.ledger_commit must be bool, got: {type(val).__name__} = {val!r}"
            )

    @pytest.mark.parametrize("fixture", ["deny_trace.json", "allow_trace.json"])
    def test_eb_reason_code_format(self, fixture: str):
        """reason_code must be ALL_CAPS_UNDERSCORE format per semantic/attributes.md §7"""
        trace = load_trace(fixture)
        for span in get_eb_evaluate_spans(trace):
            code = span["attributes"].get("eb.reason_code", "")
            assert code == code.upper(), (
                f"eb.reason_code must be ALL_CAPS, got: {code!r}"
            )
            assert " " not in code, (
                f"eb.reason_code must not contain spaces, got: {code!r}"
            )
            assert "-" not in code, (
                f"eb.reason_code must not contain hyphens (use underscore), got: {code!r}"
            )

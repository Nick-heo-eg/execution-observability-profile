"""
Invariant: High-cardinality eb.* attributes MUST NOT appear as metric labels.

Forbidden metric labels: eb.envelope_id, eb.proof_hash
Source: semantic/attributes.md §4, docs/pattern-spec.md §3.3
"""
from __future__ import annotations

import pytest
from jsonschema import validate

from conftest import load_metrics, load_schema

SCHEMA = load_schema("metrics_min.schema.json")

# Must never appear as Prometheus metric labels
FORBIDDEN_METRIC_LABELS = frozenset({"eb.envelope_id", "eb.proof_hash"})

# Prometheus uses underscores — cover both dot and underscore variants
FORBIDDEN_METRIC_LABELS_NORMALIZED = frozenset({
    "eb.envelope_id",
    "eb_envelope_id",
    "eb.proof_hash",
    "eb_proof_hash",
})


class TestCardinalityRules:

    def test_ok_metrics_validates_against_schema(self):
        m = load_metrics("ok_metrics.json")
        validate(instance=m, schema=SCHEMA)

    def test_no_forbidden_labels_in_ok_metrics(self):
        m = load_metrics("ok_metrics.json")
        for series in m["series"]:
            labels = set(series["labels"].keys())
            violations = labels & FORBIDDEN_METRIC_LABELS_NORMALIZED
            assert not violations, (
                f"Forbidden high-cardinality label(s) found in metric '{series['name']}': "
                f"{violations}. These attributes must NEVER appear as metric labels. "
                f"See semantic/attributes.md §4."
            )

    def test_bad_metrics_fixture_has_violation(self):
        """
        Meta-test: verify our bad fixture actually contains a violation.
        If this fails, the fixture is broken.
        """
        m = load_metrics("bad_metrics_envelope_id_label.json")
        found_violation = False
        for series in m["series"]:
            labels = set(series["labels"].keys())
            if labels & FORBIDDEN_METRIC_LABELS_NORMALIZED:
                found_violation = True
                break
        assert found_violation, (
            "bad_metrics_envelope_id_label.json should contain a forbidden label "
            "(this fixture is intentionally invalid)"
        )

    def test_bad_metrics_would_be_caught(self):
        """
        Confirm that running our check against the bad fixture raises AssertionError.
        This proves the detection works, not just the fixture.
        """
        m = load_metrics("bad_metrics_envelope_id_label.json")
        with pytest.raises(AssertionError, match="Forbidden"):
            for series in m["series"]:
                labels = set(series["labels"].keys())
                violations = labels & FORBIDDEN_METRIC_LABELS_NORMALIZED
                assert not violations, (
                    f"Forbidden high-cardinality label(s) found in metric '{series['name']}': "
                    f"{violations}. These attributes must NEVER appear as metric labels. "
                    f"See semantic/attributes.md §4."
                )

    def test_allowed_metric_labels(self):
        """
        Positive test: low-cardinality labels must be accepted.
        """
        allowed = {
            "eb_decision", "eb_reason_code", "eb_policy_id",
            "eb_transport_type", "eb_ledger_commit",
        }
        m = load_metrics("ok_metrics.json")
        for series in m["series"]:
            for label in series["labels"]:
                # Warn (not fail) if an unexpected label appears that isn't in our known-good set
                # This is informational — new labels aren't automatically forbidden
                pass
        # At minimum, verify ok_metrics uses known low-cardinality labels
        all_labels = {k for s in m["series"] for k in s["labels"]}
        assert all_labels.issubset(allowed | {"_comment"}), (
            f"ok_metrics.json contains unexpected labels: {all_labels - allowed}"
        )

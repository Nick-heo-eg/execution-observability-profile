# Conformance Harness

Automated enforcement of Execution Boundary Observability Pattern invariants.

**The pattern says what must hold. This harness proves it does.**

---

## Two Stages

### Stage A — Static Conformance (fast, runs on every PR)

Validates fixtures and schemas against the 4 pattern invariants.
No Docker. No network. Completes in under 15 seconds.

```bash
pip install -r conformance/requirements.txt
pytest conformance/tests/ -v
```

### Stage B — Integration Conformance (runs on main / release tags)

Starts the full OTel stack, generates real gate traffic, fetches from Jaeger,
converts to Minimal Trace format, and runs the same invariant tests.

```bash
cd examples/otelcol-debug && docker compose up -d
pip install execution-gate[otel]
python examples/quiet_adoption_demo.py   # generates DENY + ALLOW spans
python conformance/tools/jaeger_fetch.py \
    --out conformance/tmp/jaeger_traces.json \
    --decision DENY \
    --min-traces 1
pytest conformance/tests/ -v
```

---

## Invariants Enforced

| # | Invariant | Test file |
|---|---|---|
| 1 | All 4 required `eb.*` attributes present on `eb.evaluate` spans | `test_required_attributes.py` |
| 2 | DENY spans have `sampled=true` — never dropped by tail sampler | `test_deny_retention.py` |
| 3 | `eb.envelope_id` and `eb.proof_hash` never appear as metric labels | `test_cardinality_rules.py` |
| 4 | Each trace contains exactly one `eb.evaluate` span — no traceID routing splits | `test_trace_integrity.py` |

---

## Structure

```
conformance/
  README.md              ← this file
  requirements.txt       ← pytest + jsonschema only (no OTel dependency)
  schemas/
    trace_min.schema.json    ← canonical trace format for conformance
    metrics_min.schema.json  ← canonical metrics format for conformance
  fixtures/
    traces/
      deny_trace.json          ← valid DENY trace (all invariants met)
      allow_trace.json         ← valid ALLOW trace
      fragmented_trace.json    ← INVALID: missing eb.evaluate (routing failure)
      deny_not_sampled.json    ← INVALID: DENY with sampled=false (retention failure)
    metrics/
      ok_metrics.json                       ← valid metrics (no forbidden labels)
      bad_metrics_envelope_id_label.json    ← INVALID: forbidden label present
  tests/
    conftest.py               ← shared helpers
    test_required_attributes.py
    test_deny_retention.py
    test_cardinality_rules.py
    test_trace_integrity.py
  tools/
    jaeger_fetch.py           ← Jaeger → Minimal Trace converter (Integration stage)
```

---

## Fixture Convention

Valid fixtures: assert invariants pass.
Invalid fixtures (prefixed or suffixed with a violation description): used in meta-tests
to verify the detection logic works. Invalid fixtures must never be in the "normal" test
parametrize list.

---

## Minimal Trace Format

Conformance tests do not depend on Jaeger or OTLP wire format.
`tools/jaeger_fetch.py` converts Jaeger output to the canonical format.
This isolates the invariant tests from backend changes.

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "spans": [
    {
      "span_id": "00f067aa0ba902b7",
      "name": "eb.evaluate",
      "sampled": true,
      "duration_ms": 0.8,
      "attributes": {
        "eb.decision": "DENY",
        "eb.reason_code": "DENY_RULE",
        "eb.ledger_commit": true,
        "eb.proof_hash": "abc12345",
        "eb.envelope_id": "550e8400-e29b-41d4-a716-446655440000"
      }
    }
  ]
}
```

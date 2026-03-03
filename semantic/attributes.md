# Semantic Conventions — Attributes (v1)

Canonical attribute definitions for Execution Boundary observability spans.

All attributes use the `eb.` prefix (Execution Boundary namespace).
This file is normative. Changes require a version bump.

---

## 1. Required Attributes

Every span emitted during an `eb.evaluate` call MUST include all four:

| Attribute | Type | Example | Description |
|---|---|---|---|
| `eb.envelope_id` | string | `"550e8400-e29b-41d4-a716-446655440000"` | UUID of the evaluated envelope. Unique per decision. |
| `eb.decision` | string | `"ALLOW"` / `"DENY"` / `"HOLD"` | Outcome of the evaluation. Exactly one of three values. |
| `eb.reason_code` | string | `"AMOUNT_EXCEEDS_LIMIT"` | Machine-readable denial or allow reason. |
| `eb.ledger_commit` | bool | `true` | Whether the decision was successfully appended to the ledger. |

If `eb.ledger_commit` is `false`, the implementation has violated the boundary invariant.
An alert on `eb_ledger_commits_total / eb_decisions_total < 1.0` detects this condition.

---

## 2. Recommended Attributes

| Attribute | Type | Example | Description |
|---|---|---|---|
| `eb.policy_id` | string | `"finance-v2"` | Identifier of the policy set that evaluated the envelope. |
| `eb.transport_type` | string | `"iso8583"` / `"http"` / `"grpc"` | Transport type of the original request. |
| `eb.authority_score` | float | `0.85` | Authority score at evaluation time, if applicable. Range: 0.0–1.0. |
| `eb.proof_hash` | string | `"a3f2c1d0"` (first 8 chars) | Short prefix of the proof hash for correlation. Never full hash as attribute. |

---

## 3. Span Names (Fixed)

These names are fixed and must not be varied by implementation:

| Operation | Span Name |
|---|---|
| Envelope evaluation | `eb.evaluate` |
| Ledger append | `eb.ledger.append` |
| Export to canonical file | `eb.ledger.export` |
| Policy load | `eb.policy.load` |

Using non-standard span names breaks dashboard queries and alert expressions.

---

## 4. Cardinality Rules

### Span Attributes — High cardinality permitted

The following attributes appear on spans only. They MUST NOT be used as Prometheus metric labels:

| Attribute | Reason |
|---|---|
| `eb.envelope_id` | UUID — unbounded cardinality |
| `eb.proof_hash` | Hash prefix — high cardinality |

### Metric Labels — Low cardinality only

The following attributes MAY be used as Prometheus metric labels. They must remain low-cardinality:

| Attribute | Expected distinct values | Cardinality bound |
|---|---|---|
| `eb.decision` | 3 (ALLOW, DENY, HOLD) | Hard bound |
| `eb.reason_code` | < 20 per deployment | Soft bound — review if > 20 |
| `eb.policy_id` | < 10 per deployment | Soft bound |
| `eb.transport_type` | 6 defined values | Hard bound |
| `eb.ledger_commit` | 2 (true, false) | Hard bound |

**If `eb.reason_code` exceeds 20 distinct values in production, normalize to category groups.**

---

## 5. DENY Trace Retention Policy

This is a hard requirement, not a recommendation.

**DENY decisions MUST be retained in full. They MUST NOT be subject to probabilistic sampling.**

Rationale: A DENY span is the only observable proof that a proposed action was blocked. Sampling it away makes a blocked action indistinguishable from an action that was never proposed. This destroys the negative proof property of the Execution Boundary model.

Implementation requirement in the tail sampling processor:

```yaml
policies:
  - name: keep-deny
    type: string_attribute
    string_attribute:
      key: eb.decision
      values: ["DENY"]
  - name: keep-hold
    type: string_attribute
    string_attribute:
      key: eb.decision
      values: ["HOLD"]
```

These two policies MUST appear before any probabilistic policy.
Order matters: the tail sampler evaluates policies in declaration order.

**Verification:** The `otel-pipeline-health` dashboard shows sampled/evaluated ratio per policy.
`keep-deny` sampled/evaluated must be 1.0 at all times.

---

## 6. Tail Sampling Sizing Formula

Gateway tail sampling buffer (`num_traces`) must be sized to hold all in-flight traces
for the duration of `decision_wait`:

```
num_traces = peak_traces_per_second × decision_wait_seconds × safety_factor

Where:
  peak_traces_per_second  = observed peak TPS × 1.5 (burst headroom)
  decision_wait_seconds   = configured decision_wait (default: 10s)
  safety_factor           = 2.0 (recommended minimum)
```

Example (100 TPS peak, 10s wait):
```
num_traces = (100 × 1.5) × 10 × 2.0 = 3,000
```

Memory per trace estimate: ~5 KB average (varies by span count and attribute payload).

```
gateway_memory_limit_mib ≥ (num_traces × 5 KB) / 1024 + 256 MiB overhead
                         = (3,000 × 5) / 1024 + 256
                         ≈ 271 MiB  → round up to 512 MiB
```

The reference gateway config uses `limit_mib: 1024` for a 1,000 TPS peak deployment.

**Recalculate whenever peak TPS changes by more than 2×.**

---

## 7. reason_code Naming Convention

`eb.reason_code` values MUST follow this format:

```
CATEGORY_DETAIL
```

- ALL_CAPS
- Underscore-separated
- Category prefix identifies the policy domain
- No spaces, no hyphens

### Reserved values

| Value | Meaning |
|---|---|
| `POLICY_ALLOW` | Evaluation passed all policy rules |
| `POLICY_DENY` | Evaluation failed at least one policy rule (use specific code if available) |
| `EVALUATOR_UNAVAILABLE` | Evaluator could not be reached — fail-closed DENY |
| `ENVELOPE_INVALID` | Envelope failed schema validation before evaluation |
| `LEDGER_COMMIT_FAILED` | Decision reached but ledger append failed |

### Examples of domain-specific codes

| Value | Domain |
|---|---|
| `AMOUNT_EXCEEDS_LIMIT` | Financial |
| `MTI_NOT_PERMITTED` | ISO 8583 |
| `DESTINATION_BLOCKED` | Transport |
| `AUTHORITY_SCORE_LOW` | AI agent |
| `HOLD_PENDING_REVIEW` | Manual review queue |

Implementation MUST NOT use generic codes like `ERROR` or `BLOCKED` — these provide no signal for alert routing or policy debugging.

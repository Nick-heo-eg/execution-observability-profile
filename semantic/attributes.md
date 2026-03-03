# Semantic Conventions — Attributes

Span attributes emitted by an Execution Boundary gate.

All attributes use the `eb.` prefix (Execution Boundary namespace).

---

## Required Attributes

| Attribute | Type | Example | Cardinality |
|---|---|---|---|
| `eb.envelope_id` | string | `"550e8400-e29b-41d4-a716"` | High — span attribute only, never metric label |
| `eb.decision` | string | `"ALLOW"` / `"DENY"` / `"HOLD"` | Low — safe as metric label |
| `eb.reason_code` | string | `"POLICY_ALLOW"`, `"AMOUNT_EXCEEDS_LIMIT"` | Low — safe as metric label |
| `eb.ledger_commit` | bool | `true` | Low |

## Recommended Attributes

| Attribute | Type | Example | Notes |
|---|---|---|---|
| `eb.policy_id` | string | `"default"`, `"finance-v2"` | Which policy evaluated |
| `eb.authority_score` | float | `0.85` | If authority scoring used |
| `eb.transport_type` | string | `"iso8583"`, `"http"`, `"grpc"` | Transport profile |
| `eb.proof_hash` | string | `"a3f2..."` (first 16 chars) | Decision proof reference |

---

## Cardinality Rules

**Span attributes** (high cardinality OK):
- `eb.envelope_id`
- `eb.proof_hash`

**Metric labels** (low cardinality only):
- `eb.decision`
- `eb.reason_code`
- `eb.policy_id`
- `eb.transport_type`

Never use `eb.envelope_id` or `eb.proof_hash` as metric labels.

---

## Span Names

| Operation | Span Name |
|---|---|
| Envelope evaluation | `eb.evaluate` |
| Ledger append | `eb.ledger.append` |
| Export to canonical file | `eb.ledger.export` |
| Policy load | `eb.policy.load` |

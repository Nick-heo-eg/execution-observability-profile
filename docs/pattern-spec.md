# Execution Boundary Observability Pattern Specification (v1)

This document is the canonical definition of the Execution Boundary Observability Pattern.
It is normative. The README is a summary. This file is the source of truth for implementation decisions.

---

## 1. Pattern Identity

**Name:** Execution Boundary Observability Pattern
**Version:** v1.0
**Layer:** 4 (Domain Profile) in the [Execution Boundary](https://github.com/Nick-heo-eg/execution-boundary) layer model
**Depends on:** [execution-boundary-core-spec](https://github.com/Nick-heo-eg/execution-boundary-core-spec) (commit: `d3e239b`)

**This pattern observes. It does not enforce.**
Enforcement is the responsibility of the gate (Layer 2/3). This profile has no effect on gate decisions.

---

## 2. Problem Statement

An execution boundary gate produces decisions (ALLOW, DENY, HOLD) before any side-effect occurs.
Without structured observability, the following conditions are undetectable:

1. A DENY decision occurred but was sampled away — indistinguishable from a request never proposed
2. A decision was evaluated but not committed to the ledger — boundary invariant violated silently
3. Evaluator latency spiked — gate became a bottleneck without visibility
4. Metric label cardinality exploded — observability system became a failure point

This pattern defines the minimum structure required to detect all four conditions.

---

## 3. Four Invariants

### 3.1 DENY Trace Retention

**Definition:** Every DENY decision MUST produce a retained span. Probabilistic sampling MUST NOT apply to DENY spans.

**Why:** A DENY span is the observability representation of the ledger's negative proof property. If the span is sampled away, the external audit trail loses evidence that a proposed action was blocked.

**Implementation gate:** `keep-deny` policy MUST appear in tail_sampling before any probabilistic policy.

**Verification metric:**
```
sum(rate(otelcol_processor_tail_sampling_count_spans_sampled_total{policy="keep-deny"}[5m]))
/
sum(rate(otelcol_processor_tail_sampling_count_traces_evaluated_total[5m]))
```
Must be 1.0. Any value < 1.0 indicates DENY spans are being dropped.

---

### 3.2 Ledger Commit Coverage

**Definition:** Every decision — ALLOW, DENY, HOLD — MUST result in a ledger commit. The ratio of `eb_ledger_commits_total` to `eb_decisions_total` must be exactly 1.0.

**Why:** The Execution Boundary Core Spec requires unconditional ledger append. A decision without a ledger entry is an unrecorded action — the boundary invariant is broken.

**Alert:** `EbLedgerCommitFailing` fires when this ratio drops below 1.0 for 5 minutes.

**Span signal:** `eb.ledger_commit = false` on any span indicates a commit failure. These spans must be retained and routed to incident response.

---

### 3.3 Cardinality Isolation

**Definition:** `eb.envelope_id` and `eb.proof_hash` MUST NOT appear as Prometheus metric labels.

**Why:** These attributes have UUID-level cardinality. Exposing them as metric labels creates unbounded label sets that crash or degrade Prometheus and Grafana.

**Rule:** High-cardinality attributes are span attributes only. Metric labels are restricted to the low-cardinality set defined in [semantic/attributes.md](../semantic/attributes.md).

**Enforcement:** Label relabeling in the Prometheus scrape config should drop these labels if they appear:
```yaml
metric_relabel_configs:
  - source_labels: [eb_envelope_id]
    action: drop
  - source_labels: [eb_proof_hash]
    action: drop
```

---

### 3.4 TraceID-Keyed Gateway Routing

**Definition:** The Agent collector MUST use a `loadbalancing` exporter keyed on `traceId` when routing to multiple Gateway replicas.

**Why:** Tail sampling requires all spans of a trace to arrive at the same collector instance. Round-robin routing splits traces across replicas, making DENY detection probabilistic — the `keep-deny` policy may receive only part of a trace and make a wrong sampling decision.

**Implementation:**
```yaml
exporters:
  loadbalancing:
    routing_key: traceId
    protocol:
      otlp:
        tls:
          insecure: true
    resolver:
      static:
        hostnames:
          - otelcol-gateway:4317
```

Single-replica Gateway deployments are exempt from this requirement but must document the exemption.

---

## 4. Component Definitions

### 4.1 Agent Collector

Role: Per-node (DaemonSet) span receiver and forwarder.
Responsibilities:
- Receive OTLP from local gate process
- Apply resource detection (node, pod metadata)
- Forward to Gateway via traceID-keyed load balancing

Must not apply tail sampling. The Agent has incomplete trace context.

### 4.2 Gateway Collector

Role: Cluster-level (Deployment, HA) tail sampler and exporter.
Responsibilities:
- Receive complete traces from all Agents
- Apply tail sampling policy (invariant 3.1)
- Export to trace backend and metrics backend

Must run ≥ 2 replicas in production. Single-replica is acceptable only in local/debug deployments.

### 4.3 Tail Sampling Policy — Canonical Order

Policies must be declared in this order. Order affects evaluation:

```
1. keep-deny          (string_attribute: eb.decision = DENY)
2. keep-hold          (string_attribute: eb.decision = HOLD)
3. keep-errors        (status_code: ERROR)
4. keep-slow          (latency ≥ 1000ms)
5. baseline-allow     (probabilistic: 10%)
```

Items 1–4 are retention policies (100%). Item 5 is the only sampling policy.
The effective retention rate for DENY and HOLD is always 100%, regardless of item 5.

---

## 5. Metric Definitions

Metrics emitted by a conforming gate implementation:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `eb_decisions_total` | counter | `eb_decision`, `eb_reason_code`, `eb_policy_id` | Total decisions by outcome |
| `eb_decision_duration_seconds` | histogram | `eb_decision` | evaluate() call duration |
| `eb_ledger_commits_total` | counter | `eb_decision` | Total ledger appends |
| `eb_ledger_commit_duration_seconds` | histogram | — | Ledger append duration |

These metrics are produced by the gate, not the collector. The collector observes them.

---

## 6. What Conforms, What Does Not

A deployment conforms to this pattern if and only if:

| Requirement | Conformance criterion |
|---|---|
| DENY retention | `keep-deny` in tail_sampling with 100% retention; ratio verified |
| Ledger commit coverage | `EbLedgerCommitFailing` alert active; ratio alert threshold ≤ 5m |
| Cardinality isolation | `eb.envelope_id` absent from all metric label sets |
| TraceID routing | `loadbalancing` exporter with `traceId` key (or documented single-replica exemption) |
| Required attributes | All 4 required `eb.*` attributes present on every `eb.evaluate` span |

Partial adoption (e.g., dashboards without alerts, or alerts without DENY retention) does not constitute conformance.

---

## 7. Change Policy

This specification is versioned. The following changes require a version bump:

| Change type | Version impact | Process |
|---|---|---|
| New required `eb.*` attribute | Minor | Backward-compatible addition |
| Renamed `eb.*` attribute | Major | RFC required |
| Removed `eb.*` attribute | Major | RFC required |
| New invariant | Minor | Document in CHANGELOG |
| Invariant definition change | Major | RFC required |
| Tail sampling policy order change | Minor | Compatibility note required |
| New optional metric | Minor | No gate |
| Existing metric renamed | Major | RFC required |

RFC template: [execution-boundary-core-spec/docs/rfc-template.md](https://github.com/Nick-heo-eg/execution-boundary-core-spec/blob/main/docs/rfc-template.md)

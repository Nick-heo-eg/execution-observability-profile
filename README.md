# Execution Boundary Observability Profile

Observability profile for [Execution Boundary](https://github.com/Nick-heo-eg/execution-boundary) systems.

This profile defines how to observe an execution boundary — not how to enforce one.

**The gate controls execution. This profile observes the gate.**

---

## Layered Model

```
Layer 1  execution-boundary-core-spec          ← contract
Layer 2  execution-gate                        ← enforcement
Layer 3  agent-execution-guard                 ← agent SDK
Layer 4  execution-observability-profile       ← this repo
```

---

## What This Profile Defines

- OTel Collector topology (Agent → Gateway, 2-tier)
- Semantic conventions for execution boundary spans and metrics
- Tail sampling policy: keep all DENY, sample ALLOW at 10%
- Reference Grafana dashboards
- Prometheus alert rules

## What This Profile Does Not Define

- Execution gate logic
- Policy evaluation
- Ledger implementation
- Any enforcement behavior

Gate code has no dependency on this profile. Observability is additive.

---

## Semantic Conventions

Spans emitted by an execution boundary gate MUST include:

| Attribute | Type | Values | Notes |
|---|---|---|---|
| `eb.envelope_id` | string | UUID | Per-decision identifier |
| `eb.decision` | string | `ALLOW` / `DENY` / `HOLD` | Low cardinality — safe as metric label |
| `eb.policy_id` | string | policy name | Which policy evaluated |
| `eb.reason_code` | string | `POLICY_ALLOW`, `AMOUNT_EXCEEDS_LIMIT`, etc. | Low cardinality |
| `eb.ledger_commit` | bool | `true` / `false` | Was decision appended to ledger |
| `eb.authority_score` | float | 0.0–1.0 | If applicable |

**`eb.envelope_id` is a span attribute only — never a metric label.**

Full convention: [semantic/attributes.md](semantic/attributes.md)

---

## Collector Topology

```
Service / Gate
    │ OTLP (gRPC)
    ▼
Agent Collector (DaemonSet)
  - memory_limiter
  - resourcedetection
  - batch
  - loadbalancing exporter (traceID hash → Gateway)
    │
    ▼
Gateway Collector (Deployment, HA)
  - memory_limiter
  - tail_sampling  ← DENY always kept
  - batch
  - fanout → traces backend + metrics backend
```

TraceID-based load balancing is mandatory.
Without it, tail sampling across multiple Gateway replicas will produce partial traces.

Full configs: [profiles/k8s/](profiles/k8s/)

---

## Tail Sampling Policy

| Policy | Rule | Rationale |
|---|---|---|
| `keep-deny` | `eb.decision = DENY` | All denials are kept — negative proof requirement |
| `keep-errors` | `status_code = ERROR` | All errors kept |
| `keep-slow` | `latency ≥ 500ms` | Performance outliers |
| `baseline` | 10% probabilistic | ALLOW baseline coverage |

DENY traces are never sampled away. This is a hard requirement of the Execution Boundary model.

---

## Dashboards

Two reference dashboards (Grafana JSON):

| Dashboard | Purpose |
|---|---|
| `execution-boundary-overview` | Deny rate, decision latency, ledger commit latency, reason_code breakdown |
| `otel-pipeline-health` | Queue depth, drop rate, tail sampling latency, exporter errors |

→ [dashboards/grafana/](dashboards/grafana/)

---

## Alerts

Minimum alert set (Prometheus):

| Alert | Condition | Severity |
|---|---|---|
| `ExporterQueueHigh` | queue > 80% capacity | warning |
| `ExporterDropNonZero` | drop_rate > 0 | critical |
| `GatewayOOMRisk` | memory > 85% limit | warning |
| `TailSamplingLatencyHigh` | p99 decision latency > 8s | warning |
| `CollectorDown` | up == 0 | critical |

→ [alerts/prometheus/](alerts/prometheus/)

---

## Quickstart (local debug)

```bash
cd examples/otelcol-debug
docker compose up
```

Sends example ALLOW/DENY spans through the full 2-tier pipeline locally.

---

## License

Apache 2.0

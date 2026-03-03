# Execution Boundary Observability Pattern (v1)

[![conformance-static](https://github.com/Nick-heo-eg/execution-observability-profile/actions/workflows/conformance-static.yml/badge.svg)](https://github.com/Nick-heo-eg/execution-observability-profile/actions/workflows/conformance-static.yml) [![conformance-integration](https://github.com/Nick-heo-eg/execution-observability-profile/actions/workflows/conformance-integration.yml/badge.svg)](https://github.com/Nick-heo-eg/execution-observability-profile/actions/workflows/conformance-integration.yml)


Observability pattern for [Execution Boundary](https://github.com/Nick-heo-eg/execution-boundary) systems.

**The gate controls execution. This profile observes the gate.**

This is not a monitoring template. It is a structured pattern for making execution boundary decisions observable, traceable, and auditable — aligned with the Execution Boundary Core Spec.

→ **[docs/pattern-spec.md](docs/pattern-spec.md)** — canonical pattern definition

---

## 1. What This Is

An execution boundary gate produces three types of decisions: ALLOW, DENY, HOLD.

Each decision must be:
- **Recorded** before execution occurs (pre-execution)
- **Traceable** — linked to the envelope that was evaluated
- **Verifiable** — DENY decisions are never sampled away

This profile defines the OTel-based observability layer that makes these properties inspectable without modifying gate behavior.

```
Envelope → evaluate() → Decision → Ledger → [ execute only if ALLOW ]
                                      ↓
                               OTel Span (eb.*)
                                      ↓
                          Agent → Gateway → Backend
```

---

## 2. What This Is Not

- Not an execution gate (no enforcement logic)
- Not a policy engine (no authorization decisions)
- Not a logging framework (structured tracing, not free-text logs)
- Not a replacement for the Merkle ledger (complementary, not equivalent)

Gate code has zero dependency on this profile. Observability is additive and non-invasive.

---

## 3. Architecture Pattern

```
Service / Gate
    │ OTLP gRPC
    ▼
┌─────────────────────────────┐
│  Agent Collector (DaemonSet)│
│  - memory_limiter           │
│  - batch                    │
│  - loadbalancing exporter   │  ← traceID hash → deterministic routing
└─────────────┬───────────────┘
              │ OTLP gRPC (traceID-keyed)
              ▼
┌─────────────────────────────┐
│  Gateway Collector (HA ×N)  │
│  - memory_limiter           │
│  - tail_sampling            │  ← DENY always kept (hard requirement)
│  - batch                    │
│  - fanout exporters         │
└─────────────────────────────┘
```

**TraceID-based load balancing is mandatory.** Without it, a trace spanning multiple spans may be split across Gateway replicas, causing tail sampling to operate on incomplete traces and silently drop DENY spans.

Full configs: [profiles/k8s/](profiles/k8s/)

---

## 4. Failure Modes This Pattern Prevents

| Failure Mode | How This Pattern Prevents It |
|---|---|
| DENY span dropped by sampler | `keep-deny` policy: 100% retention, no probabilistic sampling on DENY |
| DENY not distinguishable from never-proposed | `eb.decision=DENY` on every denied span; `eb.ledger_commit=true` required |
| Trace split across Gateway replicas | TraceID loadbalancing exporter in Agent tier |
| Cardinality explosion on metrics | `eb.envelope_id` banned from metric labels; only low-cardinality attributes permitted |
| Evaluator latency spike undetected | `eb.evaluate` span duration tracked; alert at p99 > 100ms |
| Ledger commit silently failing | `eb_ledger_commits_total / eb_decisions_total` ratio must be 1.0 |

---

## 5. Minimal Deploy Guide

**Local (no k8s):**
```bash
cd examples/otelcol-debug
docker compose up
# Grafana → http://localhost:3000  (anonymous access enabled for local debug)
# Prometheus → http://localhost:9090
```

**Kubernetes:**
```bash
kubectl apply -f profiles/k8s/agent-collector.yaml
kubectl apply -f profiles/k8s/gateway-collector.yaml
```

Import dashboards from [dashboards/grafana/](dashboards/grafana/) into Grafana.
Apply alerts from [alerts/prometheus/](alerts/prometheus/) to Prometheus.

---

## 6. Production Hardening Checklist

- [ ] TraceID loadbalancing exporter configured in Agent (not round-robin)
- [ ] `keep-deny` tail sampling policy verified — check sampled/evaluated ratio in `otel-pipeline-health` dashboard
- [ ] `eb_ledger_commits_total / eb_decisions_total` alert active — triggers if ratio drops below 1.0
- [ ] `eb.envelope_id` confirmed absent from all metric label sets
- [ ] Gateway replicas ≥ 2 (HA); liveness probe on OTLP port
- [ ] Exporter queue capacity set per sizing formula (see [docs/pattern-spec.md](docs/pattern-spec.md))
- [ ] `ExporterDropNonZero` alert routed to critical channel
- [ ] Tail sampling `decision_wait` ≥ max expected trace duration

---

## 7. Versioning Policy

This profile follows the Execution Boundary layer versioning conventions:

- **Semantic convention changes** (new/renamed `eb.*` attributes): minor version bump, backward-compatible additions only
- **Breaking attribute removals**: major version bump, RFC required
- **Collector config changes**: patch version, no compatibility gate
- **Dashboard/alert changes**: patch version, no compatibility gate

Current version: **v1.1**

Compatibility with Core Spec: [execution-boundary-core-spec](https://github.com/Nick-heo-eg/execution-boundary-core-spec) (commit: `d3e239b`)

---

## Semantic Conventions

Spans emitted by an execution boundary gate MUST include:

| Attribute | Type | Cardinality | Metric Label? |
|---|---|---|---|
| `eb.envelope_id` | string | High | **Never** |
| `eb.decision` | string (ALLOW/DENY/HOLD) | Low | Yes |
| `eb.reason_code` | string | Low | Yes |
| `eb.ledger_commit` | bool | Low | Yes |

Full specification: [semantic/attributes.md](semantic/attributes.md)

---

## Dashboards

| Dashboard | UID | Purpose |
|---|---|---|
| Execution Boundary — Overview | `eb-overview-v1` | Deny rate, decision latency, ledger commit coverage, reason_code breakdown |
| OTel Pipeline Health | `eb-otel-pipeline-v1` | Queue depth, drop rate, tail sampling latency, exporter errors, collector uptime |

→ [dashboards/grafana/](dashboards/grafana/)

---

## Alerts

| Alert | Condition | Severity |
|---|---|---|
| `EbCollectorQueueHigh` | queue > 80% capacity for 5m | warning |
| `EbCollectorDropNonZero` | drop rate > 0 for 1m | critical |
| `EbCollectorMemoryHigh` | RSS > 85% of limit for 10m | warning |
| `EbTailSamplingLatencyHigh` | p99 decision window > 30s for 5m | warning |
| `EbCollectorDown` | up == 0 for 2m | critical |
| `EbDenyRateHigh` | deny ratio > 30% for 10m | warning |
| `EbLedgerCommitFailing` | commit/decision ratio < 1.0 for 5m | critical |
| `EbDecisionLatencyHigh` | p99 evaluate() > 100ms for 5m | warning |
| `EbNoDenyInWindow` | no DENY in 24h | info |

→ [alerts/prometheus/](alerts/prometheus/)

---

## Conformance Verification

Pattern invariants were verified against [execution-gate](https://github.com/Nick-heo-eg/execution-gate) v0.3.0.

**Setup:** execution-gate[otel] → otelcol-agent → otelcol-gateway (tail_sampling) → Jaeger

**Result (5 decisions: 2 ALLOW, 3 DENY):**

| Invariant | Expected | Observed |
|---|---|---|
| DENY retention | 3/3 kept | `keep-deny sampled=true: 3` ✓ |
| ALLOW sampling | baseline 10% | 0 retained (correct at low volume) ✓ |
| `eb.reason_code` on each DENY span | present | `NO_RULE`, `AMOUNT_EXCEEDS_LIMIT`, `DENY_RULE` ✓ |
| `eb.ledger_commit=true` on each span | present | `True` on all 3 DENY spans ✓ |
| No trace fragments | single span per traceID | 1 span / trace, no splits ✓ |

ALLOW traces absent from the backend is the expected outcome — not a gap.
A DENY that never reaches the backend would be the failure mode. None occurred.

→ Demo script: [examples/quiet_adoption_demo.py](examples/quiet_adoption_demo.py) in execution-gate

---

---

## Conformance

This profile is enforced by CI.
Pull requests that violate invariants will fail.
See [conformance/](conformance/) for machine-verifiable rules.

Conformance harness and integration workflow exist. Validated end-to-end on a real approval flow ([invest-core](https://github.com/Nick-heo-eg/invest-core-private)).

## License

Apache 2.0

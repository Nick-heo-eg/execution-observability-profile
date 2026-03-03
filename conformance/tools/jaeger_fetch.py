"""
conformance/tools/jaeger_fetch.py

Fetches eb.evaluate traces from Jaeger Query API and converts them
to the Execution Boundary Minimal Trace format (trace_min.schema.json).

Used by Integration Conformance CI to bridge Jaeger output
to the same assertions as Static Conformance tests.

Usage:
    python conformance/tools/jaeger_fetch.py \\
        --jaeger http://localhost:16686 \\
        --service execution-gate \\
        --out conformance/tmp/jaeger_traces.json \\
        --min-traces 1 \\
        --decision DENY

The output file contains a list of minimal trace objects.
Run pytest against this file using integration_conftest.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


def fetch_traces(
    jaeger_url: str,
    service: str,
    operation: str = "eb.evaluate",
    limit: int = 100,
    lookback: str = "1h",
    retries: int = 6,
    retry_delay: float = 5.0,
) -> list[dict]:
    """
    Fetch traces from Jaeger Query API v3.
    Retries to handle collector export delay.
    """
    url = (
        f"{jaeger_url.rstrip('/')}/api/traces"
        f"?service={service}"
        f"&operation={operation}"
        f"&limit={limit}"
        f"&lookback={lookback}"
    )

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = json.loads(resp.read())
                traces = body.get("data") or []
                if traces:
                    print(f"[jaeger_fetch] Fetched {len(traces)} trace(s) (attempt {attempt})")
                    return traces
                print(f"[jaeger_fetch] No traces yet, retrying in {retry_delay}s (attempt {attempt}/{retries})")
        except urllib.error.URLError as e:
            print(f"[jaeger_fetch] Jaeger unreachable: {e} (attempt {attempt}/{retries})")

        if attempt < retries:
            time.sleep(retry_delay)

    return []


def convert_jaeger_span(jaeger_span: dict, sampled: bool = True) -> dict:
    """
    Convert a single Jaeger span object to Minimal Trace span format.

    Jaeger span structure:
      {
        "spanID": "...",
        "operationName": "...",
        "duration": 1234,  (microseconds)
        "tags": [{"key": "...", "value": ..., "type": "..."}, ...]
      }
    """
    # Convert tags list to dict
    attrs = {}
    for tag in jaeger_span.get("tags", []):
        key = tag["key"]
        val = tag["value"]
        # Jaeger stores booleans as strings in some versions — normalize
        if tag.get("type") == "bool":
            val = str(val).lower() == "true"
        attrs[key] = val

    duration_us = jaeger_span.get("duration", 0)
    duration_ms = duration_us / 1000.0

    return {
        "span_id": jaeger_span.get("spanID", ""),
        "name": jaeger_span.get("operationName", ""),
        "sampled": sampled,  # if it arrived at Jaeger, it was sampled
        "duration_ms": duration_ms,
        "attributes": attrs,
    }


def convert_jaeger_trace(jaeger_trace: dict) -> dict:
    """
    Convert a Jaeger trace object to Minimal Trace format.

    Jaeger trace structure:
      {
        "traceID": "...",
        "spans": [...],
        "processes": {...}
      }
    """
    trace_id = jaeger_trace.get("traceID", "")
    spans = [
        convert_jaeger_span(s, sampled=True)
        for s in jaeger_trace.get("spans", [])
    ]
    return {
        "trace_id": trace_id,
        "spans": spans,
    }


def filter_by_decision(traces: list[dict], decision: Optional[str]) -> list[dict]:
    """
    If decision filter is set (e.g. 'DENY'), return only traces
    that contain an eb.evaluate span with eb.decision == decision.
    """
    if not decision:
        return traces

    result = []
    for trace in traces:
        for span in trace["spans"]:
            if (
                span["name"] == "eb.evaluate"
                and span["attributes"].get("eb.decision") == decision
            ):
                result.append(trace)
                break
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch eb.evaluate traces from Jaeger and convert to Minimal Trace format"
    )
    parser.add_argument("--jaeger", default="http://localhost:16686", help="Jaeger Query API base URL")
    parser.add_argument("--service", default="execution-gate", help="Service name to query")
    parser.add_argument("--operation", default="eb.evaluate", help="Operation name filter")
    parser.add_argument("--limit", type=int, default=100, help="Max traces to fetch")
    parser.add_argument("--lookback", default="1h", help="Lookback window (e.g. 1h, 30m)")
    parser.add_argument("--out", required=True, help="Output JSON file path")
    parser.add_argument("--min-traces", type=int, default=1, help="Fail if fewer traces found")
    parser.add_argument("--decision", default=None, help="Filter by eb.decision value (e.g. DENY)")
    parser.add_argument("--retries", type=int, default=6, help="Retry attempts for Jaeger connection")
    parser.add_argument("--retry-delay", type=float, default=5.0, help="Seconds between retries")
    args = parser.parse_args()

    # Fetch from Jaeger
    raw_traces = fetch_traces(
        jaeger_url=args.jaeger,
        service=args.service,
        operation=args.operation,
        limit=args.limit,
        lookback=args.lookback,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )

    if not raw_traces:
        print(f"[jaeger_fetch] ERROR: No traces found. Is the stack running and spans exported?")
        return 1

    # Convert to minimal format
    minimal_traces = [convert_jaeger_trace(t) for t in raw_traces]

    # Filter by decision if requested
    if args.decision:
        minimal_traces = filter_by_decision(minimal_traces, args.decision)
        print(f"[jaeger_fetch] After filtering eb.decision={args.decision!r}: {len(minimal_traces)} trace(s)")

    if len(minimal_traces) < args.min_traces:
        print(
            f"[jaeger_fetch] ERROR: Found {len(minimal_traces)} trace(s), "
            f"expected at least {args.min_traces}."
        )
        return 1

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(minimal_traces, indent=2))
    print(f"[jaeger_fetch] Wrote {len(minimal_traces)} trace(s) to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

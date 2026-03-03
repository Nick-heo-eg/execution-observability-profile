"""
Shared fixtures and helpers for conformance tests.
All paths are resolved relative to the repo root, not conftest location.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES_TRACES = REPO_ROOT / "conformance" / "fixtures" / "traces"
FIXTURES_METRICS = REPO_ROOT / "conformance" / "fixtures" / "metrics"
SCHEMAS = REPO_ROOT / "conformance" / "schemas"


def load_trace(filename: str) -> dict:
    return json.loads((FIXTURES_TRACES / filename).read_text())


def load_metrics(filename: str) -> dict:
    return json.loads((FIXTURES_METRICS / filename).read_text())


def load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS / filename).read_text())

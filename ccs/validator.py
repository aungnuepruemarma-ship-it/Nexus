"""Registry validation: JSON Schema + DAG/expiry consistency.

Two layers of checking:
  1. schema — each entry validates against registry/capability.schema.json;
  2. semantic — the registry-as-a-DAG is acyclic, dependencies resolve, and a
     composite's valid_until does not exceed any dependency's (expiry monotonicity).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    _HAVE_JSONSCHEMA = True
except Exception:  # pragma: no cover
    _HAVE_JSONSCHEMA = False

from .registry import Registry

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "registry" / "capability.schema.json"


def load_schema(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or _SCHEMA_PATH).read_text())


def validate_entry(entry: dict, schema: dict | None = None) -> list[str]:
    """Return a list of schema error messages ([] means valid)."""
    if not _HAVE_JSONSCHEMA:
        return _minimal_check(entry)
    schema = schema or load_schema()
    v = Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in v.iter_errors(entry)]


def _minimal_check(entry: dict) -> list[str]:
    required = ["id", "name", "status", "version", "description", "task", "signals", "date_created"]
    errs = [f"missing required field: {r}" for r in required if r not in entry]
    if entry.get("status") == "negative" and "failure_type" not in entry:
        errs.append("negative entry missing failure_type")
    return errs


def validate_registry(reg: Registry, schema: dict | None = None) -> dict:
    """Full validation. Returns {ok, schema_errors, semantic_errors}."""
    schema = schema or (load_schema() if _HAVE_JSONSCHEMA else None)
    schema_errors: dict[str, list[str]] = {}
    for cid, entry in reg.entries.items():
        errs = validate_entry(entry, schema)
        if errs:
            schema_errors[cid] = errs

    semantic: list[str] = []
    if reg.has_cycle():
        semantic.append("dependency graph contains a cycle")
    for cid, entry in reg.entries.items():
        for d in (entry.get("depends_on") or []):
            if d not in reg.entries:
                semantic.append(f"{cid}: depends_on unknown capability {d}")
        # expiry monotonicity for composites
        own = entry.get("valid_until")
        if own and entry.get("depends_on"):
            own_d = dt.date.fromisoformat(own)
            for d in entry["depends_on"]:
                dep = reg.entries.get(d, {})
                dv = dep.get("valid_until")
                if dv and dt.date.fromisoformat(dv) < own_d:
                    semantic.append(
                        f"{cid}: valid_until {own} exceeds dependency {d} ({dv})")
    return {
        "ok": not schema_errors and not semantic,
        "schema_errors": schema_errors,
        "semantic_errors": semantic,
    }

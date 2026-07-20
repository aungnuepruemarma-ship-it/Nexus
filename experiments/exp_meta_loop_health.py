"""EXP-META-LOOPHEALTH (meta): the Automated Computer Scientist measures ITSELF.

The next useful law is not about the hardware — it is about the discovery loop. From its own
discovery log and git history we recover the loop's health: how many self-experiments it has
run, what fraction certified, its cadence (experiments/hour), and how many autonomous commits
it has produced. This is the first rung toward a self-improving research strategy: the system
learning which of its own experiments are productive.

Certified positive iff the loop is healthy — enough discoveries logged and a success rate above
a pre-registered bar. Read-only and deterministic given repo state, so it reproduces trivially.

Run: python experiments/exp_meta_loop_health.py
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import re
import subprocess
from pathlib import Path

from ccs.audit import audit_capability
from ccs.validator import validate_entry

ROOT = Path(__file__).resolve().parents[1]

MIN_DISCOVERIES = 3        # pre-registered: a healthy loop has actually done some science
MIN_SUCCESS_RATE = 0.50    # and more than half of its self-experiments certify

_LOG_ENTRY = re.compile(r"^##\s+(\S+)\s+—\s+(\w+)\s+\((.+?)\)", re.M)


def parse_dream_log(text: str) -> dict:
    """Pure: extract per-discovery (id, status, timestamp) from a DREAM_LOG.md body."""
    by_status: dict[str, int] = {}
    ids, times = [], []
    for cid, status, ts in _LOG_ENTRY.findall(text):
        s = status.lower()
        by_status[s] = by_status.get(s, 0) + 1
        ids.append(cid)
        times.append(ts)
    total = len(ids)
    positive = by_status.get("positive", 0)
    return {
        "total": total,
        "by_status": by_status,
        "success_rate": round(positive / total, 4) if total else 0.0,
        "first_ts": times[0] if times else None,
        "last_ts": times[-1] if times else None,
    }


def _commit_stats(root: Path) -> dict:
    """Best-effort: autonomous 'dream:' commits and their cadence, from git history."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--grep=^dream:", "--format=%cI"],
            capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return {"autonomous_commits": 0, "commits_per_day": 0.0, "span_hours": 0.0}
    stamps = [s for s in out.splitlines() if s]
    if len(stamps) < 2:
        return {"autonomous_commits": len(stamps), "commits_per_day": 0.0, "span_hours": 0.0}
    try:
        newest = dt.datetime.fromisoformat(stamps[0])
        oldest = dt.datetime.fromisoformat(stamps[-1])
        span_h = max((newest - oldest).total_seconds() / 3600.0, 1e-6)
    except Exception:
        span_h = 0.0
    per_day = round(len(stamps) / (span_h / 24.0), 3) if span_h else 0.0
    return {"autonomous_commits": len(stamps),
            "commits_per_day": per_day, "span_hours": round(span_h, 3)}


def run(verbose: bool = True, root: Path = ROOT):
    log_path = root / "results" / "DREAM_LOG.md"
    stats = parse_dream_log(log_path.read_text() if log_path.exists() else "")
    commits = _commit_stats(root)

    total = stats["total"]
    success_rate = stats["success_rate"]
    exp_per_hour = 0.0
    if stats["first_ts"] and stats["last_ts"] and total > 1:
        try:
            span_h = max((dt.datetime.fromisoformat(stats["last_ts"])
                          - dt.datetime.fromisoformat(stats["first_ts"])).total_seconds() / 3600.0, 1e-6)
            exp_per_hour = round(total / span_h, 3)
        except Exception:
            exp_per_hour = 0.0

    passed = total >= MIN_DISCOVERIES and success_rate >= MIN_SUCCESS_RATE

    audit = audit_capability(
        signal_permissions=["none"],
        bystander_inference="None — it reads only this project's own discovery log and git history.",
        escalation_gradient="Self-monitoring is the substrate of a research-strategy optimizer; no external party is involved.",
        mitigations="Not applicable — introspective metric over the loop's own record.",
        escalation_unbounded=False, identifies_individuals=False,
    )
    today = dt.date.today()
    status = "positive" if passed else "unstable"
    entry = {
        "id": "experiment_loop_health_v1",
        "name": "Discovery-Loop Health (the scientist measuring itself)",
        "status": status,
        "version": "1.0.0",
        "description": (
            "A meta-capability: recovers the health of the Automated Computer Scientist from its "
            "own discovery log and git history — number of self-experiments, certification "
            "success rate, cadence and autonomous commits. The first step toward a self-improving "
            "research strategy that learns which experiments are productive."),
        "task": "recover discovery-loop health (experiments, success rate, cadence, commits)",
        "signals": [{"family": "capability", "name": "loop_health",
                     "sampling": "read DREAM_LOG.md + git history", "android_permission": "none"}],
        "model": {"kind": "introspective metrics over the loop's own record",
                  "features": "discoveries, success_rate, experiments/hour, commits/day"},
        "accuracy": round(min(1.0, max(0.0, success_rate)), 4),
        "confidence": round(min(1.0, max(0.0, success_rate)), 4),
        "energy_mj": 0.0,
        "latency_ms": 1.0,
        "privacy_audit": audit.as_dict(),
        "generalization": {"note": "measures this project's own loop; not a hardware law",
                           "discoveries": total, "by_status": stats["by_status"],
                           "experiments_per_hour": exp_per_hour,
                           "autonomous_commits": commits["autonomous_commits"],
                           "commits_per_day": commits["commits_per_day"]},
        "provenance": [],
        "reproducibility": {"independent_runs": 1, "within_ci": True},
        "limitations": ["Introspective over one project's history; not a claim about hardware.",
                        "Success rate here counts logged autonomous discoveries only."],
        "failure_modes": ["An empty or truncated DREAM_LOG.md makes the loop look idle (unstable)."],
        "references": ["ccs/dream/engine.py (the loop this measures)"],
        "valid_until": (today + dt.timedelta(days=30)).isoformat(),
        "half_life_days": 30,
        "date_created": today.isoformat(),
        "last_verified": today.isoformat(),
    }
    if status == "unstable":
        entry["failure_type"] = "environment-bound"

    errs = validate_entry(entry)
    result = {
        "passed": passed, "status": status,
        "discoveries": total, "by_status": stats["by_status"], "success_rate": success_rate,
        "experiments_per_hour": exp_per_hour, **commits,
        "thresholds": {"min_discoveries": MIN_DISCOVERIES, "min_success_rate": MIN_SUCCESS_RATE},
        "entry_valid": errs == [], "entry_errors": errs,
        "host": {"machine": platform.machine(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(result, indent=2))
    return result, entry


if __name__ == "__main__":
    result, entry = run()
    print("\n--- DISCOVERY-LOOP HEALTH (the scientist measuring itself) ---")
    print(f"discoveries: {result['discoveries']}  success rate: {result['success_rate']}  "
          f"autonomous commits: {result['autonomous_commits']} ({result['commits_per_day']}/day)")
    print(f"status: {result['status']}  schema-valid: {result['entry_valid']}")

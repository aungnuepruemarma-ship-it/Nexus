"""EXP-HW-TIMER-RES (real hardware): the effective granularity of this machine's clock.

A "Law of This Machine": no spec tells the software the true tick of `perf_counter_ns`.
We recover it — read the clock back-to-back many times and take the smallest nonzero delta
(the effective resolution) and the median delta (the read overhead). Certified positive iff
the resolution is sub-microsecond and reproduces across two independent batches.

Run: python experiments/exp_hw_timer_resolution.py
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import time

import numpy as np

from ccs.audit import audit_capability
from ccs.validator import validate_entry

MAX_RESOLUTION_NS = 1000.0     # pre-registered: "fine timer" == sub-microsecond effective tick


def _batch(n: int) -> tuple[float, float]:
    pc = time.perf_counter_ns
    xs = np.empty(n, dtype=np.int64)
    for i in range(n):
        xs[i] = pc()
    d = np.diff(xs)
    nz = d[d > 0]
    resolution = float(nz.min()) if len(nz) else float("inf")
    overhead = float(np.median(d))
    return resolution, overhead


def run(n: int = 200_000, verbose: bool = True):
    r1, o1 = _batch(n)
    r2, o2 = _batch(n)
    resolution = min(r1, r2)
    reproduced = (max(r1, r2) / min(r1, r2)) <= 2.0 if min(r1, r2) > 0 else False
    passed = resolution <= MAX_RESOLUTION_NS and reproduced

    audit = audit_capability(
        signal_permissions=["clock"],
        bystander_inference="None — it times only its own clock reads.",
        escalation_gradient="A fine clock is the enabler of most timing side channels; that is why coarse clocks are a standard mitigation.",
        mitigations="Coarsen the clock exposed to untrusted code (reduce timestamp resolution).",
        escalation_unbounded=False, identifies_individuals=False,
    )
    today = dt.date.today()
    status = "positive" if passed else "unstable"
    entry = {
        "id": "timer_resolution_v1",
        "name": "Effective Clock Resolution (recovered from timing)",
        "status": status,
        "version": "1.0.0",
        "description": (
            "Recovers the effective granularity of perf_counter_ns by reading it back-to-back "
            "and taking the smallest nonzero delta — the real tick the OS/CPU expose, not the "
            "advertised one. The median delta is the read overhead."),
        "task": "recover the effective clock resolution + read overhead",
        "signals": [{"family": "cpu", "name": "clock",
                     "sampling": "back-to-back perf_counter_ns", "android_permission": "none"}],
        "model": {"kind": "min-nonzero-delta over back-to-back clock reads",
                  "features": "consecutive perf_counter_ns deltas"},
        "accuracy": round(1.0 if passed else 0.0, 4),
        "confidence": round(min(1.0, MAX_RESOLUTION_NS / resolution) if resolution else 0.0, 4),
        "energy_mj": 0.0,
        "latency_ms": round(resolution / 1e6, 9),
        "privacy_audit": audit.as_dict(),
        "generalization": {"note": "single-host measurement; this CPU/OS clock",
                           "resolution_ns_batch1": round(r1, 2), "resolution_ns_batch2": round(r2, 2),
                           "read_overhead_ns": round((o1 + o2) / 2, 2)},
        "provenance": [],
        "reproducibility": {"independent_runs": 2, "within_ci": bool(reproduced)},
        "limitations": ["Measured on one host (Linux 6.18) in a container; the Python read "
                        "overhead sets a floor on the observable resolution."],
        "failure_modes": ["A coarse-timer platform (low-resolution clock) would fail the sub-µs bar."],
        "references": ["clock_getres(2); perf_counter_ns"],
        "valid_until": (today + dt.timedelta(days=180)).isoformat(),
        "half_life_days": 180,
        "date_created": today.isoformat(),
        "last_verified": today.isoformat(),
    }
    if status == "unstable":
        entry["failure_type"] = "oem-bound"

    errs = validate_entry(entry)
    result = {
        "passed": passed, "status": status,
        "resolution_ns": round(resolution, 3), "read_overhead_ns": round((o1 + o2) / 2, 2),
        "resolution_ns_batch1": round(r1, 3), "resolution_ns_batch2": round(r2, 3),
        "reproduced": reproduced, "threshold_ns": MAX_RESOLUTION_NS,
        "entry_valid": errs == [], "entry_errors": errs,
        "host": {"machine": platform.machine(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(result, indent=2))
    return result, entry


if __name__ == "__main__":
    result, entry = run()
    print("\n--- CLOCK RESOLUTION (real hardware) ---")
    print(f"effective resolution: {result['resolution_ns']} ns   read overhead: {result['read_overhead_ns']} ns")
    print(f"status: {result['status']}  reproduced: {result['reproduced']}  schema-valid: {result['entry_valid']}")

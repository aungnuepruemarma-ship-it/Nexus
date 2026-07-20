"""EXP-HW-SYSCALL (real hardware): the cost of crossing into the kernel on this machine.

A "Law of This Machine": time a bare syscall (``os.sched_yield``) back-to-back and recover the
user->kernel->user round-trip cost the OS actually charges — no spec, measured. Certified
positive iff the per-syscall cost is bounded and reproduces across two independent batches.

Run: python experiments/exp_hw_syscall.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import time

import numpy as np

from ccs.audit import audit_capability
from ccs.validator import validate_entry

MAX_SYSCALL_NS = 100_000.0     # pre-registered sanity ceiling (100 µs)


def _batch(n: int) -> float:
    yield_ = os.sched_yield
    pc = time.perf_counter_ns
    for _ in range(1000):      # warm
        yield_()
    t0 = pc()
    for _ in range(n):
        yield_()
    return (pc() - t0) / n


def run(n: int = 200_000, verbose: bool = True):
    s1 = _batch(n)
    s2 = _batch(n)
    ns = (s1 + s2) / 2
    spread = abs(s1 - s2) / max(s1, s2) if max(s1, s2) else 1.0
    reproduced = spread <= 0.5
    passed = reproduced and 0 < ns <= MAX_SYSCALL_NS

    audit = audit_capability(
        signal_permissions=["syscall"],
        bystander_inference="None — it times only its own syscalls.",
        escalation_gradient="Syscall timing is a coarse covert-channel medium; not exploited here.",
        mitigations="No action needed for self-measurement; untrusted code can be denied fine clocks.",
        escalation_unbounded=False, identifies_individuals=False,
    )
    today = dt.date.today()
    status = "positive" if passed else "unstable"
    entry = {
        "id": "syscall_latency_v1",
        "name": "System-Call Round-Trip Cost (recovered from timing)",
        "status": status,
        "version": "1.0.0",
        "description": (
            "Measures the user->kernel->user cost of a bare syscall (sched_yield) on this host "
            "by timing it back-to-back. The designed use of sched_yield is scheduling; the "
            "latent capability is empirical measurement of the kernel-crossing cost."),
        "task": "recover the per-syscall round-trip cost (ns)",
        "signals": [{"family": "cpu", "name": "syscall",
                     "sampling": "back-to-back sched_yield", "android_permission": "none"}],
        "model": {"kind": "timed back-to-back syscalls", "features": "ns per sched_yield"},
        "accuracy": round(min(1.0, 1.0 - spread), 4),
        "confidence": round(min(1.0, 1.0 - spread), 4),
        "energy_mj": 0.0,
        "latency_ms": round(ns / 1e6, 6),
        "privacy_audit": audit.as_dict(),
        "generalization": {"note": "single-host measurement; this OS/CPU syscall path",
                           "ns_batch1": round(s1, 2), "ns_batch2": round(s2, 2),
                           "spread": round(spread, 4)},
        "provenance": [],
        "reproducibility": {"independent_runs": 2, "within_ci": bool(reproduced)},
        "limitations": ["Measured on one host (Linux 6.18) in a container; sched_yield with no "
                        "runnable peer is a near-lower-bound on syscall cost, not a full context switch."],
        "failure_modes": ["Heavy scheduler contention widens spread past tolerance."],
        "references": ["lmbench lat_syscall"],
        "valid_until": (today + dt.timedelta(days=180)).isoformat(),
        "half_life_days": 180,
        "date_created": today.isoformat(),
        "last_verified": today.isoformat(),
    }
    if status == "unstable":
        entry["failure_type"] = "environment-bound"

    errs = validate_entry(entry)
    result = {
        "passed": passed, "status": status,
        "ns_per_syscall": round(ns, 2), "ns_batch1": round(s1, 2), "ns_batch2": round(s2, 2),
        "spread": round(spread, 4), "reproduced": reproduced, "threshold_ns": MAX_SYSCALL_NS,
        "entry_valid": errs == [], "entry_errors": errs,
        "host": {"machine": platform.machine(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(result, indent=2))
    return result, entry


if __name__ == "__main__":
    result, entry = run()
    print("\n--- SYSCALL COST (real hardware) ---")
    print(f"per-syscall: {result['ns_per_syscall']} ns  (batches {result['ns_batch1']} / {result['ns_batch2']})")
    print(f"status: {result['status']}  reproduced: {result['reproduced']}  schema-valid: {result['entry_valid']}")

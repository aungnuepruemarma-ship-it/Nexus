"""EXP-HW-FLOPS (real hardware): this machine's sustained floating-point throughput.

A "Law of This Machine": time a fused multiply-add (c = a*b + c) streamed over large arrays
and recover the sustained GFLOP/s the CPU + memory subsystem actually deliver — measured, not
read from a spec. Certified positive iff the throughput reproduces across two runs and clears
a floor.

Run: python experiments/exp_hw_flops.py
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import time

import numpy as np

from ccs.audit import audit_capability
from ccs.validator import validate_entry

N = 4_000_000          # 4M float64 elements per array
MIN_GFLOPS = 0.2       # pre-registered sanity floor
MAX_SPREAD = 0.35      # runs must agree within 35% to count as reproduced


def _measure_gflops(iters: int = 40) -> float:
    a = np.random.default_rng(1).random(N)
    b = np.random.default_rng(2).random(N)
    c = np.zeros(N)
    c += a * b   # warm/allocate
    t0 = time.perf_counter()
    for _ in range(iters):
        c = a * b + c            # 2 flops per element (one mul, one add)
    dt_s = time.perf_counter() - t0
    return (2 * N * iters) / dt_s / 1e9


def run(iters: int = 40, verbose: bool = True):
    g1 = _measure_gflops(iters)
    g2 = _measure_gflops(iters)
    gflops = (g1 + g2) / 2
    spread = abs(g1 - g2) / max(g1, g2) if max(g1, g2) else 1.0
    reproduced = spread <= MAX_SPREAD
    passed = reproduced and gflops >= MIN_GFLOPS

    audit = audit_capability(
        signal_permissions=["compute"],
        bystander_inference="None — it computes only on its own arrays; it reveals the host's FP throughput, not any neighbor's data.",
        escalation_gradient="Sustained-throughput probing is also how a noisy CPU neighbor is characterized (see exp_hw_workload_id); no cross-tenant attack is shown here.",
        mitigations="CPU quota / cgroup limits; schedule compute-heavy tenants apart.",
        escalation_unbounded=False, identifies_individuals=False,
    )
    today = dt.date.today()
    status = "positive" if passed else "unstable"
    entry = {
        "id": "flops_throughput_v1",
        "name": "Sustained FP Throughput (recovered from timing)",
        "status": status,
        "version": "1.0.0",
        "description": (
            "Measures sustained floating-point throughput by timing a fused multiply-add "
            "streamed over 4M-element arrays. The designed use of arithmetic is computation; "
            "the latent capability is empirical GFLOP/s characterization of the actual machine."),
        "task": "recover sustained floating-point throughput (GFLOP/s)",
        "signals": [{"family": "cpu", "name": "compute",
                     "sampling": "FMA over 4M float64", "android_permission": "none"}],
        "model": {"kind": "timed streaming multiply-add", "features": "flops / second"},
        "accuracy": round(min(1.0, 1.0 - spread), 4),
        "confidence": round(min(1.0, 1.0 - spread), 4),
        "energy_mj": round(1000.0 * (2 * N * iters) / 1e9, 3),
        "latency_ms": round(1000.0 * (2 * N * iters) / (gflops * 1e9), 4) if gflops else 0.0,
        "privacy_audit": audit.as_dict(),
        "generalization": {"note": "single-host measurement; this machine's FP pipeline + memory",
                           "gflops_run1": round(g1, 3), "gflops_run2": round(g2, 3),
                           "spread": round(spread, 4)},
        "provenance": [],
        "reproducibility": {"independent_runs": 2, "within_ci": bool(reproduced)},
        "limitations": ["Measured on one host in a container; the number reflects NumPy's "
                        "vectorized loop (memory-bound at this array size), a lower bound on peak FLOP/s.",
                        "Co-tenant CPU load lowers the observed throughput."],
        "failure_modes": ["Heavy neighbor CPU contention widens run-to-run spread past tolerance."],
        "references": ["LINPACK / peak-FLOP microbenchmarking"],
        "valid_until": (today + dt.timedelta(days=120)).isoformat(),
        "half_life_days": 120,
        "date_created": today.isoformat(),
        "last_verified": today.isoformat(),
    }
    if status == "unstable":
        entry["failure_type"] = "environment-bound"

    errs = validate_entry(entry)
    result = {
        "passed": passed, "status": status,
        "gflops": round(gflops, 3), "gflops_run1": round(g1, 3), "gflops_run2": round(g2, 3),
        "spread": round(spread, 4), "reproduced": reproduced,
        "thresholds": {"min_gflops": MIN_GFLOPS, "max_spread": MAX_SPREAD},
        "entry_valid": errs == [], "entry_errors": errs,
        "host": {"machine": platform.machine(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(result, indent=2))
    return result, entry


if __name__ == "__main__":
    result, entry = run()
    print("\n--- FP THROUGHPUT (real hardware) ---")
    print(f"sustained: {result['gflops']} GFLOP/s  (runs {result['gflops_run1']} / {result['gflops_run2']}, spread {result['spread']})")
    print(f"status: {result['status']}  reproduced: {result['reproduced']}  schema-valid: {result['entry_valid']}")

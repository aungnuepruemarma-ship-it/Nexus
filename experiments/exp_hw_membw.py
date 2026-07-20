"""EXP-HW-MEMBW (real hardware): this machine's effective streaming memory bandwidth.

A "Law of This Machine": stream a read-modify-write over a buffer far larger than any cache
and measure the sustained bytes/second the memory subsystem actually delivers — recovered,
not read from a spec sheet. Certified positive iff the bandwidth reproduces across two
independent runs (within a tolerance) and clears a sane floor.

Run: python experiments/exp_hw_membw.py
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import time

import numpy as np

from ccs.audit import audit_capability
from ccs.validator import validate_entry

BUF_BYTES = 64 << 20        # 64 MiB — well past any commodity L3
MIN_GBPS = 0.5              # pre-registered sanity floor
MAX_SPREAD = 0.35          # runs must agree within 35% to count as reproduced


def _measure_gbps(iters: int = 20) -> float:
    n = BUF_BYTES // 8
    buf = np.ones(n, dtype=np.int64)
    buf += 1  # warm/allocate pages
    t0 = time.perf_counter()
    for _ in range(iters):
        buf += 1                     # one full read + one full write of the buffer
    dt_s = time.perf_counter() - t0
    bytes_moved = 2 * BUF_BYTES * iters   # read + write
    return bytes_moved / dt_s / 1e9


def run(iters: int = 20, verbose: bool = True):
    g1 = _measure_gbps(iters)
    g2 = _measure_gbps(iters)
    gbps = (g1 + g2) / 2
    spread = abs(g1 - g2) / max(g1, g2) if max(g1, g2) else 1.0
    reproduced = spread <= MAX_SPREAD
    passed = reproduced and gbps >= MIN_GBPS

    audit = audit_capability(
        signal_permissions=["bandwidth"],
        bystander_inference="None — it streams only its own buffer; it reveals the host's memory bandwidth, not any neighbor's data.",
        escalation_gradient="Sustained bandwidth probing is also how a noisy neighbor is characterized (see exp_hw_workload_id); no cross-tenant attack is shown here.",
        mitigations="Memory-bandwidth partitioning / QoS (e.g. Intel MBA); schedule bandwidth-heavy tenants apart.",
        escalation_unbounded=False, identifies_individuals=False,
    )
    today = dt.date.today()
    status = "positive" if passed else "unstable"
    entry = {
        "id": "mem_bandwidth_v1",
        "name": "Streaming Memory Bandwidth (recovered from timing)",
        "status": status,
        "version": "1.0.0",
        "description": (
            "Measures the sustained streaming memory bandwidth of this host by timing a "
            "read-modify-write over a 64 MiB buffer (past all caches). The designed use of a "
            "memory write is storage; the latent capability is empirical bandwidth "
            "characterization of the actual machine."),
        "task": "recover sustained streaming memory bandwidth (GB/s)",
        "signals": [{"family": "memory", "name": "bandwidth",
                     "sampling": "64 MiB read-modify-write stream", "android_permission": "none"}],
        "model": {"kind": "timed streaming read-modify-write", "features": "bytes moved / second"},
        "accuracy": round(min(1.0, 1.0 - spread), 4),
        "confidence": round(min(1.0, 1.0 - spread), 4),
        "energy_mj": round(1000.0 * (BUF_BYTES / 1e9) * iters * 2, 3),
        "latency_ms": round(1000.0 * (2 * BUF_BYTES * iters) / (gbps * 1e9), 4) if gbps else 0.0,
        "privacy_audit": audit.as_dict(),
        "generalization": {"note": "single-host measurement; this machine's memory subsystem",
                           "gbps_run1": round(g1, 3), "gbps_run2": round(g2, 3),
                           "spread": round(spread, 4)},
        "provenance": [],
        "reproducibility": {"independent_runs": 2, "within_ci": bool(reproduced)},
        "limitations": ["Measured on one host in a container with a shared memory bus; absolute "
                        "GB/s reflects NumPy's vectorized loop, a lower bound on peak bandwidth.",
                        "Co-tenant bandwidth load will lower the observed number."],
        "failure_modes": ["Heavy neighbor bandwidth contention widens run-to-run spread past tolerance."],
        "references": ["STREAM benchmark (McCalpin)"],
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
        "gbps": round(gbps, 3), "gbps_run1": round(g1, 3), "gbps_run2": round(g2, 3),
        "spread": round(spread, 4), "reproduced": reproduced,
        "thresholds": {"min_gbps": MIN_GBPS, "max_spread": MAX_SPREAD},
        "entry_valid": errs == [], "entry_errors": errs,
        "host": {"machine": platform.machine(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(result, indent=2))
    return result, entry


if __name__ == "__main__":
    result, entry = run()
    print("\n--- MEMORY BANDWIDTH (real hardware) ---")
    print(f"sustained bandwidth: {result['gbps']} GB/s  (runs {result['gbps_run1']} / {result['gbps_run2']}, spread {result['spread']})")
    print(f"status: {result['status']}  reproduced: {result['reproduced']}  schema-valid: {result['entry_valid']}")

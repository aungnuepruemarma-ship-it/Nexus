"""EXP-HW-MEMPATTERN (real hardware): the random-vs-sequential memory access penalty.

A "Law of This Machine": the same bytes cost far more to touch in a random order than in
order, because sequential access rides cache lines and the hardware prefetcher while random
access defeats both. We recover that penalty ratio over a buffer larger than cache — measured,
not assumed. Certified positive iff the penalty is real (>1.1x) and reproduces across two runs.

Run: python experiments/exp_hw_mempattern.py
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import time

import numpy as np

from ccs.audit import audit_capability
from ccs.validator import validate_entry

N = 8_000_000          # 8M int64 = 64 MiB, well past any commodity L3
MIN_PENALTY = 1.10     # pre-registered: random must be >=10% slower than sequential
MAX_SPREAD = 0.35      # runs must agree within 35% to count as reproduced


def _penalty() -> tuple[float, float, float]:
    rng = np.random.default_rng(0)
    a = rng.integers(0, 1 << 30, size=N, dtype=np.int64)
    idx = rng.permutation(N)          # random gather order (built outside the timed region)
    _ = a.sum(); _ = a[idx].sum()     # warm

    t0 = time.perf_counter()
    for _ in range(3):
        s_seq = a.sum()               # sequential read (prefetch-friendly)
    seq = (time.perf_counter() - t0) / 3

    t0 = time.perf_counter()
    for _ in range(3):
        s_rnd = a[idx].sum()          # random gather (prefetch-defeating)
    rnd = (time.perf_counter() - t0) / 3
    return rnd / seq if seq else 1.0, seq, rnd


def run(verbose: bool = True):
    p1, seq1, rnd1 = _penalty()
    p2, seq2, rnd2 = _penalty()
    penalty = (p1 + p2) / 2
    spread = abs(p1 - p2) / max(p1, p2) if max(p1, p2) else 1.0
    reproduced = spread <= MAX_SPREAD
    passed = reproduced and penalty >= MIN_PENALTY

    audit = audit_capability(
        signal_permissions=["access_pattern"],
        bystander_inference="None — it walks only its own array; it reveals the host's cache-line/prefetch behaviour, not any neighbor's data.",
        escalation_gradient="Access-pattern timing underlies cache/prefetch side channels; only self-measured here.",
        mitigations="Constant-time / oblivious access patterns in secret-dependent code; cache partitioning.",
        escalation_unbounded=False, identifies_individuals=False,
    )
    today = dt.date.today()
    status = "positive" if passed else "unstable"
    entry = {
        "id": "memory_access_penalty_v1",
        "name": "Random-vs-Sequential Access Penalty (recovered from timing)",
        "status": status,
        "version": "1.0.0",
        "description": (
            "Measures how much slower random memory access is than sequential access over a "
            "64 MiB buffer — the empirical benefit this machine's cache lines + hardware "
            "prefetcher give ordered access. The designed use of memory is storage; the latent "
            "capability is recovering the access-pattern penalty of the actual hardware."),
        "task": "recover the random/sequential memory-access penalty ratio",
        "signals": [{"family": "memory", "name": "access_pattern",
                     "sampling": "sequential vs random gather over 64 MiB", "android_permission": "none"}],
        "model": {"kind": "timed sequential sum vs random-gather sum", "features": "random_time / sequential_time"},
        "accuracy": round(min(1.0, 1.0 - spread), 4),
        "confidence": round(min(1.0, 1.0 - spread), 4),
        "energy_mj": round(1000.0 * (N * 8 / 1e9) * 6, 3),
        "latency_ms": round(1000.0 * (rnd1 + rnd2) / 2, 4),
        "privacy_audit": audit.as_dict(),
        "generalization": {"note": "single-host measurement; this machine's cache-line + prefetch behaviour",
                           "penalty_run1": round(p1, 3), "penalty_run2": round(p2, 3),
                           "spread": round(spread, 4)},
        "provenance": [],
        "reproducibility": {"independent_runs": 2, "within_ci": bool(reproduced)},
        "limitations": ["Measured on one host in a container; NumPy fancy-indexing also allocates "
                        "the gather output, so the ratio is a conservative lower bound on the raw penalty.",
                        "Co-tenant memory-bandwidth load shifts the ratio."],
        "failure_modes": ["A buffer that fits in cache would erase the penalty (ratio ~1)."],
        "references": ["cache-line / hardware-prefetcher microbenchmarking"],
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
        "penalty": round(penalty, 3), "penalty_run1": round(p1, 3), "penalty_run2": round(p2, 3),
        "seq_ms": round(1000.0 * (seq1 + seq2) / 2, 4), "rnd_ms": round(1000.0 * (rnd1 + rnd2) / 2, 4),
        "spread": round(spread, 4), "reproduced": reproduced,
        "thresholds": {"min_penalty": MIN_PENALTY, "max_spread": MAX_SPREAD},
        "entry_valid": errs == [], "entry_errors": errs,
        "host": {"machine": platform.machine(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(result, indent=2))
    return result, entry


if __name__ == "__main__":
    result, entry = run()
    print("\n--- MEMORY ACCESS PENALTY (real hardware) ---")
    print(f"random/sequential penalty: {result['penalty']}x  (seq {result['seq_ms']}ms vs random {result['rnd_ms']}ms)")
    print(f"status: {result['status']}  reproduced: {result['reproduced']}  schema-valid: {result['entry_valid']}")

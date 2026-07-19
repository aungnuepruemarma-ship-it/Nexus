"""Recover this machine's memory hierarchy from timing alone — a "law of this machine".

A Silicon-Archaeologist / Latent-Physics probe: nobody tells the software where the caches
end. We recover it empirically. Chase a single-cycle pointer permutation through buffers of
geometrically increasing size and time each dependent load. While the working set fits in a
fast level of the hierarchy, per-access latency is flat; once it spills to a slower level
(cache -> DRAM), latency jumps. The *shape* of the latency-vs-working-set curve is the
machine's own cache/memory topology, discovered rather than declared.

The data-dependent pointer chase defeats hardware prefetch, so each step pays the true
access latency of the level the working set currently lives in. Pure Python adds a fixed
per-step interpreter overhead; because that overhead is *constant across working-set size*,
it shifts the whole curve up by a constant but preserves the position and ratio of the
level-transition jump — which is what we certify.

Everything here measures the machine it runs on; there is no simulation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Geometric working-set ladder: 4 KiB (inside L1) up to 32 MiB (well into DRAM on a
# commodity core). Powers of two so the cache-size boundaries fall between rungs.
DEFAULT_SIZES_BYTES = tuple(1 << k for k in range(12, 26))   # 4 KiB .. 32 MiB


def _chase_buffer(n_int64: int, seed: int) -> np.ndarray:
    """Buffer whose entries form one Hamiltonian cycle (prefetch-defeating chase)."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n_int64)
    buf = np.empty(n_int64, dtype=np.int64)
    buf[perm] = np.roll(perm, -1)
    return buf


def access_latency_ns(n_bytes: int, steps: int = 20_000, repeats: int = 3,
                      seed: int = 12345) -> float:
    """Median nanoseconds per dependent load for a working set of ``n_bytes``."""
    import time
    n = max(8, n_bytes // 8)
    buf = _chase_buffer(n, seed)
    pc = time.perf_counter_ns

    def _chase(start: int) -> int:
        idx = start
        b = buf
        for _ in range(steps):
            idx = b[idx]
        return int(idx)

    _chase(0)  # warm TLB/caches for this buffer
    samples = np.empty(repeats, dtype=np.float64)
    idx = 0
    for r in range(repeats):
        t0 = pc()
        idx = _chase(idx % n)
        samples[r] = (pc() - t0) / steps
    return float(np.median(samples))


def latency_curve(sizes_bytes=DEFAULT_SIZES_BYTES, steps: int = 20_000,
                  repeats: int = 3, seed: int = 12345) -> dict[int, float]:
    """Map each working-set size (bytes) -> median ns/access."""
    return {sz: access_latency_ns(sz, steps=steps, repeats=repeats, seed=seed)
            for sz in sizes_bytes}


@dataclass
class Hierarchy:
    """A detected memory-hierarchy transition recovered from a latency curve."""
    n_levels: int                 # number of distinct latency tiers (>=1)
    boundary_bytes: int           # working-set size at the largest latency jump
    fast_latency_ns: float        # median latency of the resident (fast) tier
    slow_latency_ns: float        # median latency of the spilled (slow) tier
    jump_ratio: float             # slow/fast — how sharp the cache->DRAM cliff is
    curve: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "n_levels": self.n_levels,
            "boundary_bytes": self.boundary_bytes,
            "boundary_human": _human_bytes(self.boundary_bytes),
            "fast_latency_ns": round(self.fast_latency_ns, 2),
            "slow_latency_ns": round(self.slow_latency_ns, 2),
            "jump_ratio": round(self.jump_ratio, 3),
            "curve_ns": {_human_bytes(k): round(v, 2) for k, v in self.curve.items()},
        }


def _human_bytes(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n}{unit}"
        n //= 1024
    return f"{n}TiB"


def detect_hierarchy(curve: dict[int, float], edge: int = 3,
                     level_threshold: float = 1.30) -> Hierarchy:
    """Recover the hierarchy from a size->latency curve (plateau-based, noise-robust).

    Reads the curve like a memory-mountain: the ``fast`` latency is the median of the
    smallest ``edge`` working sets (always cache-resident) and the ``slow`` latency is the
    median of the largest ``edge`` working sets (always in DRAM). ``jump_ratio = slow/fast``
    is the cache->DRAM cliff. The boundary is the smallest working set whose latency crosses
    the midpoint between the two plateaus — robust to single-point spikes, unlike an
    argmax-of-consecutive-jumps. ``n_levels`` is 2 when a real cliff is present, else 1."""
    sizes = sorted(curve)
    lat = [curve[s] for s in sizes]
    if len(sizes) <= 2 * edge:
        edge = max(1, len(sizes) // 3)
    fast = float(np.median(lat[:edge]))
    slow = float(np.median(lat[-edge:]))
    jump = slow / fast if fast else 1.0
    midpoint = fast + 0.5 * (slow - fast)
    # Boundary = smallest working set from which the SLOW tier is sustained (>=60% of the
    # larger sizes sit above the midpoint). Requiring persistence, not a single crossing,
    # ignores lone latency spikes inside the cache-resident plateau.
    above = [v >= midpoint for v in lat]
    boundary = sizes[-1]
    for i, s in enumerate(sizes):
        tail = above[i:]
        if above[i] and sum(tail) / len(tail) >= 0.6:
            boundary = s
            break
    n_levels = 2 if jump >= level_threshold else 1
    return Hierarchy(n_levels=n_levels, boundary_bytes=boundary,
                     fast_latency_ns=fast, slow_latency_ns=slow,
                     jump_ratio=jump, curve=dict(curve))

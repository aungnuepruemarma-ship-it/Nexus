"""Fast, deterministic tests for the memory-hierarchy (cache-ladder) capability.

Follows the repo convention: the noise-robust tier-detection logic is tested on synthetic
curves (no live timing), plus a schema check on the built entry."""
import numpy as np

from ccs.hardware import cache_ladder as cl
from ccs.validator import validate_entry


def test_detect_hierarchy_finds_cliff_and_boundary():
    # cache-resident plateau at ~110 ns up to 1 MiB, DRAM plateau at ~210 ns from 4 MiB on.
    sizes = [1 << k for k in range(12, 26)]  # 4 KiB .. 32 MiB
    curve = {s: (110.0 if s <= (1 << 20) else 210.0) for s in sizes}
    h = cl.detect_hierarchy(curve)
    assert h.n_levels == 2
    assert h.jump_ratio > 1.6                      # ~210/110
    assert h.fast_latency_ns < h.slow_latency_ns
    # boundary is the first spilled size (2 MiB, the first > 1 MiB in this synthetic curve)
    assert h.boundary_bytes == (1 << 21)


def test_detect_hierarchy_robust_to_single_spike():
    # a lone spike in the cache-resident region must not be mistaken for the boundary
    sizes = [1 << k for k in range(12, 26)]
    curve = {s: 110.0 for s in sizes}
    curve[1 << 15] = 160.0                          # 32 KiB transient spike
    for s in sizes:
        if s >= (1 << 22):                          # real DRAM plateau from 4 MiB
            curve[s] = 210.0
    h = cl.detect_hierarchy(curve)
    assert h.boundary_bytes >= (1 << 21)            # not fooled down to 32 KiB
    assert h.jump_ratio > 1.6


def test_flat_curve_is_single_level():
    sizes = [1 << k for k in range(12, 24)]
    curve = {s: 100.0 + np.random.default_rng(0).normal(0, 1) for s in sizes}
    h = cl.detect_hierarchy(curve)
    assert h.n_levels == 1
    assert h.jump_ratio < 1.30


def test_pointer_chase_buffer_is_single_cycle():
    buf = cl._chase_buffer(4096, seed=3)
    seen, idx = set(), 0
    for _ in range(len(buf)):
        seen.add(idx)
        idx = int(buf[idx])
    assert len(seen) == len(buf) and idx == 0


def test_cache_ladder_entry_is_schema_valid():
    # a short live run (small sweep) — fast enough for CI, exercises the real path end to end.
    # steps kept high enough that even cache-resident chases clock a nonzero median.
    from experiments.exp_hw_cache_ladder import run
    result, entry = run(steps=12_000, repeats=2, verbose=False)
    assert entry is not None
    assert validate_entry(entry) == []
    assert result["status"] in ("positive", "unstable")
    assert entry["status"] in ("positive", "unstable")

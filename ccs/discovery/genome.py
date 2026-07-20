"""Hardware Genome — a reproducible fingerprint of this machine's measurable traits.

Idea #3 ("Hardware Genome"): every host develops a unique vector of measurable traits, like
biological DNA. We harvest traits from the same honest primitives the certified capabilities
use (timing distribution shape, entropy of the timing LSB, the cache/memory latency ladder,
memory-vs-compute ratio) and assemble:

  * ``traits``      — the full float vector (dozens of real measured numbers);
  * ``signature``   — the noise-robust, quantized subset that is stable run to run;
  * ``genome_hash`` — a SHA-256 over the canonical signature: the host's DNA barcode.

Two runs on the same host produce the same ``genome_hash`` (the signature is bucketed coarsely
enough to absorb measurement noise); different hosts diverge. ``stability()`` measures which
traits are reproducible, so the genome only fingerprints on the parts that actually hold.

All traits are measured on the host; nothing is simulated.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from dataclasses import dataclass, field

import numpy as np

from ccs.hardware import probes, cache_ladder as cl, workload_id as wid


def _shape(d: np.ndarray, prefix: str) -> dict[str, float]:
    d = np.asarray(d, dtype=np.float64)
    med = np.median(d)
    mn = d.min()
    return {
        f"{prefix}.median_ns": float(med),
        f"{prefix}.mean_over_median": float(d.mean() / med) if med else 0.0,
        f"{prefix}.p90_over_median": float(np.percentile(d, 90) / med) if med else 0.0,
        f"{prefix}.p99_over_median": float(np.percentile(d, 99) / med) if med else 0.0,
        f"{prefix}.floor_ratio": float(med / mn) if mn else 0.0,
        f"{prefix}.cv": float(d.std() / d.mean()) if d.mean() else 0.0,
    }


def harvest_traits(*, light: bool = False) -> dict[str, float]:
    """Measure the host and return a flat dict of real, named traits.

    ``light`` uses smaller samples (for fast/repeated calls, e.g. stability sweeps)."""
    traits: dict[str, float] = {}

    # --- timer + host facts -------------------------------------------------
    t0 = time.perf_counter_ns()
    for _ in range(64):
        time.perf_counter_ns()
    traits["timer.call_ns"] = (time.perf_counter_ns() - t0) / 64.0
    traits["host.n_cpus"] = float(os.cpu_count() or 1)

    # --- compute probe (register-bound) distribution shape ------------------
    n = 400 if light else 1200
    traits.update(_shape(probes.jitter_deltas(n, work_iters=150, warmup=50), "compute"))

    # --- memory probe (pointer chase) distribution shape --------------------
    traits.update(_shape(wid.memory_probe(120 if light else 240, steps=2048), "memory"))
    traits["cross.mem_over_compute"] = (
        traits["memory.median_ns"] / traits["compute.median_ns"]
        if traits["compute.median_ns"] else 0.0)

    # --- entropy of the timing LSB ------------------------------------------
    ns = 40_000 if light else 120_000
    st = time.perf_counter()
    rep = probes.assess_entropy(probes.jitter_deltas(ns, work_iters=150, warmup=200),
                               nbits=1, elapsed_s=time.perf_counter() - st)
    traits["entropy.whitened_min_entropy"] = rep.whitened_min_entropy
    traits["entropy.whitened_monobit_bias"] = rep.whitened_monobit_bias

    # --- cache/memory ladder: full curve + recovered hierarchy --------------
    steps = 6_000 if light else 20_000
    curve = cl.latency_curve(steps=steps, repeats=2)
    for sz, lat in curve.items():
        traits[f"cache.lat_ns.{cl._human_bytes(sz)}"] = float(lat)
    h = cl.detect_hierarchy(curve)
    traits["cache.jump_ratio"] = h.jump_ratio
    traits["cache.boundary_log2"] = float(h.boundary_bytes.bit_length() - 1)
    traits["cache.fast_latency_ns"] = h.fast_latency_ns
    traits["cache.slow_latency_ns"] = h.slow_latency_ns
    traits["cache.n_levels"] = float(h.n_levels)

    return traits


# Traits that are stable enough to fingerprint on, with the quantization (buckets) that
# absorbs run-to-run measurement noise. Ratios/counts are the reproducible structure; raw
# nanosecond levels drift and are deliberately excluded from the signature.
_SIGNATURE_QUANTIZERS: dict[str, callable] = {
    "host.n_cpus": lambda v: int(v),
    "cache.n_levels": lambda v: int(round(v)),
    "cache.boundary_log2": lambda v: int(round(v)),
    "cache.jump_ratio": lambda v: round(v, 1),
    "compute.floor_ratio": lambda v: round(v, 1),
    "memory.floor_ratio": lambda v: round(v, 1),
    "cross.mem_over_compute": lambda v: int(round(v)),
    "entropy.whitened_min_entropy": lambda v: round(v, 1),
}


def signature(traits: dict[str, float]) -> dict:
    """The noise-robust, quantized subset used for the genome hash."""
    sig = {}
    for k, q in _SIGNATURE_QUANTIZERS.items():
        if k in traits:
            sig[k] = q(traits[k])
    return sig


def genome_hash(sig: dict) -> str:
    canonical = json.dumps(sig, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()[:32]


@dataclass
class Genome:
    traits: dict[str, float]
    signature: dict
    genome_hash: str
    host: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "genome_hash": self.genome_hash,
            "signature": self.signature,
            "n_traits": len(self.traits),
            "traits": {k: round(v, 5) for k, v in self.traits.items()},
            "host": self.host,
        }


def sequence(*, light: bool = False) -> Genome:
    """Measure the host and assemble its genome."""
    traits = harvest_traits(light=light)
    sig = signature(traits)
    return Genome(traits=traits, signature=sig, genome_hash=genome_hash(sig),
                  host={"machine": platform.machine(), "processor": platform.processor(),
                        "python": platform.python_version()})


def stability(runs: int = 3, *, light: bool = True) -> dict:
    """Sequence the genome several times; report per-trait reproducibility + hash agreement.

    A trait is 'stable' if its coefficient of variation across runs is small (< 0.10)."""
    seqs = [sequence(light=light) for _ in range(runs)]
    keys = sorted(set().union(*[s.traits for s in seqs]))
    per_trait = {}
    for k in keys:
        vals = np.array([s.traits[k] for s in seqs if k in s.traits], dtype=np.float64)
        mean = vals.mean()
        cv = float(vals.std() / mean) if mean else 0.0
        per_trait[k] = {"mean": round(float(mean), 4), "cv": round(cv, 4),
                        "stable": bool(cv < 0.10)}
    hashes = [s.genome_hash for s in seqs]
    return {
        "runs": runs,
        "genome_hashes": hashes,
        "hash_agreement": len(set(hashes)) == 1,
        "n_traits": len(keys),
        "n_stable_traits": sum(1 for v in per_trait.values() if v["stable"]),
        "per_trait": per_trait,
    }

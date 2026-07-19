"""Real signal collection for co-located workload-TYPE classification.

A sibling of ``probes.py``. Where ``cpu_contention_sensor`` counts how *many* compute
tenants share the core, this module asks a different question: what *kind* of work is a
co-located neighbor doing — nothing, compute, or memory? It is pure self-measurement on
the host (defensive observability for noisy-neighbor diagnosis), built from two timing
micro-probes and a monotonic clock. No /proc, no cgroup, no OS load API, no cross-process
communication.

Physical basis (the claim the falsifier tests):

  * a **register-bound arithmetic probe** (reuses ``probes._work``): its time is dominated
    by how much CPU *time* the measurer gets. A CPU-bound neighbor that oversubscribes the
    cores preempts the measurer for whole scheduler slices, which lands in the *tail* of the
    timing distribution — the mean and ``mean/median`` ratio inflate even when the median
    barely moves.
  * an **~8 MB pointer-chase memory probe**: a latency-bound walk over a buffer far larger
    than L2/L3, so each step is a likely cache miss. A neighbor saturating shared LLC /
    memory bandwidth lifts the whole memory-probe distribution — including its *median* —
    because every miss costs more, independent of scheduling.

So the two probes react to different physics:

    class          compute probe            memory probe
    ------------   ----------------------   -----------------------------
    idle           baseline                 baseline
    cpu_bound      heavy tail (preemption)  heavy tail (preemption)
    memory_bound   mild tail                elevated median + tail (bandwidth)

The asymmetry is what separates the loaded classes: cpu_bound is a *preemption* signature
(tail inflation on both probes, memory median roughly unchanged), while memory_bound is a
*bandwidth* signature (the memory-probe median itself rises). Neither probe alone is
sufficient, so the two-signal candidate is compared against each single-signal baseline by
``ccs.harness.falsify``.

NOTE: CPU affinity is only advisory in this container (pinning to a single core does not
produce time-slicing contention — verified empirically), so unlike ``cpu_contention_sensor``
this capability does not pin; it oversubscribes every core instead. The measured verdict on
this host is recorded honestly in the registry, whatever it turns out to be.

Everything here measures the machine it runs on; there is no simulation.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time

import numpy as np

from ccs.hardware import probes

WORKLOAD_CLASSES = ("idle", "cpu_bound", "memory_bound")

MEM_BUF_INT64 = 1 << 20   # 1,048,576 int64 = 8 MiB pointer-chase buffer
CPU_OVERSUB = 4           # cpu_bound spawns CPU_OVERSUB x n_cpus register burners
MEM_WORKER_BYTES = 32 << 20   # 32 MiB streamed per memory-bandwidth worker


# ---------------------------------------------------------------------------
# Compute probe: reuse the register-bound xorshift workload from probes.py so the
# two capabilities share one honest primitive.
# ---------------------------------------------------------------------------

def compute_probe(n: int, work_iters: int = 150, warmup: int = 50) -> np.ndarray:
    """``n`` nanosecond timings of the fixed register-bound workload ``probes._work``."""
    pc = time.perf_counter_ns
    for _ in range(warmup):
        probes._work(work_iters)
    out = np.empty(n, dtype=np.int64)
    w = work_iters
    work = probes._work
    for i in range(n):
        t0 = pc()
        work(w)
        out[i] = pc() - t0
    return out


# ---------------------------------------------------------------------------
# Memory probe: a single-cycle pointer chase over an ~8 MB buffer. Data-dependent
# loads defeat prefetch, so each step's latency reflects cache/memory pressure.
# ---------------------------------------------------------------------------

_CHASE_CACHE: dict[int, np.ndarray] = {}


def _pointer_chase_buffer(n_int64: int = MEM_BUF_INT64, seed: int = 0xC0FFEE) -> np.ndarray:
    """Build (and cache) a buffer whose entries form one big permutation cycle.

    ``buf[i]`` is the index to visit after ``i``; following it ``k`` times performs ``k``
    dependent, cache-unfriendly loads. Built vectorized once, then reused (read-only)."""
    buf = _CHASE_CACHE.get(n_int64)
    if buf is None:
        rng = np.random.default_rng(seed)
        perm = rng.permutation(n_int64)
        buf = np.empty(n_int64, dtype=np.int64)
        buf[perm] = np.roll(perm, -1)   # perm[i] -> perm[i+1], a single Hamiltonian cycle
        _CHASE_CACHE[n_int64] = buf
    return buf


def memory_probe(n: int, steps: int = 2048, warmup: int = 8) -> np.ndarray:
    """``n`` nanosecond timings of a fixed ``steps``-long pointer chase over ~8 MB."""
    buf = _pointer_chase_buffer()
    pc = time.perf_counter_ns
    mask = len(buf) - 1  # power-of-two length: cheap wrap, keeps overhead off the clock

    def _chase(start: int) -> int:
        idx = start
        b = buf
        for _ in range(steps):
            idx = b[idx]
        return int(idx)

    for _ in range(warmup):
        _chase(0)
    out = np.empty(n, dtype=np.int64)
    idx = 0
    for i in range(n):
        t0 = pc()
        idx = _chase(idx & mask)
        out[i] = pc() - t0
    return out


# ---------------------------------------------------------------------------
# Typed background workloads = ground truth. idle / cpu_bound / memory_bound.
# ---------------------------------------------------------------------------

def _mem_burn(stop_flag, cpu, nbytes):
    """Stream read+write over a large buffer to saturate memory/LLC bandwidth."""
    if cpu is not None:
        try:
            os.sched_setaffinity(0, {cpu})
        except Exception:
            pass
    buf = np.ones(max(8, nbytes // 8), dtype=np.int64)
    while not stop_flag.value:
        buf += 1          # full-array read-modify-write => high bandwidth, poor locality
        buf ^= 0x5A5A5A5A


class WorkloadGenerator:
    """Context manager that runs a typed background workload as ground truth.

    ``idle``          — no background processes.
    ``cpu_bound``     — ``CPU_OVERSUB x n_cpus`` register-bound burners (oversubscribing
                        every core). CPU affinity is only advisory in this container, so
                        pinning to one core does not create contention; oversubscribing all
                        cores does. The measurer is then preempted for whole scheduler
                        slices, which shows up as heavy-tailed timings (mean/tail inflate
                        even when the median does not) on BOTH probes.
    ``memory_bound``  — one bandwidth-streaming worker per core, hammering shared LLC /
                        memory bandwidth. This lifts the memory probe's whole distribution
                        (median included), with less of the pure-preemption tail that marks
                        cpu_bound — the asymmetry the classifier keys on.
    """

    def __init__(self, kind: str, n_cpus: int | None = None):
        if kind not in WORKLOAD_CLASSES:
            raise ValueError(f"unknown workload kind: {kind!r}")
        self.kind = kind
        self.n_cpus = n_cpus or (os.cpu_count() or 1)
        self.procs: list[mp.Process] = []
        self._stop = mp.Value("b", False)

    def __enter__(self):
        self._stop.value = False
        if self.kind == "cpu_bound":
            for _ in range(max(3, CPU_OVERSUB * self.n_cpus)):
                p = mp.Process(target=probes._burn, args=(self._stop, None), daemon=True)
                p.start()
                self.procs.append(p)
        elif self.kind == "memory_bound":
            for _ in range(max(3, 2 * self.n_cpus)):
                p = mp.Process(target=_mem_burn, args=(self._stop, None, MEM_WORKER_BYTES), daemon=True)
                p.start()
                self.procs.append(p)
        # idle: nothing to start.
        if self.procs:
            time.sleep(0.3)  # let the scheduler settle and load ramp up
        return self

    def __exit__(self, *exc):
        self._stop.value = True
        for p in self.procs:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        self.procs.clear()


# ---------------------------------------------------------------------------
# Per-window features. Pure ``_features_from_timings`` is unit-testable with injected
# arrays; ``window_features`` collects live probe bursts and delegates to it.
# ---------------------------------------------------------------------------

def _shape_features(d: np.ndarray) -> list[float]:
    """Drift-aware distribution-shape features for one probe's timing array."""
    d = np.asarray(d, dtype=np.float64)
    med = np.median(d)
    mean = np.mean(d)
    p90 = np.percentile(d, 90)
    mn = d.min()
    return [
        mean,
        float(np.std(d)),
        med,
        mean / med if med else 0.0,        # inflation: time-slicing / contention lifts mean
        p90 / med if med else 0.0,         # tail/contention ratio
        med / mn if mn else 0.0,           # floor ratio (drift-invariant baseline)
    ]


def _features_from_timings(compute_ns: np.ndarray, mem_ns: np.ndarray) -> np.ndarray:
    """12-D feature vector: 6 compute-probe + 6 memory-probe shape features.

    Each column belongs to exactly one probe (see ``WORKLOAD_FEATURE_SIGNALS``) so the
    falsifier's single-signal baselines stay honest — no column mixes both probes."""
    return np.array(_shape_features(compute_ns) + _shape_features(mem_ns), dtype=np.float64)


def window_features(compute_probes: int = 240, work_iters: int = 150,
                    memory_probes: int = 180, chase_steps: int = 2048) -> np.ndarray:
    """One window: a burst of compute-probe timings and a burst of memory-probe timings."""
    c = compute_probe(compute_probes, work_iters=work_iters)
    m = memory_probe(memory_probes, steps=chase_steps)
    return _features_from_timings(c, m)


_SHAPE_SUFFIXES = ["mean", "std", "median", "mean_over_median", "p90_over_median", "floor_ratio"]

WORKLOAD_FEATURE_NAMES = (
    [f"compute_probe.0.{s}" for s in _SHAPE_SUFFIXES]
    + [f"mem_probe.0.{s}" for s in _SHAPE_SUFFIXES]
)

WORKLOAD_FEATURE_SIGNALS = (
    ["compute_probe"] * len(_SHAPE_SUFFIXES) + ["mem_probe"] * len(_SHAPE_SUFFIXES)
)

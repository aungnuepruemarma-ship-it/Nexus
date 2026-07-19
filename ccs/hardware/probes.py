"""Real signal collection from the host CPU.

Two latent capabilities are probed here, both built only on a monotonic clock and a
busy loop — signals whose *designed* uses are timekeeping and computation:

  1. timing jitter as a physical entropy source (nanosecond variation in the time to
     run a fixed workload is driven by microarchitectural + scheduler + interrupt
     noise);
  2. the same jitter as a load/contention sensor (per-iteration wall time grows when
     other work contends for the cores), with no /proc access.

Everything here measures the machine it runs on; there is no simulation.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time
import zlib
from dataclasses import dataclass

import numpy as np


def pin_current(cpu: int) -> bool:
    """Pin the calling process to a single CPU (Linux). Returns success."""
    try:
        os.sched_setaffinity(0, {cpu})
        return True
    except Exception:
        return False


def unpin_current() -> bool:
    """Restore the calling process's affinity to all CPUs. Undoes ``pin_current`` so
    process-global affinity does not leak between experiments."""
    try:
        os.sched_setaffinity(0, set(range(os.cpu_count() or 1)))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixed workload whose timing we measure. Kept in pure Python so its duration is
# dominated by interpreter/microarchitecture jitter rather than a libc fast path.
# ---------------------------------------------------------------------------

def _work(k: int) -> int:
    x = 88172645463325252 & 0xFFFFFFFFFFFFFFFF
    for _ in range(k):
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 7
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
    return x


def jitter_deltas(n: int, work_iters: int = 200, warmup: int = 500) -> np.ndarray:
    """Return ``n`` nanosecond timings of a fixed workload."""
    pc = time.perf_counter_ns
    for _ in range(warmup):
        _work(work_iters)
    out = np.empty(n, dtype=np.int64)
    w = work_iters
    for i in range(n):
        t0 = pc()
        _work(w)
        out[i] = pc() - t0
    return out


# ---------------------------------------------------------------------------
# Entropy harvesting.
# ---------------------------------------------------------------------------

def raw_lsb_bits(deltas: np.ndarray, nbits: int = 1) -> np.ndarray:
    """Extract the low ``nbits`` of each timing (XOR-folded to one bit each)."""
    d = deltas.astype(np.int64)
    if nbits == 1:
        return (d & 1).astype(np.uint8)
    bits = np.zeros(len(d), dtype=np.uint8)
    for b in range(nbits):
        bits ^= ((d >> b) & 1).astype(np.uint8)
    return bits


def von_neumann(bits: np.ndarray) -> np.ndarray:
    """Von Neumann debiasing: map bit pairs 01->0, 10->1, drop 00/11.

    Removes first-order bias at the cost of throughput. Output is unbiased if input
    bits are independent (not necessarily so — hence we also test the result)."""
    b = bits[: len(bits) // 2 * 2].reshape(-1, 2)
    keep = b[:, 0] != b[:, 1]
    return b[keep, 0]


def bits_to_bytes(bits: np.ndarray) -> bytes:
    n = len(bits) // 8 * 8
    if n == 0:
        return b""
    return np.packbits(bits[:n]).tobytes()


# ---- entropy / randomness tests -------------------------------------------

def min_entropy_mcv(bits: np.ndarray, symbol_bits: int = 8) -> float:
    """NIST SP 800-90B-style most-common-value min-entropy, in bits per output bit.

    Groups the stream into ``symbol_bits``-bit symbols, finds p_max = frequency of the
    most common symbol, and returns -log2(p_max) / symbol_bits (per-bit min-entropy).
    """
    n = len(bits) // symbol_bits * symbol_bits
    if n == 0:
        return 0.0
    syms = bits[:n].reshape(-1, symbol_bits)
    vals = syms.dot(1 << np.arange(symbol_bits)[::-1])
    counts = np.bincount(vals, minlength=1 << symbol_bits)
    p_max = counts.max() / counts.sum()
    return float(-np.log2(p_max) / symbol_bits)


def monobit_bias(bits: np.ndarray) -> float:
    """|fraction of ones - 0.5| (0 = perfectly balanced)."""
    return float(abs(bits.mean() - 0.5)) if len(bits) else 0.5


def runs_z(bits: np.ndarray) -> float:
    """NIST runs-test z-score (|z| small => run structure consistent with random)."""
    n = len(bits)
    pi = bits.mean()
    if n < 2 or pi in (0.0, 1.0):
        return float("inf")
    vobs = 1 + int(np.sum(bits[1:] != bits[:-1]))
    num = vobs - 2 * n * pi * (1 - pi)
    den = 2 * np.sqrt(2 * n) * pi * (1 - pi)
    return float(num / den) if den else float("inf")


def chi2_uniform_bytes(bits: np.ndarray) -> float:
    """Chi-square statistic of the byte distribution against uniform (lower=better)."""
    bs = np.frombuffer(bits_to_bytes(bits), dtype=np.uint8)
    if len(bs) == 0:
        return float("inf")
    counts = np.bincount(bs, minlength=256)
    exp = len(bs) / 256.0
    return float(np.sum((counts - exp) ** 2 / exp))


def compression_ratio(bits: np.ndarray) -> float:
    """zlib compressed size / original size (>=~1.0 means incompressible = random)."""
    data = bits_to_bytes(bits)
    if not data:
        return 0.0
    return len(zlib.compress(data, 9)) / len(data)


@dataclass
class EntropyReport:
    n_raw_bits: int
    n_whitened_bits: int
    raw_min_entropy: float
    whitened_min_entropy: float
    raw_monobit_bias: float
    whitened_monobit_bias: float
    whitened_runs_z: float
    whitened_chi2_bytes: float
    whitened_compression: float
    throughput_bits_per_s: float

    def as_dict(self) -> dict:
        return {k: (round(v, 5) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


def assess_entropy(deltas: np.ndarray, nbits: int = 1, elapsed_s: float | None = None) -> EntropyReport:
    raw = raw_lsb_bits(deltas, nbits=nbits)
    white = von_neumann(raw)
    tput = (len(white) / elapsed_s) if elapsed_s else 0.0
    return EntropyReport(
        n_raw_bits=len(raw),
        n_whitened_bits=len(white),
        raw_min_entropy=min_entropy_mcv(raw),
        whitened_min_entropy=min_entropy_mcv(white),
        raw_monobit_bias=monobit_bias(raw),
        whitened_monobit_bias=monobit_bias(white),
        whitened_runs_z=runs_z(white),
        whitened_chi2_bytes=chi2_uniform_bytes(white),
        whitened_compression=compression_ratio(white),
        throughput_bits_per_s=tput,
    )


# ---------------------------------------------------------------------------
# Load / contention sensing.
# ---------------------------------------------------------------------------

def _burn(stop_flag, cpu):
    if cpu is not None:
        try:
            os.sched_setaffinity(0, {cpu})
        except Exception:
            pass
    x = 0
    while not stop_flag.value:
        x ^= (x * 2654435761 + 1) & 0xFFFFFFFF
        x = (x + 1) & 0xFFFFFFFF


class LoadGenerator:
    """Context manager running ``n_workers`` background CPU burners for ground truth.

    When ``cpu`` is set, burners are pinned to that single core. Pinning the measurer
    to the same core turns background load into direct, countable contention: the CFS
    scheduler splits the core evenly among (n_workers + 1) threads, so a fixed
    workload's wall time scales ~linearly with the co-runner count.
    """
    def __init__(self, n_workers: int, cpu: int | None = None):
        self.n_workers = n_workers
        self.cpu = cpu
        self.procs: list[mp.Process] = []
        self._stop = mp.Value("b", False)

    def __enter__(self):
        self._stop.value = False
        for _ in range(self.n_workers):
            p = mp.Process(target=_burn, args=(self._stop, self.cpu), daemon=True)
            p.start()
            self.procs.append(p)
        time.sleep(0.2)  # let the scheduler settle
        return self

    def __exit__(self, *exc):
        self._stop.value = True
        for p in self.procs:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        self.procs.clear()


def timing_window_features(probes: int = 400, work_iters: int = 150) -> np.ndarray:
    """One window of load-sensing features from a burst of fixed-workload timings.

    Features are chosen to be robust and interpretable: central tendency, spread, tail,
    and a contention ratio (p90/median). Contention inflates the spread and tail more
    than the median, so the *shape* of the timing distribution encodes load.
    """
    d = jitter_deltas(probes, work_iters=work_iters, warmup=50).astype(np.float64)
    med = np.median(d)
    mean = np.mean(d)
    p90 = np.percentile(d, 90)
    p99 = np.percentile(d, 99)
    mn = d.min()
    return np.array([
        mean,
        np.std(d),
        med,
        p90,
        p99,
        mean / med if med else 0.0,         # KEY: time-slicing lifts the mean above the median
        p90 / med if med else 0.0,          # contention ratio
        p99 / med if med else 0.0,          # tail ratio
        np.mean(d > 1.5 * med),             # fraction of stalled probes
        med / mn if mn else 0.0,            # floor ratio (drift-invariant)
    ])


LOADSENSE_FEATURE_NAMES = [
    "loop_timing.0.mean", "loop_timing.0.std", "loop_timing.0.median",
    "loop_timing.0.p90", "loop_timing.0.p99", "loop_timing.0.mean_over_median",
    "loop_timing.0.p90_over_median", "loop_timing.0.p99_over_median",
    "loop_timing.0.stall_frac", "loop_timing.0.floor_ratio",
]

# CCS Results — Latent Capabilities Discovered on Real Hardware

**Host:** Intel Xeon @ 2.80GHz, 4 cores, Linux 6.18 (x86_64 container)
**Pipeline:** `python scripts/run_all.py` — reproducible end-to-end.
Exact live numbers are in [`manifest.json`](manifest.json) and the per-experiment JSON
files; representative figures from one run are quoted below (real-hardware numbers vary
run to run but the *conclusions* reproduce).

The thesis of CCS: computer architecture asks *what capabilities should new hardware
provide?* — CCS asks *what capabilities already exist in deployed hardware but stay
hidden because our software abstractions never search for them?* We ran that search on
the very machine the platform runs on.

---

## Two new uses of hardware, certified

### 1. The CPU clock is a hardware entropy source — `cpu_jitter_entropy_v1` (positive)

The *designed* use of `perf_counter_ns` is timekeeping. The latent capability: the
nanosecond jitter in the time to run a fixed workload is physically unpredictable
(microarchitectural state, scheduler, interrupts). Harvesting the low bit and whitening
it with a von Neumann extractor yields:

| metric | measured | pre-registered bar | pass |
|---|---|---|---|
| whitened min-entropy / bit | **0.935** | ≥ 0.90 | ✅ |
| monobit bias | 0.0009 | ≤ 0.01 | ✅ |
| runs-test z | 0.32 | \|z\| ≤ 3.0 | ✅ |
| χ² over bytes (df 255) | ~250 | ≤ 293.25 | ✅ |
| compression ratio | 1.0009 | ≥ 0.95 (incompressible) | ✅ |

400,000 raw timings → ~100,000 whitened bits that pass the full randomness battery.
This is a true-random source hiding inside a clock. (Linux already ships a production
version of this idea as `jitterentropy`; CCS *rediscovers* it from first principles by
searching, which is the point — the method finds it without being told it exists.)

### 2. Timing jitter counts your CPU co-tenants — `cpu_contention_sensor_v1` (positive)

The designed use of a busy loop is computation. The latent capability: the *shape* of a
fixed workload's timing distribution reveals **how many other compute tenants are
sharing your core** — with no `/proc`, no cgroup, no OS load API. Only a clock and a
loop.

- **Accuracy: ~0.94** at a 4-way contention count {0,1,2,3 co-runners} vs a 0.25
  majority baseline.
- **Generalizes across time:** certified under a cross-time-block split (train on early
  blocks, test on a held-out later block) — per-axis accuracy ~0.94, so it is not
  memorizing a momentary system state.
- **Reproduced** on an independent re-split.
- Cost: ~50 ms / ~250 mJ per inference (a 500-probe window).

Mechanism: when the measurer and the load share one core, the CFS scheduler splits the
core evenly among the `(k+1)` threads, so a fixed workload's mean time scales ~linearly
with the co-runner count `k` (measured: 0→31.7µs, 1→59.3µs, 2→93.3µs, 3→109.7µs). The
drift-invariant `mean/median` ratio is the load-carrying feature.

---

## A third probe, honestly falsified — `workload_type_classifier_v1` (negative)

We then asked a harder question than *how many* neighbors — *what kind* of work is a
co-located neighbor doing: **idle / cpu_bound / memory_bound**? This is defensive
observability for noisy-neighbor diagnosis (pure self-measurement; no `/proc`, no cgroup,
no cross-process channel). Two timing micro-probes, reacting to different physics:

- a **register-bound arithmetic probe** — a CPU-bound neighbor preempts the measurer for
  whole scheduler slices, which lands in the timing **tail** (median barely moves, but the
  mean and `mean/median` inflate — measured on this host: `mean/median` ≈ 1.07 idle →
  ≈ 1.6 under CPU load);
- an **~8 MB pointer-chase memory probe** — a memory-bandwidth neighbor lifts the whole
  memory-probe distribution, **median included** (≈ 466 µs idle → ≈ 525 µs under bandwidth
  pressure), because every cache miss costs more regardless of scheduling.

(Unlike the contention sensor, this host's CPU affinity is only *advisory* — pinning to one
core creates no contention, verified empirically — so the ground-truth loads oversubscribe
every core instead of pinning. That environmental fact is recorded in the entry.)

| metric | measured (this run) | across runs | bar |
|---|---|---|---|
| accuracy (3-way) | **0.863** | ~0.85–0.96 | vs 0.33 majority |
| cross-time-block per-axis | 0.863 | tracks overall | — |
| reproduced (independent re-split) | ✅ | usually ✅ | — |
| **best single probe (`mem_probe` alone)** | **0.873** | ~0.87–0.92 | — |

**The verdict is a real negative — `redundant-with-baseline`.** The classifier genuinely
works (≈ 0.86, well above the 0.33 majority, reproduces, and generalizes across time
blocks), but it does **not** beat the memory probe *alone* (0.873 ≥ 0.863). Falsification
shows the memory probe is a near-sufficient statistic for workload type on this host — its
median carries the bandwidth signal and its tail already picks up CPU preemption — so the
second (compute) probe's marginal value is within run-to-run noise. Over repeated runs the
strict CCS multi-signal test oscillates between `positive` and `redundant-with-baseline`;
we record it **conservatively as a negative** rather than tune toward the favorable draw.
The honest finding: *you do not need two probes here — one does the job.* The entry still
ships its measured accuracy, cross-time-block generalization, and dual-use audit so the
negative stays informative.

This is the falsification standard earning its keep a second time: an intuitively appealing
"two probes separate three classes" story, held to *beats every single-signal baseline*,
does not survive — and that is exactly the kind of over-claim a registry should catch.

---

## The discipline earned its keep — the improvement arc

The contention sensor did **not** work on the first try, and CCS is what caught it:

| version | cross-time-block accuracy | verdict |
|---|---|---|
| naive, absolute timing features, background load on other cores | **0.10** (worse than chance) | falsifier rejected — non-generalizing |
| + drift-invariant ratio features | ~0.35 | still `unstable` |
| + physical insight: pin measurer & load to the same core | **~0.94** | **certified positive** |

The unpinned configuration is kept in the registry as a **real negative**
(`cpu_contention_unpinned_v1`, `environment-bound`, accuracy ~0.27 ≈ chance). Same signal,
same features — the *physical understanding* of core co-location is what created the
capability. A registry that logs this saves every future searcher the dead end.

We also caught a **process-hygiene bug** mid-investigation: CPU affinity set by the
pinned run leaked into the unpinned run (a global side effect), briefly making the
"negative" look positive. Fixing it — setting affinity explicitly per run — is what
produced the honest ~0.27. This is the falsification standard doing its job on our own
code, not just the models.

---

## Registry state (all four quadrants populated)

| id | status | note |
|---|---|---|
| `cpu_jitter_entropy_v1` | positive | CPU clock as entropy source (real hw) |
| `cpu_contention_sensor_v1` | positive | co-tenant counter from timing (real hw) |
| `occupancy_sim_v1` | positive | simulated occupancy, validates the pipeline |
| `occupancy_v1` | positive | hand-written example |
| `cpu_contention_unpinned_v1` | **negative** | `environment-bound` — real-hw non-capability |
| `workload_type_classifier_v1` | **negative** | `redundant-with-baseline` — two-probe workload-type classifier; the memory probe alone suffices (real hw) |
| `battery_light` | **negative** | `redundant-with-baseline` example |
| `occupancy_room_echo_trap` | **unstable** | planted memorization trap, `environment-bound` |
| `sustained_contention_v1` | **experimental** | composite: `temporal-integration` of the contention sensor; `depends_on` it; not yet independently falsified ("no free confidence") |

A healthy registry has all four quadrants. If it held only positives, the falsifier
would not be working.

**Composition & decay:** `sustained_contention_v1` inherits its `valid_until` as the
`min` over its dependency (decay-cut-set = `[cpu_contention_sensor_v1]`), so when the
atom's certification lapses the composite is automatically demoted — capability
supply-chain semantics.

---

## Benchmark (measured on host)

- Screening throughput: **~37,000 windows/s** over the 4-signal occupancy lattice
  (2,880 windows) with monotone pruning.
- Full falsification (train + cross-OEM/room split + baselines + reproduction +
  per-axis diagnostics): **~3.6 s**.

---

## Dual-use, stated plainly

Both real capabilities are, by construction, side channels — the audit ships in each
registry entry:

- **Entropy source:** benign; consumes only its own timing. Recommended conditioning:
  von Neumann here, a cryptographic conditioner (e.g. SHA-256) in deployment.
- **Contention sensor:** a **noisy-neighbor / co-tenancy detector** — it reveals the
  presence and count of co-resident tenants on a shared host with no OS API and no
  permission. Both are marked permissionless in the audit. Mitigations recorded:
  coarsen the clock exposed to untrusted code, add scheduler noise, pin tenants to
  disjoint cores. These are demonstrated on our own machine; no attack tooling is
  included.
- **Workload-type classifier (negative):** even though it did not certify, its audit ships
  in the registry entry. It is a **noisy-neighbor diagnosis** channel — it infers the
  *type* of a co-resident workload (idle / cpu / memory) from self-timing, but reads no
  neighbor data and identifies no one (permissionless, `disclosure_sensitive: false`).
  Mitigations recorded: coarsen the exposed clock, partition shared LLC / memory bandwidth,
  schedule tenants on disjoint cores.

---

## How to reproduce

```bash
pip install numpy pandas scikit-learn jsonschema pyarrow pytest
python scripts/run_all.py        # runs all experiments, writes results/ and registry/registry.json
python -m pytest -q              # 30 tests
python benchmark/bench_pipeline.py
```

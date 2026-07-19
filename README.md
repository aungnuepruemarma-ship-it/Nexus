# Nexus — Computational Capability Search (CCS)

Computer architecture asks: *what capabilities should new hardware provide?*

CCS asks the inverse: **what capabilities already exist in deployed hardware but remain hidden, because our software abstractions never search for them?**

A modern phone is a dense physical measurement instrument. Its battery current traces the thermal environment; its WiFi RSSI traces bodies moving through a room; its barometer traces doors and HVAC cycles. Nexus is an open, reproducible platform for systematically searching, falsifying, and cataloging these latent capabilities — including the negative results.

Nexus is not just a design. It is a **working platform**, and we turned it on the machine
it runs on — searching the latent capability space of a real CPU and certifying two new
uses of it.

## Discovered on real hardware (see [`results/REPORT.md`](results/REPORT.md))

| Capability | What it does | Result |
|---|---|---|
| **CPU clock → entropy source** | Nanosecond timing jitter of a fixed workload, whitened, yields true-random bits | **positive** — min-entropy ~0.94 bits/bit, passes the full randomness battery |
| **Timing jitter → co-tenant counter** | The shape of a fixed workload's timing distribution counts how many compute tenants share your core — no `/proc`, no OS load API | **positive** — ~0.94 accuracy, generalizes across held-out time blocks |

The naive version of the co-tenant counter was **rejected** by the falsifier and is kept
as a real negative (`cpu_contention_unpinned_v1`) — the physical insight (same-core
contention) is what created the capability, and the registry logs the dead end.

## Run it

```bash
pip install numpy pandas scikit-learn jsonschema pyarrow pytest
python scripts/run_all.py          # all experiments -> results/ + registry/registry.json
python -m pytest -q                # 25 tests
python benchmark/bench_pipeline.py # measured throughput/latency
```

## Layout

| Path | Contents |
|---|---|
| [`docs/ccs-vision.md`](docs/ccs-vision.md) | The discipline: the latent capability space, the Prospecting Loop, certification by invariance, capability half-life, the composition algebra, the dual-use privacy audit. |
| [`docs/architecture.md`](docs/architecture.md) | The platform components and repository layout. |
| `ccs/` | The library: `signals`, `screening` (MI lattice gate), `harness` (falsification), `registry` (DAG + decay), `validator`, `composition` (algebra), `audit`, plus `ccs/hardware/` (real probes) and `ccs/sim/` (physics simulator). |
| `experiments/` | `exp001_occupancy_sim.py`, `exp_hw_entropy.py`, `exp_hw_loadsense.py`. |
| [`registry/capability.schema.json`](registry/capability.schema.json) | JSON Schema (draft 2020-12) for registry entries; `registry/registry.json` is generated. |
| `results/` | Generated metrics, the populated registry summary, and [`REPORT.md`](results/REPORT.md). |

## How CCS separates real capabilities from memorization

A capability is a **falsifiable claim** (task `T` inferable from signal subset `S` on
device population `D` at accuracy `A`, energy `E`, latency `L`, privacy `P`). It is
certified only if it **transfers across invariance axes** (cross-OEM/room/time), **beats
the best single-signal baseline**, **reproduces**, and **stays within a pre-registered
budget**. The pipeline is demonstrated to reject a planted memorization trap and a real
non-generalizing sensor while certifying the genuine ones.

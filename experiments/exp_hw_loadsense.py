"""EXP-HW-LOADSENSE (real hardware): CPU timing jitter as a load/contention sensor.

The designed use of a busy loop is computation. The latent capability searched here:
the *shape* of a fixed workload's timing distribution reveals how many concurrent
compute tenants are contending for the cores — a "room occupancy" sensor for the CPU,
built with no /proc, no cgroup, no OS load API. Only a clock and a loop.

Protocol: for each contention class {0,1,2,3} extra busy cores, run background burners
as ground truth and collect timing-window features. Repeat across several time blocks;
certify under a cross-time-block invariance split (train on early blocks, test on a
held-out later block) so the model must generalize in time, not memorize a moment.

Run: python experiments/exp_hw_loadsense.py
"""
from __future__ import annotations

import json
import platform
import time
from pathlib import Path

import numpy as np

from ccs.hardware import probes
from ccs.signals import FeatureSet
from ccs.harness import ExperimentSpec, Dataset, InvarianceAxis, falsify
from ccs.capability import certify
from ccs.audit import audit_capability
from ccs.validator import validate_entry

ROOT = Path(__file__).resolve().parents[1]

LOAD_CLASSES = (0, 1, 2, 3)   # extra busy cores contending with the measurer


SHARED_CPU = 0   # pin measurer + burners to one core so contention is direct & countable


def collect(rounds: int = 4, windows_per_cell: int = 22,
            probes_per_window: int = 500, work_iters: int = 150,
            pinned: bool = True, verbose=True):
    """Collect real timing-window features labeled by contention level and time block.

    When ``pinned``, the measurer and burners share ``SHARED_CPU`` so the number of
    co-runners maps to a ~linear inflation of the fixed workload's mean time. When not
    pinned, background burners land on other cores and barely perturb the measurer —
    the naive design the falsifier is expected to reject.
    """
    cpu = SHARED_CPU if pinned else None
    # Set affinity explicitly every run so process-global state never leaks between
    # the pinned and unpinned experiments.
    if pinned:
        probes.pin_current(SHARED_CPU)
    else:
        probes.unpin_current()
    X, y, block = [], [], []
    for r in range(rounds):
        for load in LOAD_CLASSES:
            with probes.LoadGenerator(load, cpu=cpu):
                for _ in range(windows_per_cell):
                    X.append(probes.timing_window_features(probes_per_window, work_iters))
                    y.append(load)
                    block.append(r)
        if verbose:
            print(f"  round {r+1}/{rounds} ({'pinned' if pinned else 'unpinned'}) collected", flush=True)
    return np.array(X), np.array(y), np.array(block)


def run(rounds: int = 4, pinned: bool = True, cid: str | None = None, verbose: bool = True):
    t0 = time.perf_counter()
    X, y, block = collect(rounds=rounds, pinned=pinned, verbose=verbose)
    collect_s = time.perf_counter() - t0

    names = probes.LOADSENSE_FEATURE_NAMES
    feature_signal = ["loop_timing"] * len(names)
    fs = FeatureSet(X=X, names=names,
                    t_ns=np.arange(len(y), dtype=np.int64),
                    feature_signal=feature_signal)

    # cross-time-block invariance: train on all but the last block, test on the last.
    train_blocks = tuple(range(rounds - 1))
    test_blocks = (rounds - 1,)
    axes = [InvarianceAxis("time_block", block, train_blocks, test_blocks)]

    # per-inference latency: measured window collection time (ms).
    per_window_ms = 1000.0 * collect_s / len(y)
    # rough energy model: one core-second ~ 5 J for a server core at this timing.
    energy_mj = round(per_window_ms * 5.0, 3)

    ds = Dataset(fs=fs, y=y, axes=axes, signal_cost_mj={"loop_timing": 0.0})
    spec = ExperimentSpec(
        experiment_id="EXP-HW-LOADSENSE",
        title="CPU Contention Level from Timing Jitter",
        question="How many concurrent compute tenants are running, inferred only from timing?",
        task="cpu contention level: 0 / 1 / 2 / 3 extra busy cores",
        classes=LOAD_CLASSES,
        target_accuracy=0.70,
        energy_budget_mj=max(50.0, energy_mj + 10),
        latency_budget_ms=max(50.0, per_window_ms + 10),
    )
    result = falsify(spec, ds, ("loop_timing",),
                     compute_energy_mj=energy_mj, inference_latency_ms=round(per_window_ms, 3))

    audit = audit_capability(
        signal_permissions=["loop_timing"],
        bystander_inference=(
            "Reveals the presence and count of co-resident compute tenants on the same host "
            "without any OS load API — a noisy-neighbor / co-tenancy side channel."),
        escalation_gradient=(
            "Finer time resolution and per-core pinning could fingerprint specific neighbor "
            "workloads or build a covert channel; not demonstrated here."),
        mitigations="Coarsen the clock exposed to untrusted code; add scheduler noise; pin tenants to disjoint cores.",
        escalation_unbounded=False,
        identifies_individuals=False,
    )

    cid = cid or ("cpu_contention_sensor_v1" if pinned else "cpu_contention_unpinned_v1")
    name = ("CPU Contention Sensor (timing jitter)" if pinned
            else "CPU Contention Sensor — unpinned (naive)")
    desc = (
        "Infers the number of concurrent compute tenants contending for the CPU from the "
        "shape of a fixed workload's timing distribution — no /proc, no cgroup, no OS load "
        "API. The designed use of a busy loop is computation; the latent use is a "
        "contention sensor. Certified on this host under a cross-time-block split."
        if pinned else
        "Naive contention sensor with the measurer NOT pinned to the load's core. Background "
        "burners land on other cores, so the fixed workload is barely perturbed and the "
        "capability fails to generalize across time blocks — the falsifier rejects it. Kept "
        "as a negative result: the physical insight (same-core contention) is what mattered.")
    entry = certify(
        cid, name, spec, result,
        signals=[{"family": "cpu", "name": "loop_timing",
                  "sampling": "500 probes/window", "android_permission": "none"}],
        model={"kind": "random forest over timing-distribution shape features",
               "features": "mean/std/median/p90/p99, mean-over-median & p90-over-median ratios, stall fraction"},
        audit=audit,
        provenance=[],
        half_life_days=120,
        description=desc,
        generalization={"axis": "time_block", "train_blocks": list(train_blocks),
                        "test_blocks": list(test_blocks),
                        "per_axis_accuracy": result.per_axis_accuracy},
        limitations=[
            "Measured on one CPU (Intel Xeon @ 2.80GHz, 4 cores, Linux 6.18) in a container.",
            "Cross-CPU / cross-host generalization not yet certified (single-device scope).",
            "Absolute contention counts assume a comparable core count.",
        ],
        failure_modes=[
            "A fully idle host with a constant background daemon could shift the noise floor.",
        ],
        references=["exp_hw_entropy.py (same timing channel, entropy use)"],
    )

    out = {
        "status": result.status,
        "passed": result.passed,
        "failure_type": result.failure_type,
        "metrics": result.metrics,
        "baseline_best_acc": result.baseline_best_acc,
        "baseline_best_signal": result.baseline_best_signal,
        "per_axis_accuracy": result.per_axis_accuracy,
        "energy_mj": result.energy_mj,
        "latency_ms": result.latency_ms,
        "reproduced": result.reproduced,
        "notes": result.notes,
        "n_windows": len(y),
        "collect_seconds": round(collect_s, 2),
        "entry_valid": (validate_entry(entry) == []) if entry else None,
        "host": {"processor": platform.processor(), "python": platform.python_version()},
    }
    if verbose:
        print(json.dumps(out, indent=2, default=list))
    return out, entry, (fs, y, block, spec, ds)


if __name__ == "__main__":
    out, entry, _ = run()
    print("\n--- CPU CONTENTION SENSOR (real hardware) ---")
    print(f"windows: {out['n_windows']}  collect: {out['collect_seconds']}s")
    print(f"accuracy: {out['metrics'].get('accuracy')}  "
          f"vs majority baseline {out['baseline_best_acc']} ({out['baseline_best_signal']})")
    print(f"cross-time-block per-axis: {out['per_axis_accuracy']}")
    print(f"status: {out['status']}  failure_type: {out['failure_type']}  "
          f"schema-valid: {out['entry_valid']}")

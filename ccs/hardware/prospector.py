"""Prospector: run the CCS Prospecting Loop on the host CPU.

A thin programmatic entry point that ties the real probes to the pipeline, so the
whole loop (Sense -> Screen -> Hypothesize -> Falsify -> Certify) can be invoked in one
call. The concrete, fuller experiments live in experiments/exp_hw_*.py; this module is
the reusable API the architecture (docs/architecture.md section 1) refers to.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import probes
from ..signals import FeatureSet
from ..harness import ExperimentSpec, Dataset, InvarianceAxis, falsify


@dataclass
class ProspectResult:
    task: str
    status: str
    accuracy: float | None
    failure_type: str | None
    detail: dict


def prospect_entropy(n_samples: int = 200_000) -> ProspectResult:
    """Sense timing jitter and assess it as an entropy source."""
    import time
    t0 = time.perf_counter()
    deltas = probes.jitter_deltas(n_samples, work_iters=200, warmup=500)
    rep = probes.assess_entropy(deltas, nbits=1, elapsed_s=time.perf_counter() - t0)
    passed = (rep.whitened_min_entropy >= 0.90 and rep.whitened_monobit_bias <= 0.01
              and abs(rep.whitened_runs_z) <= 3.0 and rep.whitened_compression >= 0.95)
    return ProspectResult(
        task="entropy source",
        status="positive" if passed else "unstable",
        accuracy=round(rep.whitened_min_entropy, 4),
        failure_type=None if passed else "oem-bound",
        detail=rep.as_dict(),
    )


def prospect_contention(rounds: int = 3, windows_per_cell: int = 20,
                        classes=(0, 1, 2, 3), shared_cpu: int = 0) -> ProspectResult:
    """Sense loop timing under controlled contention and falsify a co-tenant counter."""
    probes.pin_current(shared_cpu)
    X, y, block = [], [], []
    for r in range(rounds):
        for load in classes:
            with probes.LoadGenerator(load, cpu=shared_cpu):
                for _ in range(windows_per_cell):
                    X.append(probes.timing_window_features(400, 150))
                    y.append(load)
                    block.append(r)
    X, y, block = np.array(X), np.array(y), np.array(block)
    fs = FeatureSet(X=X, names=probes.LOADSENSE_FEATURE_NAMES,
                    t_ns=np.arange(len(y), dtype=np.int64),
                    feature_signal=["loop_timing"] * len(probes.LOADSENSE_FEATURE_NAMES))
    ds = Dataset(fs=fs, y=y, signal_cost_mj={"loop_timing": 0.0},
                 axes=[InvarianceAxis("time_block", block,
                                      tuple(range(rounds - 1)), (rounds - 1,))])
    spec = ExperimentSpec("EXP-HW-LOADSENSE", "contention", "how many co-tenants?",
                          "cpu contention level", classes, 0.70, 1e9, 1e9)
    r = falsify(spec, ds, ("loop_timing",), compute_energy_mj=0.0)
    return ProspectResult(
        task="cpu contention level",
        status=r.status,
        accuracy=r.metrics.get("accuracy"),
        failure_type=r.failure_type,
        detail={"per_axis": r.per_axis_accuracy, "baseline": r.baseline_best_acc,
                "reproduced": r.reproduced, "notes": r.notes},
    )


def prospect_all() -> list[ProspectResult]:
    return [prospect_entropy(), prospect_contention()]

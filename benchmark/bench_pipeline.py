"""Benchmark the CCS pipeline: screening throughput, falsification latency, and a
capability comparison table. Numbers are measured on the host, not estimated.

Run: python benchmark/bench_pipeline.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from ccs.sim import occupancy
from ccs import screening
from ccs.harness import ExperimentSpec, Dataset, InvarianceAxis, falsify

ROOT = Path(__file__).resolve().parents[1]


def bench_screening(reps=5):
    fs, y, oem, room, cost = occupancy.generate()
    t = []
    for _ in range(reps):
        t0 = time.perf_counter()
        screening.screen_lattice(fs, y, cost, max_order=3, threshold_bits=0.1)
        t.append(time.perf_counter() - t0)
    return {"n_windows": int(fs.X.shape[0]), "n_signals": len(set(fs.feature_signal)),
            "median_s": round(float(np.median(t)), 4),
            "windows_per_s": int(fs.X.shape[0] / np.median(t))}


def bench_falsify(reps=3):
    fs, y, oem, room, cost = occupancy.generate()
    ds = Dataset(fs=fs, y=y, axes=[
        InvarianceAxis("oem", oem, ("Pixel", "Samsung"), ("Xiaomi",)),
        InvarianceAxis("room", room, ("office", "bedroom"), ("conference",))],
        signal_cost_mj=cost)
    spec = ExperimentSpec("EXP-001", "t", "q", "occ", occupancy.CLASSES, 0.75, 20.0, 50.0)
    t = []
    for _ in range(reps):
        t0 = time.perf_counter()
        r = falsify(spec, ds, ("wifi_rssi", "thermal", "imu"))
        t.append(time.perf_counter() - t0)
    return {"median_s": round(float(np.median(t)), 3), "status": r.status,
            "accuracy": r.metrics["accuracy"]}


def capability_table():
    """Load any generated registry entries and tabulate the key metrics."""
    reg_path = ROOT / "registry" / "registry.json"
    rows = []
    if reg_path.exists():
        entries = json.loads(reg_path.read_text())
        for e in entries.values():
            rows.append({
                "id": e["id"], "status": e.get("status"),
                "accuracy": e.get("accuracy"),
                "energy_mj": e.get("energy_mj"),
                "latency_ms": e.get("latency_ms"),
                "privacy": (e.get("privacy_audit") or {}).get("score"),
                "valid_until": e.get("valid_until"),
            })
    return rows


def main():
    out = {
        "screening": bench_screening(),
        "falsification": bench_falsify(),
        "capabilities": capability_table(),
    }
    print(json.dumps(out, indent=2))
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "benchmark.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()

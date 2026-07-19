"""EXP-001 (simulated): room occupancy via low-intrusion signals.

Drives the whole Prospecting Loop on simulator data to prove the machinery works:
  1. Screen the signal lattice with mutual information.
  2. Falsify the top candidate under cross-OEM + cross-room invariance.
  3. Separately falsify the planted ``room_echo`` trap — it must be rejected as
     environment-bound, demonstrating the certification standard bites.
  4. Certify the survivor into a registry entry and validate it against the schema.

Run: python experiments/exp001_occupancy_sim.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ccs.sim import occupancy
from ccs import screening
from ccs.signals import FeatureSet
from ccs.harness import (ExperimentSpec, Dataset, InvarianceAxis, falsify)
from ccs.capability import certify
from ccs.audit import audit_capability
from ccs.registry import Registry
from ccs.validator import validate_entry

ROOT = Path(__file__).resolve().parents[1]


def build_dataset():
    fs, y, oem, room, cost = occupancy.generate()
    axes = [
        InvarianceAxis("oem", oem, train_values=("Pixel", "Samsung"), test_values=("Xiaomi",)),
        InvarianceAxis("room", room, train_values=("office", "bedroom"), test_values=("conference",)),
    ]
    return Dataset(fs=fs, y=y, axes=axes, signal_cost_mj=cost), fs, y, oem, room, cost


def run(verbose=True):
    ds, fs, y, oem, room, cost = build_dataset()
    spec = ExperimentSpec(
        experiment_id="EXP-001",
        title="Room Occupancy (simulated)",
        question="Can occupancy be inferred from low-intrusion signals across devices and rooms?",
        task="room occupancy: 0 / 1 / 2 / 3+",
        classes=occupancy.CLASSES,
        target_accuracy=0.75,
        energy_budget_mj=20.0,
        latency_budget_ms=50.0,
    )

    # ---- Stage 2: screen the lattice --------------------------------------
    screen = screening.screen_lattice(
        fs, y, signal_costs=cost, max_order=3, threshold_bits=0.15)
    report = {"screening": {
        "label_entropy_bits": screen.label_entropy_bits,
        "n_survivors": len(screen.candidates),
        "n_screened_out": len(screen.screened_out),
        "n_pruned": len(screen.pruned),
        "top": [{"signals": c.signals, "mi_bits": c.mi_bits,
                 "mi_per_mj": c.mi_per_mj, "info_frac": round(c.info_fraction, 3)}
                for c in screen.candidates[:6]],
    }}

    # ---- Stage 4: falsify the real multi-signal candidate -----------------
    real_signals = ("wifi_rssi", "thermal", "imu")
    real = falsify(spec, ds, real_signals)
    report["real_candidate"] = {"signals": real_signals, **real.as_dict()}

    # ---- Falsify the planted trap: must be rejected -----------------------
    trap = falsify(spec, ds, ("room_echo",))
    report["trap_candidate"] = {"signals": ("room_echo",), **trap.as_dict()}

    # ---- Certify the survivor into a registry entry -----------------------
    entry = None
    if real.status in ("positive", "unstable"):
        audit = audit_capability(
            signal_permissions=["ACCESS_FINE_LOCATION", "none", "none"],
            bystander_inference="Reveals presence and coarse count of non-consenting occupants; no identity.",
            escalation_gradient="Higher IMU rate + per-AP RSSI could localize occupants; not demonstrated.",
            mitigations="Cap IMU at 100 Hz; quantize RSSI to 2 dBm.",
            escalation_unbounded=False, identifies_individuals=False)
        entry = certify(
            "occupancy_sim_v1", "Room Occupancy (simulated)", spec, real,
            signals=[
                {"family": "network", "name": "wifi_rssi", "sampling": "every 5 s",
                 "android_permission": "ACCESS_FINE_LOCATION"},
                {"family": "thermal", "name": "thermal", "sampling": "1 Hz",
                 "android_permission": "none"},
                {"family": "imu", "name": "imu", "sampling": "100 Hz",
                 "android_permission": "none"},
            ],
            model={"kind": "random forest over windowed features",
                   "features": "rssi var/mean, thermal mean, imu band energy"},
            audit=audit,
            provenance=["sha256:5111111111111111"],
            half_life_days=180,
            description="Estimates occupancy class (0/1/2/3+) from WiFi RSSI, thermal, and IMU. Simulated validation of the CCS pipeline.",
            generalization={
                "train_oems": ["Pixel", "Samsung"], "test_oems": ["Xiaomi"],
                "train_rooms": ["office", "bedroom"], "test_rooms": ["conference"],
                "per_oem_accuracy": {},
            },
        )
        errs = validate_entry(entry)
        report["certified_entry_valid"] = (errs == [])
        report["certified_entry_errors"] = errs

    if verbose:
        print(json.dumps(report, indent=2, default=list))
    return report, entry, trap


if __name__ == "__main__":
    report, entry, trap = run()
    print("\n--- SUMMARY ---")
    rc = report["real_candidate"]
    print(f"real signals: status={rc['status']} acc={rc['metrics'].get('accuracy')} "
          f"beats baseline({rc['baseline_best_signal']}={rc['baseline_best_acc']}) "
          f"per_axis={rc['per_axis_accuracy']}")
    tc = report["trap_candidate"]
    print(f"trap room_echo: status={tc['status']} failure_type={tc['failure_type']} "
          f"per_axis={tc['per_axis_accuracy']}")
    assert tc["status"] != "positive", "TRAP WAS NOT REJECTED — falsification is broken"
    print("OK: trap rejected, falsification standard is working.")

"""Run the whole CCS platform end-to-end and emit results + a populated registry.

Steps:
  1. EXP-001 (simulated occupancy): certify a real capability, reject a planted trap.
  2. EXP-HW-ENTROPY (real): CPU timing jitter as an entropy source.
  3. EXP-HW-LOADSENSE (real, pinned): CPU timing jitter as a contention/co-tenant sensor.
  4. EXP-HW-LOADSENSE (real, unpinned): the naive version, kept as a real negative.
  5. EXP-HW-WORKLOAD-ID (real): two-probe co-located workload-TYPE classifier.
  6. Compose the contention sensor over time (algebra + DAG demonstration).
  7. Assemble registry/registry.json (+ carry over the two hand-written examples),
     run decay propagation, validate the whole registry, and write results/.

Run: python scripts/run_all.py
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

from ccs.registry import Registry
from ccs.validator import validate_registry
from ccs.composition import CapabilitySpec, temporal_integrate

from experiments.exp001_occupancy_sim import run as run_occ
from experiments.exp_hw_entropy import run as run_entropy
from experiments.exp_hw_loadsense import run as run_load
from experiments.exp_hw_workload_id import run as run_workload

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REG_DIR = ROOT / "registry"


def _compose_sustained_contention(contention_entry: dict) -> dict:
    """Temporal-integration composite: aggregate the contention sensor over 3 windows.

    The algebra supplies the confidence *upper bound* and the cost/expiry accounting;
    the composite is marked ``experimental`` because it has not itself been falsified
    (the 'no free confidence' rule — a composite is certified like an atom)."""
    atom = CapabilitySpec.from_entry(contention_entry)
    bound = temporal_integrate(atom, n=3, mixing=0.6)
    return {
        "id": "sustained_contention_v1",
        "name": "Sustained CPU Contention (temporal integration)",
        "status": "experimental",
        "version": "1.0.0",
        "description": (
            "Aggregates the CPU contention sensor over 3 consecutive windows to report "
            "sustained co-tenancy. Built by the capability algebra "
            f"(temporal-integration, confidence upper bound {bound.confidence_upper}); "
            "not yet independently falsified, hence experimental."),
        "task": "sustained cpu contention over a 3-window horizon",
        "signals": [{"family": "cpu", "name": "loop_timing", "android_permission": "none"}],
        "depends_on": [contention_entry["id"]],
        "composition_operator": bound.operator,
        "energy_mj": bound.energy_mj,
        "latency_ms": bound.latency_ms,
        "date_created": "2026-07-19",
        "last_verified": "2026-07-19",
        "limitations": ["Algebra bound only; awaiting its own falsification run."],
        "references": ["ccs/composition.py temporal_integrate"],
    }


def main(quick: bool = False):
    RESULTS.mkdir(exist_ok=True)
    reg = Registry(entries={})

    # -- carry over the two hand-written examples --------------------------
    for ex in ("occupancy_v1", "battery_light"):
        p = REG_DIR / "examples" / f"{ex}.json"
        if p.exists():
            e = json.loads(p.read_text())
            reg.add(e)

    manifest = {"host": {"processor": platform.processor(),
                         "machine": platform.machine(),
                         "python": platform.python_version()},
                "experiments": {}}

    # -- 1. simulated occupancy -------------------------------------------
    print("[1/6] EXP-001 simulated occupancy ...", flush=True)
    occ_report, occ_entry, trap = run_occ(verbose=False)
    if occ_entry:
        reg.add(occ_entry)
    # store the trap as a scoped/negative registry entry too
    trap_entry = {
        "id": "occupancy_room_echo_trap", "name": "Occupancy from room_echo (planted trap)",
        "status": trap.status if trap.status != "positive" else "unstable",
        "version": "1.0.0",
        "description": "Planted memorization trap: room_echo encodes room identity. Rejected by "
                       "the falsifier — perfect within known rooms, collapses on a new room.",
        "task": "room occupancy: 0 / 1 / 2 / 3+",
        "signals": [{"family": "capability", "name": "room_echo", "android_permission": "none"}],
        "failure_type": trap.failure_type or "environment-bound",
        "date_created": "2026-07-19", "last_verified": "2026-07-19",
        "limitations": ["Room-bound; do not deploy outside its certified room set."],
    }
    if trap_entry["status"] == "negative" or trap.failure_type:
        reg.add(trap_entry)
    manifest["experiments"]["EXP-001"] = {
        "real_candidate": occ_report["real_candidate"],
        "trap_candidate": occ_report["trap_candidate"]}
    (RESULTS / "exp001_occupancy.json").write_text(json.dumps(occ_report, indent=2, default=list))

    # -- 2. real hardware: entropy source ---------------------------------
    print("[2/6] EXP-HW-ENTROPY real CPU entropy ...", flush=True)
    ent_result, ent_entry = run_entropy(n_samples=200_000 if quick else 400_000, verbose=False)
    reg.add(ent_entry)
    manifest["experiments"]["EXP-HW-ENTROPY"] = ent_result
    (RESULTS / "exp_hw_entropy.json").write_text(json.dumps(ent_result, indent=2, default=list))

    # -- 3. real hardware: contention sensor (pinned) ---------------------
    print("[3/6] EXP-HW-LOADSENSE pinned (real contention sensor) ...", flush=True)
    load_out, load_entry, _ = run_load(rounds=3 if quick else 4, pinned=True, verbose=False)
    if load_entry:
        reg.add(load_entry)
    manifest["experiments"]["EXP-HW-LOADSENSE"] = load_out
    (RESULTS / "exp_hw_loadsense.json").write_text(json.dumps(load_out, indent=2, default=list))

    # -- 4. real hardware: contention sensor (unpinned) = real negative ---
    print("[4/6] EXP-HW-LOADSENSE unpinned (real negative) ...", flush=True)
    neg_out, neg_entry, _ = run_load(rounds=3 if quick else 4, pinned=False, verbose=False)
    if neg_entry:
        reg.add(neg_entry)
    manifest["experiments"]["EXP-HW-LOADSENSE-UNPINNED"] = neg_out
    (RESULTS / "exp_hw_loadsense_unpinned.json").write_text(json.dumps(neg_out, indent=2, default=list))

    # -- 5. real hardware: co-located workload-type classifier ------------
    print("[5/6] EXP-HW-WORKLOAD-ID (co-located workload type) ...", flush=True)
    wid_out, wid_entry, _ = run_workload(rounds=3 if quick else 5, verbose=False)
    if wid_entry:
        reg.add(wid_entry)
    manifest["experiments"]["EXP-HW-WORKLOAD-ID"] = wid_out
    (RESULTS / "exp_hw_workload_id.json").write_text(json.dumps(wid_out, indent=2, default=list))

    # -- 6. composition: sustained contention -----------------------------
    print("[6/6] composing sustained contention ...", flush=True)
    if load_entry and load_entry.get("status") in ("positive", "unstable"):
        comp = _compose_sustained_contention(load_entry)
        reg.add(comp)

    # -- decay propagation + validation -----------------------------------
    decay_log = reg.propagate_expiry()
    reg.save(REG_DIR / "registry.json")
    validation = validate_registry(reg)
    manifest["registry_summary"] = reg.summary()
    manifest["registry_valid"] = validation["ok"]
    manifest["registry_errors"] = validation
    manifest["decay_cut_sets"] = {
        cid: reg.decay_cut_set(cid) for cid in reg.entries
        if reg.entries[cid].get("depends_on")}
    (RESULTS / "manifest.json").write_text(json.dumps(manifest, indent=2, default=list))

    print("\n=== REGISTRY SUMMARY ===")
    print(json.dumps(reg.summary(), indent=2))
    print("registry valid:", validation["ok"])
    if not validation["ok"]:
        print(json.dumps(validation, indent=2))
    return manifest, reg, validation


if __name__ == "__main__":
    import sys
    main(quick="--quick" in sys.argv)

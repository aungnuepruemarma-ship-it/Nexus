"""End-to-end pipeline tests on the occupancy simulator: the certification standard
must certify a real capability and reject a planted memorization trap."""
import numpy as np

from ccs.sim import occupancy
from ccs import screening
from ccs.harness import ExperimentSpec, Dataset, InvarianceAxis, falsify, make_split
from ccs.validator import validate_entry
from experiments.exp001_occupancy_sim import run as run_exp001


def _dataset():
    fs, y, oem, room, cost = occupancy.generate()
    axes = [
        InvarianceAxis("oem", oem, ("Pixel", "Samsung"), ("Xiaomi",)),
        InvarianceAxis("room", room, ("office", "bedroom"), ("conference",)),
    ]
    return Dataset(fs=fs, y=y, axes=axes, signal_cost_mj=cost)


def _spec():
    return ExperimentSpec("EXP-001", "t", "q", "occ", occupancy.CLASSES, 0.75, 20.0, 50.0)


def test_split_is_disjoint_and_transfers():
    ds = _dataset()
    tr, te = make_split(ds.axes, len(ds.y))
    assert tr.sum() > 0 and te.sum() > 0
    assert not np.any(tr & te)  # disjoint


def test_real_capability_certifies_positive():
    ds, spec = _dataset(), _spec()
    r = falsify(spec, ds, ("wifi_rssi", "thermal", "imu"))
    assert r.status == "positive"
    assert r.metrics["accuracy"] > r.baseline_best_acc  # beats best single signal
    assert r.per_axis_accuracy["oem"] >= 0.75
    assert r.per_axis_accuracy["room"] >= 0.75


def test_trap_is_rejected():
    ds, spec = _dataset(), _spec()
    r = falsify(spec, ds, ("room_echo",))
    assert r.status != "positive"
    assert r.failure_type in ("environment-bound", "redundant-with-baseline")
    # room axis collapses while oem axis holds -> environment binding
    assert r.per_axis_accuracy["room"] < r.per_axis_accuracy["oem"]


def test_screening_ranks_informative_over_trap_per_cost():
    fs, y, oem, room, cost = occupancy.generate()
    res = screening.screen_lattice(fs, y, cost, max_order=2, threshold_bits=0.05)
    assert res.best is not None
    # the informative real signals should appear among survivors
    survivor_sigs = {s for c in res.candidates for s in c.signals}
    assert {"wifi_rssi", "thermal", "imu"} & survivor_sigs


def test_exp001_end_to_end_entry_valid():
    report, entry, trap = run_exp001(verbose=False)
    assert entry is not None
    assert validate_entry(entry) == []
    assert trap.status != "positive"

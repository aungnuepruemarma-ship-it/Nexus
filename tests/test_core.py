"""Unit tests for the CCS core library."""
import datetime as dt

import numpy as np
import pytest

from ccs import signals, metrics, screening, composition, audit
from ccs.registry import Registry
from ccs.validator import validate_entry, validate_registry


# --------------------------- signals ---------------------------------------

def test_feature_extraction_shapes():
    t = np.arange(0, 1_000_000_000, 10_000_000)  # 100 samples @10ms
    s = signals.Signal("accel", "imu", t, np.sin(t / 1e8), "100 Hz")
    fs = signals.extract_features([s], window_ns=100_000_000)
    assert fs.X.shape[0] == len(fs.t_ns)
    assert fs.X.shape[1] == len(signals.DEFAULT_FEATURES)  # 1 axis * n features
    assert set(fs.feature_signal) == {"accel"}


def test_feature_subset_mask():
    t = np.arange(0, 5_000_000_000, 10_000_000)
    a = signals.Signal("a", "imu", t, np.zeros(len(t)))
    b = signals.Signal("b", "thermal", t, np.ones(len(t)))
    fs = signals.extract_features([a, b], window_ns=500_000_000)
    sub = fs.subset(["a"])
    assert set(sub.feature_signal) == {"a"}
    assert sub.X.shape[1] == len(signals.DEFAULT_FEATURES)


def test_bad_family_rejected():
    with pytest.raises(ValueError):
        signals.Signal("x", "not_a_family", [0, 1], [0.0, 1.0])


# --------------------------- metrics ---------------------------------------

def test_metrics_perfect():
    y = [0, 1, 2, 0, 1, 2]
    m = metrics.evaluate(y, y, labels=[0, 1, 2])
    assert m.accuracy == 1.0 and m.f1 == 1.0


def test_metrics_known_values():
    y_true = [0, 0, 1, 1]
    y_pred = [0, 1, 1, 1]
    m = metrics.evaluate(y_true, y_pred, labels=[0, 1])
    assert m.accuracy == 0.75
    # class1 precision = 2/3, recall = 1.0 ; class0 precision=1, recall=0.5
    assert 0.8 < m.precision < 0.84


def test_roc_auc_separable():
    y = [0, 0, 1, 1]
    proba = np.array([[0.9, 0.1], [0.8, 0.2], [0.2, 0.8], [0.1, 0.9]])
    assert metrics.roc_auc(y, proba, [0, 1]) == 1.0


# --------------------------- screening -------------------------------------

def test_mi_independent_is_low():
    rng = np.random.default_rng(0)
    x = rng.normal(size=2000)
    y = (rng.random(2000) > 0.5).astype(int)
    assert screening.mi_feature_label(x, y) < 0.05


def test_mi_dependent_is_high():
    rng = np.random.default_rng(0)
    y = (rng.random(2000) > 0.5).astype(int)
    x = y + rng.normal(0, 0.1, size=2000)  # x strongly encodes y
    assert screening.mi_feature_label(x, y) > 0.5


def test_monotone_pruning_runs():
    from ccs.signals import FeatureSet
    rng = np.random.default_rng(1)
    n = 400
    y = rng.integers(0, 2, n)
    good = y + rng.normal(0, 0.2, n)
    noise = rng.normal(size=n)
    X = np.column_stack([good, noise])
    fs = FeatureSet(X=X, names=["g.0.mean", "n.0.mean"], t_ns=np.arange(n),
                    feature_signal=["g", "n"])
    res = screening.screen_lattice(fs, y, {"g": 1.0, "n": 1.0}, max_order=2,
                                   threshold_bits=0.1)
    # the informative signal survives, pure noise is screened out
    survivors = {c.signals for c in res.candidates}
    assert ("g",) in survivors
    assert ("n",) in res.screened_out


# --------------------------- registry / decay ------------------------------

def test_cycle_detection():
    reg = Registry(entries={
        "a": {"id": "a", "depends_on": ["b"]},
        "b": {"id": "b", "depends_on": ["a"]},
    })
    assert reg.has_cycle()


def test_decay_expires_and_propagates():
    today = dt.date(2026, 7, 19)
    reg = Registry(entries={
        "atom": {"id": "atom", "status": "positive", "valid_until": "2026-01-01"},
        "comp": {"id": "comp", "status": "positive", "depends_on": ["atom"],
                 "valid_until": "2030-01-01"},
    })
    log = reg.propagate_expiry(today=today)
    assert reg.get("atom")["status"] == "unstable"        # expired
    # composite inherits min expiry from its (now-expired) atom
    assert reg.get("comp")["valid_until"] == "2026-01-01"
    assert any(e["id"] == "atom" and e["event"] == "expired" for e in log)


def test_dependency_failure_demotes_composite():
    reg = Registry(entries={
        "atom": {"id": "atom", "status": "negative", "failure_type": "non-reproducible"},
        "comp": {"id": "comp", "status": "positive", "depends_on": ["atom"]},
    })
    reg.propagate_expiry(today=dt.date(2026, 7, 19))
    assert reg.get("comp")["status"] == "unstable"


def test_decay_cut_set():
    reg = Registry(entries={
        "a": {"id": "a"},
        "b": {"id": "b", "depends_on": ["a"]},
        "c": {"id": "c", "depends_on": ["b"]},
    })
    assert reg.decay_cut_set("c") == ["a", "b"]


# --------------------------- validator -------------------------------------

def test_valid_negative_entry():
    e = {"id": "neg1", "name": "n", "status": "negative", "version": "1.0.0",
         "description": "d", "task": "t",
         "signals": [{"family": "imu", "name": "accel"}],
         "date_created": "2026-07-19", "failure_type": "screened-out"}
    assert validate_entry(e) == []


def test_negative_without_failure_type_invalid():
    e = {"id": "neg1", "name": "n", "status": "negative", "version": "1.0.0",
         "description": "d", "task": "t",
         "signals": [{"family": "imu", "name": "accel"}],
         "date_created": "2026-07-19"}
    assert validate_entry(e) != []


def test_registry_semantic_expiry_violation():
    reg = Registry(entries={
        "atom": {"id": "atom", "name": "a", "status": "positive", "version": "1.0.0",
                 "description": "d", "task": "t",
                 "signals": [{"family": "imu", "name": "accel"}],
                 "date_created": "2026-07-19", "valid_until": "2026-08-01"},
        "comp": {"id": "comp", "name": "c", "status": "positive", "version": "1.0.0",
                 "description": "d", "task": "t",
                 "signals": [{"family": "imu", "name": "accel"}],
                 "date_created": "2026-07-19", "valid_until": "2027-01-01",
                 "depends_on": ["atom"], "composition_operator": "fusion"},
    })
    res = validate_registry(reg)
    assert any("exceeds dependency" in s for s in res["semantic_errors"])


# --------------------------- composition -----------------------------------

def test_fusion_energy_dedup_and_expiry_min():
    a = composition.CapabilitySpec("a", 0.8, 10.0, 5.0, 0.9, "2027-01-01", ("wifi",))
    b = composition.CapabilitySpec("b", 0.7, 6.0, 4.0, 0.8, "2026-09-01", ("wifi",))
    c = composition.fuse(a, b)
    # shared "wifi" sensing charged once -> less than naive 16.0
    assert c.energy_mj < 16.0
    assert c.valid_until == "2026-09-01"        # min expiry
    assert c.privacy_score == 0.8               # most-revealing dominates


def test_refinement_confidence_is_product_upper_bound():
    a = composition.CapabilitySpec("a", 0.8, 1.0, 1.0, 1.0, "2027-01-01")
    b = composition.CapabilitySpec("b", 0.5, 1.0, 1.0, 1.0, "2027-01-01")
    c = composition.refine(a, b)
    assert abs(c.confidence_upper - 0.4) < 1e-9


# --------------------------- audit -----------------------------------------

def test_permissionless_and_disclosure_sensitive():
    a = audit.audit_capability(
        signal_permissions=["none", "cpu_timing"],
        bystander_inference="x", escalation_gradient="y", mitigations="z",
        escalation_unbounded=True)
    assert a.permissionless is True
    assert a.disclosure_sensitive is True
    assert a.score < 0.5


def test_permissioned_not_disclosure_sensitive():
    a = audit.audit_capability(
        signal_permissions=["ACCESS_FINE_LOCATION"],
        bystander_inference="x", escalation_gradient="y", mitigations="z")
    assert a.permissionless is False
    assert a.disclosure_sensitive is False

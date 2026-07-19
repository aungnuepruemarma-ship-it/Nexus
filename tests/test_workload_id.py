"""Fast, deterministic tests for the co-located workload-type capability.

Follows the repo convention that real-hardware timing experiments are NOT exercised in the
test suite (they spawn burners, take seconds and are host/timing dependent). We test the
pure feature function, the metadata invariants, and the falsify -> certify -> schema path on
seeded synthetic data instead — mirroring tests/test_pipeline.py."""
import numpy as np

from ccs.hardware import workload_id as wid
from ccs.signals import FeatureSet
from ccs.harness import ExperimentSpec, Dataset, InvarianceAxis, falsify
from ccs.capability import certify
from ccs.audit import audit_capability
from ccs.validator import validate_entry


def test_feature_names_match_vector():
    rng = np.random.default_rng(0)
    compute_ns = rng.normal(40_000, 2_000, 300)
    mem_ns = rng.normal(470_000, 10_000, 200)
    v = wid._features_from_timings(compute_ns, mem_ns)
    assert v.shape == (len(wid.WORKLOAD_FEATURE_NAMES),)
    assert len(wid.WORKLOAD_FEATURE_SIGNALS) == len(wid.WORKLOAD_FEATURE_NAMES)
    assert set(wid.WORKLOAD_FEATURE_SIGNALS) == {"compute_probe", "mem_probe"}
    assert np.all(np.isfinite(v))


def test_pointer_chase_is_single_cycle():
    # Every entry visited exactly once before returning to the start == one Hamiltonian cycle,
    # which is what makes the walk data-dependent (prefetch-defeating).
    buf = wid._pointer_chase_buffer(1024, seed=7)
    seen = set()
    idx = 0
    for _ in range(len(buf)):
        seen.add(idx)
        idx = int(buf[idx])
    assert len(seen) == len(buf)
    assert idx == 0  # closed the cycle


def test_generator_idle_spawns_nothing_and_rejects_unknown():
    with wid.WorkloadGenerator("idle") as g:
        assert g.procs == []
    try:
        wid.WorkloadGenerator("gpu_bound")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("unknown workload kind must raise")


def _synthetic_dataset(seed=0, n_per=24, blocks=4):
    """Seeded, physically-shaped clusters: the compute probe separates idle from the loaded
    classes, the memory probe separates memory_bound from the rest — so neither single probe
    is sufficient but the pair is. Guarantees the two-signal candidate strictly beats each
    single-signal baseline (a genuine, non-redundant positive)."""
    rng = np.random.default_rng(seed)
    n_c = wid.WORKLOAD_FEATURE_SIGNALS.count("compute_probe")
    # per-class means on the (compute-level, memory-level) axes
    compute_level = {"idle": 0.0, "cpu_bound": 6.0, "memory_bound": 6.0}
    memory_level = {"idle": 0.0, "cpu_bound": 0.0, "memory_bound": 6.0}
    X, y, block = [], [], []
    for b in range(blocks):
        for kind in wid.WORKLOAD_CLASSES:
            for _ in range(n_per):
                row = []
                for sig in wid.WORKLOAD_FEATURE_SIGNALS:
                    base = compute_level[kind] if sig == "compute_probe" else memory_level[kind]
                    row.append(base + rng.normal(0, 0.6))
                X.append(row)
                y.append(kind)
                block.append(b)
    fs = FeatureSet(X=np.array(X), names=wid.WORKLOAD_FEATURE_NAMES,
                    t_ns=np.arange(len(y), dtype=np.int64),
                    feature_signal=list(wid.WORKLOAD_FEATURE_SIGNALS))
    axes = [InvarianceAxis("time_block", np.array(block),
                           tuple(range(blocks - 1)), (blocks - 1,))]
    ds = Dataset(fs=fs, y=np.array(y), axes=axes,
                 signal_cost_mj={"compute_probe": 0.0, "mem_probe": 0.0})
    spec = ExperimentSpec("EXP-HW-WORKLOAD-ID", "t", "q",
                          "co-located workload type: idle / cpu_bound / memory_bound",
                          wid.WORKLOAD_CLASSES, 0.70, 1e9, 1e9)
    return ds, spec


def test_two_probe_candidate_beats_single_probe_baselines():
    ds, spec = _synthetic_dataset()
    both = falsify(spec, ds, ("compute_probe", "mem_probe"))
    compute_only = falsify(spec, ds, ("compute_probe",))
    mem_only = falsify(spec, ds, ("mem_probe",))
    # neither probe alone can resolve all three classes; the pair can
    assert both.metrics["accuracy"] > compute_only.metrics["accuracy"]
    assert both.metrics["accuracy"] > mem_only.metrics["accuracy"]
    assert both.status == "positive"


def test_certified_entry_is_schema_valid():
    ds, spec = _synthetic_dataset()
    result = falsify(spec, ds, ("compute_probe", "mem_probe"))
    audit = audit_capability(
        signal_permissions=["none", "none"],
        bystander_inference="workload-type diagnosis side channel",
        escalation_gradient="none demonstrated",
        mitigations="coarsen clock; partition bandwidth",
    )
    entry = certify(
        "workload_type_classifier_test", "test", spec, result,
        signals=[{"family": "cpu", "name": "compute_probe", "android_permission": "none"},
                 {"family": "memory", "name": "mem_probe", "android_permission": "none"}],
        model={"kind": "random forest", "features": "two-probe timing shape"},
        audit=audit, provenance=[], half_life_days=120,
        description="synthetic schema check for the workload-type classifier",
        generalization={"axis": "time_block", "per_axis_accuracy": result.per_axis_accuracy},
    )
    assert validate_entry(entry) == []

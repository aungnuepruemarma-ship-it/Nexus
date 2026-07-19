"""Experiment harness: pre-registration, invariance splits, baselines, typed failures.

Implements Prospecting-Loop stages 3-4 (docs/ccs-vision.md sections 3-4). A capability
claim is *pre-registered* (target accuracy + budgets fixed before the run), then the
harness tries to *falsify* it: it must transfer across every declared invariance axis
(e.g. cross-OEM AND cross-room), beat the best single-signal baseline on the same
split, reproduce across an independent re-split, and stay within budget. Any failure
produces a typed negative.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np

from .signals import FeatureSet
from .metrics import evaluate, majority_baseline_accuracy, Metrics

# Typed failure conditions — must match registry/capability.schema.json failure_type enum.
FAILURE_TYPES = (
    "redundant-with-baseline", "non-reproducible", "oem-bound",
    "environment-bound", "over-budget", "screened-out",
)


# ---------------------------------------------------------------------------
# Default model. Small, dependency-light, with a numpy fallback.
# ---------------------------------------------------------------------------

def default_model_factory():
    try:
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=120, max_depth=None,
                                      random_state=0, n_jobs=-1)
    except Exception:  # pragma: no cover
        return _NearestCentroid()


class _NearestCentroid:
    """Fallback classifier: standardized nearest-centroid with proba via softmax."""
    def fit(self, X, y):
        X = np.asarray(X, float)
        self.mu = X.mean(0); self.sd = X.std(0) + 1e-9
        Xs = (X - self.mu) / self.sd
        self.classes_ = np.unique(y)
        self.cent = np.array([Xs[np.asarray(y) == c].mean(0) for c in self.classes_])
        return self

    def _d(self, X):
        Xs = (np.asarray(X, float) - self.mu) / self.sd
        return np.linalg.norm(Xs[:, None, :] - self.cent[None, :, :], axis=2)

    def predict(self, X):
        return self.classes_[np.argmin(self._d(X), axis=1)]

    def predict_proba(self, X):
        d = self._d(X)
        z = np.exp(-(d - d.min(1, keepdims=True)))
        return z / z.sum(1, keepdims=True)


# ---------------------------------------------------------------------------
# Experiment specification and dataset.
# ---------------------------------------------------------------------------

@dataclass
class InvarianceAxis:
    """One axis the capability must generalize across (e.g. OEM, room, time-block)."""
    name: str
    groups: np.ndarray            # per-window group label
    train_values: tuple
    test_values: tuple


@dataclass
class ExperimentSpec:
    experiment_id: str
    title: str
    question: str
    task: str
    classes: tuple
    target_accuracy: float
    energy_budget_mj: float
    latency_budget_ms: float


@dataclass
class Dataset:
    fs: FeatureSet
    y: np.ndarray
    axes: list[InvarianceAxis] = field(default_factory=list)
    signal_cost_mj: dict = field(default_factory=dict)   # per-signal sensing energy


@dataclass
class CertificationResult:
    passed: bool
    status: str                          # positive / unstable / negative
    failure_type: str | None
    metrics: dict
    baseline_best_acc: float
    baseline_best_signal: str
    per_axis_accuracy: dict
    energy_mj: float
    latency_ms: float
    reproduced: bool
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Split construction.
# ---------------------------------------------------------------------------

def _axis_mask(axis: InvarianceAxis, which: str) -> np.ndarray:
    vals = axis.train_values if which == "train" else axis.test_values
    return np.isin(axis.groups, list(vals))


def make_split(axes: list[InvarianceAxis], n: int):
    """Train = intersection of all axes' train partitions; test = intersection of
    all axes' test partitions. Enforces simultaneous transfer across every axis."""
    if not axes:
        # random 60/40 fallback
        rng = np.random.default_rng(0)
        idx = rng.permutation(n)
        cut = int(0.6 * n)
        tr = np.zeros(n, bool); tr[idx[:cut]] = True
        te = ~tr
        return tr, te
    tr = np.ones(n, bool); te = np.ones(n, bool)
    for ax in axes:
        tr &= _axis_mask(ax, "train")
        te &= _axis_mask(ax, "test")
    return tr, te


# ---------------------------------------------------------------------------
# Falsification.
# ---------------------------------------------------------------------------

def _as_str_labels(y) -> np.ndarray:
    """Normalize labels to a string array so classifiers and equality checks agree
    regardless of the original label type (int occupancy classes, str device ids...)."""
    return np.asarray([str(v) for v in np.asarray(y).ravel()], dtype=object)


def _fit_predict(model_factory, Xtr, ytr, Xte):
    model = model_factory()
    model.fit(Xtr, _as_str_labels(ytr))
    yp = model.predict(Xte)
    try:
        proba = model.predict_proba(Xte)
        classes = list(model.classes_)
    except Exception:
        proba, classes = None, None
    return yp, proba, classes


def _subset_columns(fs: FeatureSet, signal_subset) -> np.ndarray:
    return fs.columns_for(signal_subset)


def falsify(
    spec: ExperimentSpec,
    dataset: Dataset,
    signal_subset,
    model_factory=default_model_factory,
    compute_energy_mj: float = 1.0,
    inference_latency_ms: float | None = None,
) -> CertificationResult:
    """Run the full certification standard against ``signal_subset``."""
    fs, y = dataset.fs, _as_str_labels(dataset.y)
    labels = [str(c) for c in spec.classes]
    notes: list[str] = []

    tr, te = make_split(dataset.axes, len(y))
    if tr.sum() < len(labels) or te.sum() < len(labels):
        return CertificationResult(
            passed=False, status="negative", failure_type="non-reproducible",
            metrics={}, baseline_best_acc=0.0, baseline_best_signal="",
            per_axis_accuracy={}, energy_mj=0.0, latency_ms=0.0, reproduced=False,
            notes=["insufficient data in train/test split"],
        )

    mask = _subset_columns(fs, signal_subset)
    Xtr, Xte = fs.X[tr][:, mask], fs.X[te][:, mask]
    ytr, yte = y[tr], y[te]

    yp, proba, classes = _fit_predict(model_factory, Xtr, ytr, Xte)
    order_proba = None
    if proba is not None:
        # reorder proba columns to match spec.classes order
        cmap = {c: i for i, c in enumerate(classes)}
        cols = [cmap[c] for c in labels if c in cmap]
        if len(cols) == len(labels):
            order_proba = proba[:, cols]
    m: Metrics = evaluate(yte, yp, labels, proba=order_proba)

    # ---- single-signal baselines on the SAME split ------------------------
    # Compare against the majority-class baseline and every *other* single signal.
    # A single-signal candidate is not compared against itself (that is the capability).
    baseline_best_acc, baseline_best_signal = majority_baseline_accuracy(yte), "majority"
    subset_set = set(signal_subset)
    for sig in sorted(set(fs.feature_signal)):
        if {sig} == subset_set:
            continue
        smask = fs.columns_for([sig])
        if smask.sum() == 0:
            continue
        bp, _, _ = _fit_predict(model_factory, fs.X[tr][:, smask], ytr, fs.X[te][:, smask])
        acc = float(np.mean([a == b for a, b in zip(yte, bp)]))
        if acc > baseline_best_acc:
            baseline_best_acc, baseline_best_signal = acc, sig

    # ---- reproduction: independent re-split (seeded differently) ----------
    reproduced = _reproduce(spec, dataset, signal_subset, model_factory, m.accuracy)

    # ---- per-axis diagnostics (which axis, if any, breaks) ---------------
    per_axis = {}
    for ax in dataset.axes:
        per_axis[ax.name] = _axis_accuracy(fs, y, ax, signal_subset, model_factory, labels)

    # ---- cost accounting --------------------------------------------------
    sensing = sum(dataset.signal_cost_mj.get(s, 0.0) for s in signal_subset)
    energy = round(sensing + compute_energy_mj, 4)
    latency = inference_latency_ms if inference_latency_ms is not None else round(
        1.0 + 0.5 * Xtr.shape[1], 3)

    # ---- typed failure evaluation ----------------------------------------
    status, failure_type, passed = _classify_outcome(
        spec, m, baseline_best_acc, per_axis, energy, latency, reproduced, notes)

    return CertificationResult(
        passed=passed, status=status, failure_type=failure_type,
        metrics=m.as_dict(), baseline_best_acc=round(baseline_best_acc, 4),
        baseline_best_signal=baseline_best_signal, per_axis_accuracy=per_axis,
        energy_mj=energy, latency_ms=latency, reproduced=reproduced, notes=notes,
    )


def _axis_accuracy(fs, y, axis, signal_subset, model_factory, labels) -> float:
    tr = _axis_mask(axis, "train"); te = _axis_mask(axis, "test")
    if tr.sum() < len(labels) or te.sum() < len(labels):
        return float("nan")
    mask = fs.columns_for(signal_subset)
    yp, _, _ = _fit_predict(model_factory, fs.X[tr][:, mask], y[tr], fs.X[te][:, mask])
    return round(float(np.mean([a == b for a, b in zip(y[te], yp)])), 4)


def _reproduce(spec, dataset, signal_subset, model_factory, ref_acc, tol=0.1) -> bool:
    """Re-run on a shuffled 60/40 split; must land within tol of the reference."""
    fs, y = dataset.fs, _as_str_labels(dataset.y)
    rng = np.random.default_rng(12345)
    idx = rng.permutation(len(y))
    cut = int(0.6 * len(y))
    tr = np.zeros(len(y), bool); tr[idx[:cut]] = True
    te = ~tr
    labels = list(spec.classes)
    if tr.sum() < len(labels) or te.sum() < len(labels):
        return False
    mask = fs.columns_for(signal_subset)
    yp, _, _ = _fit_predict(model_factory, fs.X[tr][:, mask], y[tr], fs.X[te][:, mask])
    acc = float(np.mean([a == b for a, b in zip(y[te], yp)]))
    return abs(acc - ref_acc) <= tol


def _classify_outcome(spec, m, baseline_best_acc, per_axis, energy, latency,
                      reproduced, notes):
    """Apply typed failure conditions in priority order."""
    # over budget (cost violations dominate everything)
    if energy > spec.energy_budget_mj or latency > spec.latency_budget_ms:
        notes.append(f"energy {energy}mJ / latency {latency}ms vs budget "
                     f"{spec.energy_budget_mj}mJ / {spec.latency_budget_ms}ms")
        return "negative", "over-budget", False

    # invariance failures — an axis far below target while another axis holds is a
    # binding (memorized a device/room), a more informative diagnosis than "redundant".
    broken = [name for name, acc in per_axis.items()
              if not np.isnan(acc) and acc < spec.target_accuracy]
    passing = [name for name, acc in per_axis.items()
               if not np.isnan(acc) and acc >= spec.target_accuracy]
    if broken:
        oem_broken = [b for b in broken if "oem" in b or "device" in b]
        env_broken = [b for b in broken if b not in oem_broken]  # room/time/condition axes
        ftype = "oem-bound" if oem_broken else "environment-bound"
        # A total collapse on an axis (near chance) with nothing passing => negative;
        # a partial binding with some axis still holding => scoped unstable.
        collapsed = any(per_axis[b] <= (1.0 / max(2, len(spec.classes))) + 0.05 for b in broken)
        if collapsed and not passing:
            notes.append(f"collapses on invariance axes {broken}")
            return "negative", ftype, False
        notes.append(f"fails invariance axes {broken}; holds on {passing}; scoped unstable")
        return "unstable", ftype, False

    # redundant with a single-signal baseline (transfers, but fusion adds nothing)
    if m.accuracy <= baseline_best_acc + 1e-9:
        notes.append(f"accuracy {m.accuracy:.3f} does not beat best single-signal "
                     f"baseline {baseline_best_acc:.3f} ({'the real capability'})")
        return "negative", "redundant-with-baseline", False
    # not reproducible
    if not reproduced:
        notes.append("independent re-split fell outside tolerance")
        return "negative", "non-reproducible", False
    # target accuracy on the full invariance split
    if m.accuracy < spec.target_accuracy:
        notes.append(f"accuracy {m.accuracy:.3f} < target {spec.target_accuracy}")
        return "unstable", None, False
    return "positive", None, True

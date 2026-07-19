"""Screening: mutual-information gate over the signal-subset lattice.

This is Prospecting-Loop stage 2 (docs/ccs-vision.md section 3). Before spending
any model-training budget, estimate the mutual information I(S; T) between candidate
signal subsets and the task label, rank survivors by information per unit sensing
cost, and prune the lattice using the monotonicity of information: if a subset S
scores below threshold, every subset of S is also below threshold and need not be
tested. Screened-out subsets are emitted as weak negatives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from .signals import FeatureSet


# ---------------------------------------------------------------------------
# Non-parametric MI estimators.
# ---------------------------------------------------------------------------

def _entropy_from_counts(counts) -> float:
    counts = np.asarray(counts, dtype=float)
    p = counts / counts.sum()
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


def mi_discrete(x_labels, y_labels) -> float:
    """MI in bits between two discrete label arrays."""
    xs = np.asarray(x_labels)
    ys = np.asarray(y_labels)
    xv, xi = np.unique(xs, return_inverse=True)
    yv, yi = np.unique(ys, return_inverse=True)
    joint = np.zeros((len(xv), len(yv)))
    for a, b in zip(xi, yi):
        joint[a, b] += 1
    n = joint.sum()
    if n == 0:
        return 0.0
    hx = _entropy_from_counts(joint.sum(axis=1))
    hy = _entropy_from_counts(joint.sum(axis=0))
    hxy = _entropy_from_counts(joint.flatten())
    return max(0.0, hx + hy - hxy)


def _quantize(col, bins) -> np.ndarray:
    """Quantile-binning of a continuous feature into ``bins`` discrete levels."""
    col = np.asarray(col, dtype=float)
    if np.allclose(col, col[0]):
        return np.zeros(len(col), dtype=int)
    qs = np.quantile(col, np.linspace(0, 1, bins + 1)[1:-1])
    qs = np.unique(qs)
    return np.digitize(col, qs)


def mi_feature_label(feature_col, labels, bins: int = 8) -> float:
    """Estimated MI(feature; label) in bits via quantile binning."""
    xb = _quantize(feature_col, bins)
    return mi_discrete(xb, labels)


def mi_subset_label(X: np.ndarray, labels, bins: int = 6, top_k: int = 3) -> float:
    """Estimate MI of a multi-column subset with the label.

    Uses a joint code of the ``top_k`` most individually-informative columns
    (quantized) to approximate the subset's joint MI while controlling the curse
    of dimensionality. This is a screening estimate, not a certified number.
    """
    if X.shape[1] == 0:
        return 0.0
    per_col = np.array([mi_feature_label(X[:, j], labels, bins) for j in range(X.shape[1])])
    keep = np.argsort(per_col)[::-1][:top_k]
    codes = np.zeros(X.shape[0], dtype=np.int64)
    base = 1
    for j in keep:
        q = _quantize(X[:, j], bins)
        codes = codes + base * q
        base *= (bins + 1)
    return mi_discrete(codes, labels)


# ---------------------------------------------------------------------------
# Lattice screening.
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    signals: tuple[str, ...]
    mi_bits: float
    sensing_cost_mj: float
    mi_per_mj: float
    label_entropy_bits: float

    @property
    def info_fraction(self) -> float:
        """Fraction of the label's entropy this subset explains (0..1)."""
        return self.mi_bits / self.label_entropy_bits if self.label_entropy_bits > 0 else 0.0


@dataclass
class ScreeningResult:
    candidates: list[Candidate]                    # survivors, ranked by mi_per_mj
    screened_out: list[tuple[str, ...]] = field(default_factory=list)
    pruned: list[tuple[str, ...]] = field(default_factory=list)  # skipped by monotonicity
    threshold_bits: float = 0.0
    label_entropy_bits: float = 0.0

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None


def screen_lattice(
    fs: FeatureSet,
    labels,
    signal_costs: dict[str, float],
    max_order: int = 3,
    threshold_bits: float = 0.1,
    bins: int = 6,
) -> ScreeningResult:
    """Walk the signal-subset lattice bottom-up with monotone pruning.

    ``signal_costs`` maps signal name -> sensing energy (mJ). We enumerate subsets
    up to ``max_order`` signals. A subset is pruned (untested) if any of its
    immediate sub-subsets already fell below threshold — the monotonicity of
    information guarantees it cannot exceed the threshold either.
    """
    signals = sorted(set(fs.feature_signal))
    label_H = _entropy_from_counts(
        np.unique(np.asarray(labels, dtype=object), return_counts=True)[1]
    )

    survivors: list[Candidate] = []
    screened_out: list[tuple[str, ...]] = []
    pruned: list[tuple[str, ...]] = []
    failed: set[frozenset] = set()  # subsets known to be below threshold

    for order in range(1, max_order + 1):
        for combo in combinations(signals, order):
            cs = frozenset(combo)
            # Monotone pruning: if any (order-1) sub-subset failed, skip.
            if order > 1 and any(frozenset(sub) in failed
                                 for sub in combinations(combo, order - 1)):
                pruned.append(combo)
                continue
            sub = fs.subset(combo)
            mi = mi_subset_label(sub.X, labels, bins=bins)
            if mi < threshold_bits:
                failed.add(cs)
                screened_out.append(combo)
                continue
            cost = sum(signal_costs.get(s, 1.0) for s in combo)
            survivors.append(Candidate(
                signals=combo,
                mi_bits=round(mi, 4),
                sensing_cost_mj=round(cost, 4),
                mi_per_mj=round(mi / cost, 6) if cost > 0 else 0.0,
                label_entropy_bits=round(label_H, 4),
            ))

    survivors.sort(key=lambda c: c.mi_per_mj, reverse=True)
    return ScreeningResult(
        candidates=survivors,
        screened_out=screened_out,
        pruned=pruned,
        threshold_bits=threshold_bits,
        label_entropy_bits=round(label_H, 4),
    )

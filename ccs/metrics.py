"""Classification and cost metrics used by the harness and registry.

Implemented with numpy so the platform has no hard sklearn dependency at
evaluation time (sklearn is used only in models/screening baselines where handy).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class Metrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    n: int

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in asdict(self).items()}


def confusion(y_true, y_pred, labels) -> np.ndarray:
    idx = {c: i for i, c in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[idx[t], idx[p]] += 1
    return m


def _macro_prf(y_true, y_pred, labels):
    cm = confusion(y_true, y_pred, labels)
    precs, recs, f1s = [], [], []
    for i in range(len(labels)):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        precs.append(p); recs.append(r); f1s.append(f)
    return float(np.mean(precs)), float(np.mean(recs)), float(np.mean(f1s))


def _roc_auc_binary(y_true_bin, scores) -> float:
    """Rank-based AUC (Mann-Whitney U). Ties handled by average rank."""
    y = np.asarray(y_true_bin, dtype=int)
    s = np.asarray(scores, dtype=float)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        ranks[order[i:j + 1]] = avg
        i = j + 1
    sum_ranks_pos = ranks[y == 1].sum()
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def roc_auc(y_true, proba, labels) -> float:
    """One-vs-rest macro ROC-AUC. ``proba`` is (n, n_labels)."""
    proba = np.asarray(proba, dtype=float)
    if proba.ndim == 1:
        proba = np.column_stack([1 - proba, proba])
    aucs = []
    for i, c in enumerate(labels):
        yb = np.array([1 if t == c else 0 for t in y_true])
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue
        aucs.append(_roc_auc_binary(yb, proba[:, i]))
    return float(np.mean(aucs)) if aucs else 0.5


def evaluate(y_true, y_pred, labels, proba=None) -> Metrics:
    y_true = list(y_true)
    y_pred = list(y_pred)
    acc = float(np.mean([t == p for t, p in zip(y_true, y_pred)])) if y_true else 0.0
    prec, rec, f1 = _macro_prf(y_true, y_pred, labels)
    auc = roc_auc(y_true, proba, labels) if proba is not None else 0.5
    return Metrics(accuracy=acc, precision=prec, recall=rec, f1=f1,
                   roc_auc=auc, n=len(y_true))


def majority_baseline_accuracy(y_true) -> float:
    vals, counts = np.unique(np.asarray(y_true, dtype=object), return_counts=True)
    return float(counts.max() / counts.sum()) if len(y_true) else 0.0

"""Causal Discovery Engine — the associational skeleton of a hardware-signal graph.

Honest scope: this is NOT interventional causality. It recovers the *skeleton* of a
linear-Gaussian graphical model (the first phase of the PC algorithm): an edge between two
signals survives only if their **partial correlation** — the correlation that remains after
controlling for every other measured signal — exceeds a threshold. A pair that is marginally
correlated but whose partial correlation collapses is flagged as *mediated* (indirect), which
is exactly the "A affects B only through C" pattern. Directionality and true interventions are
out of scope and stated as such; this is the causal-discovery primitive the platform can build
on, run on real measured features.
"""
from __future__ import annotations

import numpy as np


def partial_correlations(X: np.ndarray) -> np.ndarray:
    """Partial correlation matrix (control for all other columns) via the precision matrix."""
    X = np.asarray(X, dtype=np.float64)
    C = np.corrcoef(X, rowvar=False)
    C = np.nan_to_num(C, nan=0.0)
    C += 1e-6 * np.eye(C.shape[0])          # ridge for numerical stability / singular inputs
    P = np.linalg.pinv(C)
    d = np.sqrt(np.clip(np.diag(P), 1e-12, None))
    pc = -P / np.outer(d, d)
    np.fill_diagonal(pc, 1.0)
    return pc


def associational_skeleton(X: np.ndarray, names: list[str],
                           direct_threshold: float = 0.3,
                           marginal_threshold: float = 0.3) -> dict:
    """Recover direct (partial-corr) edges and flag mediated (marginal-only) pairs."""
    X = np.asarray(X, dtype=np.float64)
    marg = np.nan_to_num(np.corrcoef(X, rowvar=False), nan=0.0)
    pc = partial_correlations(X)
    n = len(names)
    direct, mediated, collider = [], [], []
    for i in range(n):
        for j in range(i + 1, n):
            m, p = float(marg[i, j]), float(pc[i, j])
            am, ap = abs(m), abs(p)
            edge = {"a": names[i], "b": names[j], "partial": round(p, 3), "marginal": round(m, 3)}
            if ap >= direct_threshold and am >= marginal_threshold:
                direct.append(edge)                 # correlated both ways -> a direct link
            elif ap >= direct_threshold and am < marginal_threshold:
                collider.append(edge)               # partial-only -> conditioning opened a collider
            elif am >= marginal_threshold and ap < direct_threshold:
                mediated.append(edge)               # marginal-only -> indirect / mediated
    return {"n_vars": n,
            "n_direct_edges": len(direct), "n_mediated_pairs": len(mediated),
            "n_collider_suspects": len(collider),
            "direct_edges": sorted(direct, key=lambda e: -abs(e["partial"])),
            "mediated_pairs": sorted(mediated, key=lambda e: -abs(e["marginal"])),
            "collider_suspects": sorted(collider, key=lambda e: -abs(e["partial"])),
            "method": ("linear-Gaussian partial-correlation skeleton (PC phase-1): direct = "
                       "marginal AND partial correlated; mediated = marginal only; collider "
                       "suspect = partial only. Associational and undirected — no interventions.")}


def discover_from_workload(n_windows: int = 40, seed: int = 0) -> dict:
    """Collect a real two-probe feature matrix (idle) and recover its associational skeleton."""
    from ccs.hardware import workload_id as wid
    rows = [wid.window_features() for _ in range(n_windows)]
    X = np.asarray(rows, dtype=np.float64)
    # drop zero-variance columns (constant features carry no association)
    keep = [i for i in range(X.shape[1]) if np.std(X[:, i]) > 0]
    names = [wid.WORKLOAD_FEATURE_NAMES[i] for i in keep]
    out = associational_skeleton(X[:, keep], names)
    out["n_windows"] = n_windows
    return out

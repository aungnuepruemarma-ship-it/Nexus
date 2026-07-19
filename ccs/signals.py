"""Signals and windowed feature extraction.

A ``Signal`` is a named, time-stamped physical observable recorded on a single
monotonic timeline (see docs/architecture.md section 2). Feature extraction turns
a raw signal into fixed-length windowed feature vectors that screening and the
harness consume. The logger records reality; this module is the first place that
interpretation happens, and it is deliberately generic (no task-specific logic).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

# Signal families recognized across the platform. Must match the enum in
# registry/capability.schema.json ("signals[].family").
FAMILIES = (
    "imu", "battery", "thermal", "cpu", "memory",
    "network", "light", "pressure", "capability",
)


@dataclass
class Signal:
    """A single physical observable sampled on the monotonic timeline.

    ``t_ns`` and ``value`` are parallel arrays of equal length. ``value`` may be
    multi-column (e.g. 3-axis IMU) with shape (n_samples, n_axes).
    """
    name: str
    family: str
    t_ns: np.ndarray
    value: np.ndarray
    sampling: str = ""

    def __post_init__(self) -> None:
        self.t_ns = np.asarray(self.t_ns, dtype=np.int64)
        self.value = np.asarray(self.value, dtype=np.float64)
        if self.value.ndim == 1:
            self.value = self.value.reshape(-1, 1)
        if self.family not in FAMILIES:
            raise ValueError(f"unknown signal family: {self.family!r}")
        if len(self.t_ns) != len(self.value):
            raise ValueError("t_ns and value length mismatch")

    @property
    def n_axes(self) -> int:
        return self.value.shape[1]


# ---------------------------------------------------------------------------
# Feature functions. Each maps a (window_len, n_axes) block to a scalar per axis.
# Kept small, cheap, and interpretable: these are what screening estimates MI over.
# ---------------------------------------------------------------------------

def _safe(x: np.ndarray) -> np.ndarray:
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def f_mean(w):    return _safe(np.mean(w, axis=0))
def f_std(w):     return _safe(np.std(w, axis=0))
def f_min(w):     return _safe(np.min(w, axis=0))
def f_max(w):     return _safe(np.max(w, axis=0))
def f_range(w):   return _safe(np.max(w, axis=0) - np.min(w, axis=0))
def f_iqr(w):     return _safe(np.subtract(*np.percentile(w, [75, 25], axis=0)))
def f_slope(w):
    n = w.shape[0]
    if n < 2:
        return np.zeros(w.shape[1])
    t = np.arange(n)
    t = t - t.mean()
    denom = float(np.dot(t, t))
    return _safe((t @ (w - w.mean(axis=0))) / denom)


def f_spec_entropy(w):
    """Spectral entropy per axis: how spread the power spectrum is (0..1)."""
    out = []
    for j in range(w.shape[1]):
        x = w[:, j] - np.mean(w[:, j])
        ps = np.abs(np.fft.rfft(x)) ** 2
        s = ps.sum()
        if s <= 0:
            out.append(0.0)
            continue
        p = ps / s
        p = p[p > 0]
        h = -np.sum(p * np.log2(p))
        hmax = np.log2(len(ps)) if len(ps) > 1 else 1.0
        out.append(float(h / hmax) if hmax > 0 else 0.0)
    return _safe(np.array(out))


DEFAULT_FEATURES: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "mean": f_mean,
    "std": f_std,
    "range": f_range,
    "iqr": f_iqr,
    "slope": f_slope,
    "spec_entropy": f_spec_entropy,
}


@dataclass
class FeatureSet:
    """Extracted windowed features for a set of signals.

    ``X`` has shape (n_windows, n_features); ``names`` labels the columns as
    ``"<signal>.<axis>.<feature>"``. ``t_ns`` is the start time of each window.
    """
    X: np.ndarray
    names: list[str]
    t_ns: np.ndarray
    feature_signal: list[str] = field(default_factory=list)  # signal name per column

    def columns_for(self, signal_names) -> np.ndarray:
        """Boolean mask selecting columns that came from ``signal_names``."""
        wanted = set(signal_names)
        return np.array([s in wanted for s in self.feature_signal], dtype=bool)

    def subset(self, signal_names) -> "FeatureSet":
        mask = self.columns_for(signal_names)
        return FeatureSet(
            X=self.X[:, mask],
            names=[n for n, m in zip(self.names, mask) if m],
            t_ns=self.t_ns,
            feature_signal=[s for s, m in zip(self.feature_signal, mask) if m],
        )


def extract_features(
    signals: list[Signal],
    window_ns: int,
    hop_ns: int | None = None,
    features: dict | None = None,
) -> FeatureSet:
    """Slide a window over the shared timeline and extract features per signal.

    Windows are aligned to a common grid so every signal contributes columns to
    the same rows. Signals with no samples in a window contribute zeros.
    """
    if not signals:
        raise ValueError("no signals given")
    features = features or DEFAULT_FEATURES
    hop_ns = hop_ns or window_ns

    t0 = min(int(s.t_ns[0]) for s in signals)
    t1 = max(int(s.t_ns[-1]) for s in signals)
    starts = np.arange(t0, max(t0 + 1, t1 - window_ns + 1), hop_ns, dtype=np.int64)

    cols: list[np.ndarray] = []
    names: list[str] = []
    feat_sig: list[str] = []

    for s in signals:
        idx = np.searchsorted(s.t_ns, starts)
        for ax in range(s.n_axes):
            for fname, fn in features.items():
                col = np.empty(len(starts), dtype=np.float64)
                for i, st in enumerate(starts):
                    lo = np.searchsorted(s.t_ns, st, side="left")
                    hi = np.searchsorted(s.t_ns, st + window_ns, side="left")
                    if hi - lo < 1:
                        col[i] = 0.0
                    else:
                        col[i] = fn(s.value[lo:hi])[ax]
                cols.append(col)
                names.append(f"{s.name}.{ax}.{fname}")
                feat_sig.append(s.name)
    X = np.column_stack(cols) if cols else np.empty((len(starts), 0))
    return FeatureSet(X=X, names=names, t_ns=starts, feature_signal=feat_sig)

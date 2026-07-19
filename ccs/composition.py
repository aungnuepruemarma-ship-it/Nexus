"""The capability algebra (docs/ccs-vision.md section 7).

Composition operators combine certified capabilities into composites. The algebra
provides *upper bounds and null hypotheses*, never the final confidence — a composite
is certified the same way an atom is (measurement decides). What the algebra
guarantees is cost/expiry accounting: energy and privacy costs are conserved (only
add, minus shared sensing), and expiry propagates as the minimum over parts.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass
class CapabilitySpec:
    """Lightweight view of a capability used for algebra (subset of a registry entry)."""
    id: str
    confidence: float
    energy_mj: float
    latency_ms: float
    privacy_score: float
    valid_until: str
    signals: tuple[str, ...] = ()

    @classmethod
    def from_entry(cls, e: dict) -> "CapabilitySpec":
        return cls(
            id=e["id"],
            confidence=float(e.get("confidence", e.get("accuracy", 0.0))),
            energy_mj=float(e.get("energy_mj", 0.0)),
            latency_ms=float(e.get("latency_ms", 0.0)),
            privacy_score=float((e.get("privacy_audit") or {}).get("score", 1.0)),
            valid_until=e.get("valid_until", ""),
            signals=tuple(s.get("name") for s in e.get("signals", []) if s.get("name")),
        )


def _min_date(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    return min(a, b, key=dt.date.fromisoformat)


def _merged_energy(a: CapabilitySpec, b: CapabilitySpec) -> float:
    """Energy adds, but sensing shared between the two is only paid once.

    We approximate shared sensing cost as proportional to the fraction of shared
    signals, charged at the cheaper operand's per-signal average.
    """
    shared = set(a.signals) & set(b.signals)
    total = a.energy_mj + b.energy_mj
    if shared and a.signals and b.signals:
        per_a = a.energy_mj / max(1, len(a.signals))
        per_b = b.energy_mj / max(1, len(b.signals))
        total -= len(shared) * min(per_a, per_b)
    return round(max(0.0, total), 4)


@dataclass
class CompositeBound:
    """The algebra's predicted bounds for a composite (to be tested, not trusted)."""
    operator: str
    depends_on: tuple[str, ...]
    confidence_upper: float      # null/upper bound; real value comes from Falsify
    energy_mj: float
    latency_ms: float
    privacy_score: float         # min of parts (most revealing dominates)
    valid_until: str             # min over parts
    signals: tuple[str, ...]


def fuse(a: CapabilitySpec, b: CapabilitySpec) -> CompositeBound:
    """A ⊕ B: same task, different signals. Confidence *may* exceed max(a,b) only
    if the fused claim is separately certified to beat both baselines."""
    return CompositeBound(
        operator="fusion",
        depends_on=(a.id, b.id),
        confidence_upper=round(min(1.0, a.confidence + b.confidence
                                   - a.confidence * b.confidence), 4),
        energy_mj=_merged_energy(a, b),
        latency_ms=round(max(a.latency_ms, b.latency_ms), 4),
        privacy_score=round(min(a.privacy_score, b.privacy_score), 4),
        valid_until=_min_date(a.valid_until, b.valid_until),
        signals=tuple(sorted(set(a.signals) | set(b.signals))),
    )


def refine(a: CapabilitySpec, b: CapabilitySpec) -> CompositeBound:
    """A ▷ B: B conditions on A's output. Confidence upper-bounded by the product."""
    return CompositeBound(
        operator="refinement",
        depends_on=(a.id, b.id),
        confidence_upper=round(a.confidence * b.confidence, 4),
        energy_mj=round(a.energy_mj + b.energy_mj, 4),
        latency_ms=round(a.latency_ms + b.latency_ms, 4),
        privacy_score=round(min(a.privacy_score, b.privacy_score), 4),
        valid_until=_min_date(a.valid_until, b.valid_until),
        signals=tuple(sorted(set(a.signals) | set(b.signals))),
    )


def temporal_integrate(a: CapabilitySpec, n: int, mixing: float = 1.0) -> CompositeBound:
    """∫ₜ A: aggregate A over n windows. Confidence grows with the measured mixing
    rate (independent samples reduce variance); energy scales with n."""
    eff_n = max(1.0, n * mixing)
    gain = 1.0 - (1.0 - a.confidence) ** eff_n  # optimistic independence bound
    return CompositeBound(
        operator="temporal-integration",
        depends_on=(a.id,),
        confidence_upper=round(min(1.0, gain), 4),
        energy_mj=round(a.energy_mj * n, 4),
        latency_ms=round(a.latency_ms * n, 4),
        privacy_score=a.privacy_score,
        valid_until=a.valid_until,
        signals=a.signals,
    )

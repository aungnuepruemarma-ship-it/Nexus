"""Capability<T> runtime interface and certify(): turn a passed falsification into a
schema-conformant registry entry (docs/architecture.md section 6).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable

from .harness import CertificationResult, ExperimentSpec
from .audit import PrivacyAudit


@dataclass
class Estimate:
    estimate: Any
    confidence: float
    energy_mj: float
    latency_ms: float
    privacy: float
    valid_until: str
    version: str


class Capability:
    """Runtime handle exposing the uniform capability interface.

    ``fn`` maps a feature window -> (estimate, confidence). The wrapper attaches the
    certified cost/expiry metadata so a consumer asks 'is the certification live?'
    rather than 'does it exist?'.
    """
    def __init__(self, cid, fn: Callable, *, energy_mj, latency_ms, privacy,
                 valid_until, version):
        self.id = cid
        self._fn = fn
        self.energy_mj = energy_mj
        self.latency_ms = latency_ms
        self.privacy = privacy
        self.valid_until = valid_until
        self.version = version

    def is_live(self, today: dt.date | None = None) -> bool:
        if not self.valid_until:
            return True
        return dt.date.fromisoformat(self.valid_until) >= (today or dt.date.today())

    def __call__(self, window) -> Estimate:
        est, conf = self._fn(window)
        return Estimate(estimate=est, confidence=conf, energy_mj=self.energy_mj,
                        latency_ms=self.latency_ms, privacy=self.privacy,
                        valid_until=self.valid_until, version=self.version)


def _half_life_to_valid_until(half_life_days: float, today: dt.date) -> str:
    # Certify for one half-life ahead.
    return (today + dt.timedelta(days=int(half_life_days))).isoformat()


def certify(
    cid: str,
    name: str,
    spec: ExperimentSpec,
    result: CertificationResult,
    *,
    signals: list[dict],
    model: dict,
    audit: PrivacyAudit,
    provenance: list[str],
    half_life_days: float,
    description: str,
    generalization: dict | None = None,
    version: str = "1.0.0",
    limitations: list[str] | None = None,
    failure_modes: list[str] | None = None,
    references: list[str] | None = None,
    today: dt.date | None = None,
) -> dict:
    """Build a registry entry from a certification result.

    Status comes straight from the result: ``positive`` when it passed all
    conditions, ``unstable`` when it only transfers on a scoped population,
    ``negative`` when falsified. Negatives carry ``failure_type`` and skip the
    positive-only fields.
    """
    today = today or dt.date.today()
    entry: dict = {
        "id": cid,
        "name": name,
        "status": result.status,
        "version": version,
        "description": description,
        "task": spec.task,
        "signals": signals,
        "date_created": today.isoformat(),
        "last_verified": today.isoformat(),
        "training_protocol": spec.experiment_id,
        "validation_protocol": f"{spec.experiment_id} invariance split (ccs.harness.falsify)",
        "limitations": limitations or [],
        "failure_modes": failure_modes or [],
        "references": references or [],
    }

    if result.status == "negative":
        entry["failure_type"] = result.failure_type or "non-reproducible"
        entry["provenance"] = provenance
        return entry

    # positive / unstable carry full evidence
    m = result.metrics
    entry.update({
        "model": model,
        "accuracy": round(float(m.get("accuracy", 0.0)), 4),
        "confidence": round(float(m.get("accuracy", 0.0)), 4),
        "metrics": {
            "precision": m.get("precision"),
            "recall": m.get("recall"),
            "f1": m.get("f1"),
            "roc_auc": m.get("roc_auc"),
        },
        "energy_mj": result.energy_mj,
        "latency_ms": result.latency_ms,
        "privacy_audit": audit.as_dict(),
        "generalization": generalization or {},
        "provenance": provenance,
        "reproducibility": {"independent_runs": 1, "within_ci": bool(result.reproduced)},
        "valid_until": _half_life_to_valid_until(half_life_days, today),
        "half_life_days": half_life_days,
    })
    if result.status == "unstable" and result.failure_type:
        entry["failure_type"] = result.failure_type
    return entry

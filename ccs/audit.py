"""Dual-use privacy audit (docs/ccs-vision.md section 6).

Every latent capability is, by construction, an inference the hardware designers did
not intend to expose — i.e. a potential side channel. Certification requires an
adversarial audit whose findings ship in the registry entry. This module builds the
audit structure and computes a privacy score at the recommended operating point.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

# Coarse permission tiers for Android-style signals; "none" = permissionless.
PERMISSIONLESS = {
    "none", "", None,
    "battery_temperature", "battery_current", "battery_voltage",
    "skin_temperature", "cpu_temperature", "linear_acceleration",
    "accelerometer", "gyroscope", "gravity", "ambient_light", "barometer",
    "cpu_timing", "loop_timing", "scheduler_jitter",
}


@dataclass
class PrivacyAudit:
    score: float
    bystander_inference: str
    escalation_gradient: str
    permissionless: bool
    mitigations: str
    disclosure_sensitive: bool

    def as_dict(self) -> dict:
        return asdict(self)


def permission_surface(signal_permissions: list[str]) -> bool:
    """True if *every* signal is permissionless (invisible to the consent model)."""
    return all((p in PERMISSIONLESS) for p in signal_permissions)


def audit_capability(
    *,
    signal_permissions: list[str],
    bystander_inference: str,
    escalation_gradient: str,
    mitigations: str,
    escalation_unbounded: bool = False,
    identifies_individuals: bool = False,
) -> PrivacyAudit:
    """Assemble an audit and derive a privacy score in [0,1] (higher = safer).

    The score starts at 1.0 and is penalized by: permissionless operation (the
    inference bypasses consent), unbounded escalation, and individual
    identifiability. ``disclosure_sensitive`` is set when a permissionless capability
    also has unbounded escalation — the case CCS publishes as a *finding* but flags
    rather than shipping as a turnkey recipe.
    """
    permissionless = permission_surface(signal_permissions)
    score = 1.0
    if permissionless:
        score -= 0.3
    if escalation_unbounded:
        score -= 0.3
    if identifies_individuals:
        score -= 0.4
    score = round(max(0.0, min(1.0, score)), 3)
    disclosure_sensitive = bool(permissionless and escalation_unbounded)
    return PrivacyAudit(
        score=score,
        bystander_inference=bystander_inference,
        escalation_gradient=escalation_gradient,
        permissionless=permissionless,
        mitigations=mitigations,
        disclosure_sensitive=disclosure_sensitive,
    )

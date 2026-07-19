"""CCS — Computational Capability Search.

A platform for discovering, falsifying, and cataloging latent computational
capabilities in deployed hardware. See docs/ccs-vision.md for the framing.

The package is organized bottom-up:

    signals      -> raw samples and windowed feature extraction
    metrics      -> accuracy / precision / recall / f1 / roc-auc + cost
    screening    -> mutual-information gate over the signal-subset lattice
    archive      -> immutable session store with provenance hashing
    registry     -> registry.json load/save, status lifecycle, decay propagation
    validator    -> schema + DAG/expiry consistency checks
    composition  -> capability algebra (fusion / refinement / temporal-integration)
    audit        -> dual-use privacy audit
    harness      -> pre-registration, invariance splits, baselines, typed failures
    capability   -> Capability<T> runtime interface + certify()
"""

__version__ = "0.1.0"

"""Sandbox: a deny-by-default permission gate for the autonomous DreamEngine.

Loads ``permissions.yaml`` and answers "may the loop do X?". Everything the engine does with
side effects (writing files, git) is routed through ``ccs.dream.actions.GuardedActions``, which
calls this gate first. If the YAML is missing or a category/action is not listed, the action is
refused — the model never gets unrestricted shell or filesystem access.
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

try:
    import yaml
    _HAVE_YAML = True
except Exception:  # pragma: no cover
    _HAVE_YAML = False

DEFAULT_PERMISSIONS = Path(__file__).with_name("permissions.yaml")


class Sandbox:
    def __init__(self, path: str | Path = DEFAULT_PERMISSIONS):
        self.path = Path(path)
        self.spec = self._load()

    def _load(self) -> dict:
        if _HAVE_YAML and self.path.exists():
            try:
                return yaml.safe_load(self.path.read_text()) or {}
            except Exception:
                pass
        # No policy readable -> deny everything (empty allowlist).
        return {"allowed": {}, "denied": [], "limits": {}}

    @property
    def allowed(self) -> dict:
        return self.spec.get("allowed", {}) or {}

    @property
    def denied(self) -> set:
        return set(self.spec.get("denied", []) or [])

    def allows(self, category: str, action: str) -> bool:
        if action in self.denied:
            return False
        return action in (self.allowed.get(category, []) or [])

    def check(self, category: str, action: str) -> None:
        if not self.allows(category, action):
            raise PermissionError(
                f"action '{action}' in '{category}' is not permitted by {self.path.name}")

    # -- filesystem write scoping -----------------------------------------
    def writable_globs(self) -> list:
        return self.spec.get("limits", {}).get("writable_globs", []) or []

    def can_write(self, relpath: str | Path) -> bool:
        globs = self.writable_globs()
        if not globs:
            return False  # deny-by-default: no writable paths configured => no writes
        rp = str(relpath).replace(os.sep, "/").lstrip("./")
        return any(fnmatch.fnmatch(rp, g) for g in globs)

    def check_write(self, relpath: str | Path) -> None:
        if not self.can_write(relpath):
            raise PermissionError(
                f"write to '{relpath}' is outside the sandbox writable paths")

    def max_commits_per_cycle(self) -> int | None:
        v = self.spec.get("limits", {}).get("max_commits_per_cycle")
        return int(v) if v else None

    def summary(self) -> dict:
        return {"policy": self.path.name,
                "filesystem": self.allowed.get("filesystem", []),
                "git": self.allowed.get("git", []),
                "denied": sorted(self.denied),
                "writable_globs": self.writable_globs()}

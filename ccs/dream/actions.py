"""GuardedActions: every side effect the DreamEngine performs, behind the Sandbox gate.

The engine never writes files or runs git directly — it goes through here, and each method
asks the Sandbox for permission first. A disallowed action raises ``PermissionError`` (writes)
or is refused, so tightening ``permissions.yaml`` immediately constrains the autonomous loop.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .sandbox import Sandbox


class GuardedActions:
    def __init__(self, root: str | Path, sandbox: Sandbox | None = None):
        self.root = Path(root)
        self.sandbox = sandbox or Sandbox()

    # -- filesystem (scoped to writable_globs) ----------------------------
    def write_text(self, relpath: str, text: str) -> Path:
        self.sandbox.check_write(relpath)
        p = self.root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def append_text(self, relpath: str, text: str) -> Path:
        self.sandbox.check_write(relpath)
        p = self.root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(text)
        return p

    # -- git (gated per action) -------------------------------------------
    def _git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True)

    def git_add_all(self) -> None:
        self.sandbox.check("git", "git_add")
        self._git("add", "-A")

    def git_commit(self, message: str) -> bool:
        self.sandbox.check("git", "git_commit")
        return self._git("commit", "-m", message).returncode == 0

    def git_push(self, branch: str) -> bool:
        self.sandbox.check("git", "git_push")
        return self._git("push", "origin", branch).returncode == 0

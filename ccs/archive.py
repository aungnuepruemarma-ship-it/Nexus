"""Immutable physical-state archive with provenance hashing.

Sessions are append-only. Registry entries cite archive content by sha256 hash;
editing the archive would silently invalidate certifications, so writes refuse to
overwrite an existing session (docs/architecture.md section 3).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .signals import Signal


def _hash_bytes(*chunks: bytes) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c)
    return "sha256:" + h.hexdigest()[:16]


@dataclass
class Session:
    device_id: str
    signals: list[Signal]
    metadata: dict

    def content_hash(self) -> str:
        chunks = []
        for s in sorted(self.signals, key=lambda x: x.name):
            chunks.append(s.name.encode())
            chunks.append(s.t_ns.tobytes())
            chunks.append(np.ascontiguousarray(s.value).tobytes())
        return _hash_bytes(*chunks)


class Archive:
    """A directory-backed, append-only archive of sessions."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def session_dir(self, device_id: str, session_id: str) -> Path:
        return self.root / device_id / session_id

    def write(self, session_id: str, session: Session, allow_existing: bool = False) -> str:
        d = self.session_dir(session.device_id, session_id)
        if d.exists() and not allow_existing:
            raise FileExistsError(f"archive is append-only; {d} already exists")
        d.mkdir(parents=True, exist_ok=True)
        for s in session.signals:
            cols = {"t_ns": s.t_ns}
            for ax in range(s.n_axes):
                cols[f"v{ax}"] = s.value[:, ax]
            df = pd.DataFrame(cols)
            try:
                df.to_parquet(d / f"{s.name}.parquet", index=False)
            except Exception:
                df.to_csv(d / f"{s.name}.csv", index=False)
        h = session.content_hash()
        meta = dict(session.metadata)
        meta.update({"device_id": session.device_id,
                     "session_id": session_id,
                     "hash": h,
                     "signals": [s.name for s in session.signals]})
        (d / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
        return h

    def list_sessions(self) -> list[tuple[str, str]]:
        out = []
        for dev in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for ses in sorted(p for p in dev.iterdir() if p.is_dir()):
                out.append((dev.name, ses.name))
        return out

    def read_metadata(self, device_id: str, session_id: str) -> dict:
        return json.loads((self.session_dir(device_id, session_id) / "metadata.json").read_text())

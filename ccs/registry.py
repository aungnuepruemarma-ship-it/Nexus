"""The capability registry: a DAG of capability claims with a decay lifecycle.

Entries are stored as JSON conforming to registry/capability.schema.json. The
registry adds behavior on top of storage (docs/ccs-vision.md sections 5, 7):

  * status lifecycle: experimental -> positive -> unstable -> deprecated; negative
  * decay-watch: entries expire at ``valid_until``; expired atoms demote dependents
  * composition DAG: ``depends_on`` edges; ``valid_until`` of a composite is the min
    over its dependencies (expiry propagates upward).
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

STATUSES = ("positive", "negative", "unstable", "deprecated", "experimental")


def _today() -> dt.date:
    return dt.date.today()


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    return dt.date.fromisoformat(s)


@dataclass
class Registry:
    entries: dict[str, dict]

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        p = Path(path)
        if not p.exists():
            return cls(entries={})
        data = json.loads(p.read_text())
        if isinstance(data, list):
            data = {e["id"]: e for e in data}
        return cls(entries=data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.entries, indent=2, sort_keys=True))

    # -- basic ops ----------------------------------------------------------
    def add(self, entry: dict) -> None:
        self.entries[entry["id"]] = entry

    def get(self, cid: str) -> dict:
        return self.entries[cid]

    def by_status(self, status: str) -> list[dict]:
        return [e for e in self.entries.values() if e.get("status") == status]

    # -- DAG ----------------------------------------------------------------
    def dependents(self, cid: str) -> list[str]:
        return [e["id"] for e in self.entries.values()
                if cid in (e.get("depends_on") or [])]

    def has_cycle(self) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {cid: WHITE for cid in self.entries}

        def visit(u: str) -> bool:
            color[u] = GRAY
            for v in (self.entries[u].get("depends_on") or []):
                if v not in color:
                    continue
                if color[v] == GRAY:
                    return True
                if color[v] == WHITE and visit(v):
                    return True
            color[u] = BLACK
            return False

        return any(color[c] == WHITE and visit(c) for c in list(self.entries))

    def decay_cut_set(self, cid: str) -> list[str]:
        """Atoms whose expiry would take ``cid`` down (its transitive dependencies)."""
        seen: set[str] = set()
        stack = list(self.entries.get(cid, {}).get("depends_on") or [])
        while stack:
            d = stack.pop()
            if d in seen or d not in self.entries:
                continue
            seen.add(d)
            stack.extend(self.entries[d].get("depends_on") or [])
        return sorted(seen)

    # -- decay lifecycle ----------------------------------------------------
    def propagate_expiry(self, today: dt.date | None = None) -> list[dict]:
        """Apply decay-watch. Returns a log of transitions made.

        Rules:
          * a positive/unstable entry past ``valid_until`` -> ``unstable`` (needs
            re-verification) and a decay event is logged;
          * a composite's effective ``valid_until`` is the min over dependencies;
            if any dependency is expired/negative the composite is demoted to
            ``unstable`` (supply-chain recall semantics).
        """
        today = today or _today()
        log: list[dict] = []

        # First pass: expire atoms whose own valid_until has passed.
        for e in self.entries.values():
            if e.get("status") in ("positive", "unstable"):
                vu = _parse_date(e.get("valid_until"))
                if vu is not None and vu < today and e.get("status") == "positive":
                    e["status"] = "unstable"
                    log.append({"id": e["id"], "event": "expired",
                                "reason": f"valid_until {e['valid_until']} < {today}"})

        # Second pass: propagate min-expiry + dependency demotion through the DAG.
        changed = True
        while changed:
            changed = False
            for e in self.entries.values():
                deps = e.get("depends_on") or []
                if not deps:
                    continue
                dep_dates = []
                for d in deps:
                    dep = self.entries.get(d)
                    if dep is None:
                        continue
                    if dep.get("status") in ("negative", "deprecated"):
                        if e.get("status") == "positive":
                            e["status"] = "unstable"
                            log.append({"id": e["id"], "event": "dependency_failed",
                                        "reason": f"depends_on {d} is {dep['status']}"})
                            changed = True
                    vu = _parse_date(dep.get("valid_until"))
                    if vu is not None:
                        dep_dates.append(vu)
                if dep_dates:
                    new_vu = min(dep_dates).isoformat()
                    own_vu = _parse_date(e.get("valid_until"))
                    if own_vu is None or min(dep_dates) < own_vu:
                        if e.get("valid_until") != new_vu:
                            e["valid_until"] = new_vu
                            changed = True
        return log

    def summary(self) -> dict:
        counts = {s: len(self.by_status(s)) for s in STATUSES}
        counts["total"] = len(self.entries)
        counts["has_cycle"] = self.has_cycle()
        return counts

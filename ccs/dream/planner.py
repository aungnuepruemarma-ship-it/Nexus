"""Research Planner: decide what the loop should work on next, and why.

Instead of walking a fixed backlog top-to-bottom, the planner scores candidate experiments and
orders them. It draws from three sources — never-attempted backlog laws, dated certifications
that are about to lapse (re-verify), and freshly *generated* experiments that fill gaps in the
Memory Graph — and boosts under-represented signal families so the loop broadens its coverage.
Output is an explainable plan (each item carries a priority and a reason), the bridge from
"autonomous runner" toward a system that chooses its own research direction.
"""
from __future__ import annotations

import datetime as dt

from ccs.registry import Registry
from .generator import ExperimentGenerator
from .memory_graph import MemoryGraph


class ResearchPlanner:
    def __init__(self, engine, generator: ExperimentGenerator | None = None,
                 refresh_within_days: int = 21):
        self.engine = engine
        self.generator = generator or ExperimentGenerator(model=getattr(engine, "model", None))
        self.refresh_within_days = refresh_within_days

    def plan(self, max_items: int = 10) -> list[dict]:
        reg = (Registry.load(self.engine.registry_path)
               if self.engine.registry_path.exists() else Registry(entries={}))
        known = set(reg.entries)
        graph = MemoryGraph.from_registry(reg.entries)
        fam_counts = graph.families()
        fam_min = min(fam_counts.values()) if fam_counts else 0

        def fam_boost(dream) -> float:
            # a generated/backlog dream in a scarce family is worth more (broaden coverage)
            fam = getattr(dream, "topic", "")
            return 0.5 if fam and fam_min == 0 else 0.0

        items: list[dict] = []

        # 1) never-attempted / lapsed backlog laws (highest priority)
        for d in self.engine.pending():
            items.append({"id": d.id, "dream": d, "source": "backlog",
                          "priority": round(3.0 + fam_boost(d), 3),
                          "reason": "uncertified or lapsed backlog law"})

        # 2) certified-but-soon-expiring backlog laws -> refresh
        today = dt.date.today()
        soon = (today + dt.timedelta(days=self.refresh_within_days)).isoformat()
        pending_ids = {d.id for d in self.engine.pending()}
        for d in self.engine.backlog:
            e = reg.entries.get(d.id)
            if e and d.id not in pending_ids and e.get("valid_until") and e["valid_until"] <= soon:
                items.append({"id": d.id, "dream": d, "source": "refresh",
                              "priority": 2.0, "reason": f"certification lapses by {e['valid_until']}"})

        # 3) generated experiments that fill graph gaps
        for d in self.generator.propose(known, n=4):
            items.append({"id": d.id, "dream": d, "source": "generated",
                          "priority": round(1.0 + fam_boost(d), 3),
                          "reason": "generated parameter point not yet in registry"})

        items.sort(key=lambda it: -it["priority"])
        return items[:max_items]

    def summary(self, max_items: int = 10) -> list[dict]:
        return [{"id": it["id"], "priority": it["priority"],
                 "source": it["source"], "reason": it["reason"]}
                for it in self.plan(max_items)]

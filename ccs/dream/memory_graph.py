"""Scientific Memory Graph: the registry as a graph of capabilities and their relationships.

Nodes are certified (and falsified) capabilities; edges capture how they relate:
  * ``shares_signal`` — two capabilities read the same signal family (cpu/memory/…),
  * ``depends_on``    — composition edges (a composite built on an atom),
  * ``shares_reference`` — they cite the same source/experiment.

This gives the planner a map of what has been explored and where the gaps are, and it makes
the loop's accumulated knowledge queryable ("what relates to the memory hierarchy?") instead
of a flat list. Built purely from the registry — no extra measurement.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path


class MemoryGraph:
    def __init__(self, nodes: dict, edges: list):
        self.nodes = nodes            # id -> {status, family, task}
        self.edges = edges            # list of (a, b, kind)

    @classmethod
    def from_registry(cls, entries: dict) -> "MemoryGraph":
        nodes = {}
        for cid, e in entries.items():
            fams = sorted({s.get("family") for s in e.get("signals", []) if s.get("family")})
            nodes[cid] = {"status": e.get("status"), "families": fams, "task": e.get("task", "")}
        edges = []
        ids = list(entries)
        # depends_on (composition)
        for cid, e in entries.items():
            for dep in e.get("depends_on", []) or []:
                if dep in entries:
                    edges.append((cid, dep, "depends_on"))
        # shares_signal (same family) + shares_reference
        for a, b in itertools.combinations(ids, 2):
            fa, fb = set(nodes[a]["families"]), set(nodes[b]["families"])
            if fa & fb:
                edges.append((a, b, "shares_signal"))
            ra = set(entries[a].get("references", []) or [])
            rb = set(entries[b].get("references", []) or [])
            if ra & rb:
                edges.append((a, b, "shares_reference"))
        return cls(nodes, edges)

    def neighbors(self, cid: str) -> list:
        out = []
        for a, b, kind in self.edges:
            if a == cid:
                out.append((b, kind))
            elif b == cid:
                out.append((a, kind))
        return out

    def families(self) -> dict:
        counts: dict[str, int] = {}
        for n in self.nodes.values():
            for f in n["families"]:
                counts[f] = counts.get(f, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict:
        return {"n_nodes": len(self.nodes), "n_edges": len(self.edges),
                "families": self.families(),
                "nodes": self.nodes,
                "edges": [{"a": a, "b": b, "kind": k} for a, b, k in self.edges]}

    def to_mermaid(self) -> str:
        style = {"positive": ":::pos", "negative": ":::neg",
                 "unstable": ":::unst", "experimental": ":::exp"}
        lines = ["graph TD"]
        for cid, n in self.nodes.items():
            lines.append(f'  {cid}["{cid}"]{style.get(n["status"], "")}')
        arrow = {"depends_on": "-->|depends|", "shares_signal": "-.->|signal|",
                 "shares_reference": "-.->|ref|"}
        seen = set()
        for a, b, k in self.edges:
            key = (a, b, k)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {a} {arrow.get(k, '---')} {b}")
        lines += ["classDef pos fill:#1b5e20,color:#fff;",
                  "classDef neg fill:#7f1d1d,color:#fff;",
                  "classDef unst fill:#8a6d00,color:#fff;",
                  "classDef exp fill:#1e3a5f,color:#fff;"]
        return "\n".join(lines)

    def save(self, root: Path) -> None:
        (Path(root) / "results" / "memory_graph.json").write_text(json.dumps(self.to_dict(), indent=2))
        (Path(root) / "results" / "memory_graph.mmd").write_text(self.to_mermaid())

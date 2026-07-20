"""The full research program — generator + memory graph + causal + planner + reviewer.

One command runs the whole scientist:
  1. build the Scientific Memory Graph from the registry,
  2. run Causal Discovery (associational skeleton) on real measured features,
  3. have the Research Planner choose what to work on (backlog / refresh / generated),
  4. execute the top items through the DreamEngine, where the Multi-agent Reviewer gates
     certification, and commit what survives.

    python scripts/research_program.py --iterations 1
    python scripts/research_program.py --no-commit --no-causal     # inspect the plan only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ccs.registry import Registry
from ccs.dream import (LocalModel, WebBrowser, DreamEngine, ExperimentGenerator,
                       MemoryGraph, ResearchPlanner, ReviewPanel, causal)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Nexus autonomous research program")
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--no-model", action="store_true")
    ap.add_argument("--no-causal", action="store_true")
    args = ap.parse_args()

    model = LocalModel(enabled=not args.no_model)
    web = WebBrowser()
    reviewer = ReviewPanel(model=model)
    generator = ExperimentGenerator(model=model)
    engine = DreamEngine(model=model, web=web, do_commit=not args.no_commit, reviewer=reviewer)
    print(f"[research] model={model.info()['available']} sandbox={engine.sandbox.summary()['git']}", flush=True)

    # 1. Scientific Memory Graph
    reg = Registry.load(engine.registry_path)
    graph = MemoryGraph.from_registry(reg.entries)
    graph.save(ROOT)
    gd = graph.to_dict()
    print(f"[research] memory graph: {gd['n_nodes']} nodes, {gd['n_edges']} edges; families {graph.families()}",
          flush=True)

    # 2. Causal Discovery on real features
    if not args.no_causal:
        skel = causal.discover_from_workload(n_windows=40)
        (ROOT / "results" / "causal_skeleton.json").write_text(json.dumps(skel, indent=2))
        print(f"[research] causal skeleton: {skel['n_direct_edges']} direct edges, "
              f"{skel['n_mediated_pairs']} mediated pairs over {skel['n_vars']} signals", flush=True)
        for e in skel["direct_edges"][:3]:
            print(f"    direct: {e['a']} — {e['b']}  (partial {e['partial']}, marginal {e['marginal']})")

    # 3. Research Planner
    planner = ResearchPlanner(engine, generator)
    plan = planner.plan(max_items=args.iterations + 4)
    (ROOT / "results" / "research_plan.json").write_text(json.dumps(planner.summary(20), indent=2))
    print("[research] plan (top 5):", flush=True)
    for it in plan[:5]:
        print(f"    [{it['priority']:>4}] {it['id']} <{it['source']}> — {it['reason']}")

    # 4. Execute top items through the engine (run -> review -> certify -> commit)
    executed = []
    for it in plan[:args.iterations]:
        s = engine.step(it["dream"])
        executed.append({"id": s["dream"], "status": s.get("status"),
                         "review": s.get("review"), "committed": s.get("committed")})
        print(f"[research] {s['dream']}: status={s.get('status')} "
              f"review={s.get('review')} committed={s.get('committed')}", flush=True)

    print("\n[research] done.", json.dumps({"executed": executed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Autonomous discovery loop — the Hardware Dreaming Engine / Automated Computer Scientist.

Runs the DreamEngine: a small local open-source model proposes hypotheses, a web-browsing
ability fetches context, and each pending "law of this machine" is measured on real hardware,
certified through the falsification harness, written to the registry + discovery log, and
committed to git — with no human in the loop.

    python scripts/dream_loop.py                # work the whole pending backlog, commit each
    python scripts/dream_loop.py --iterations 1 # a single discovery
    python scripts/dream_loop.py --no-commit    # dry run (no git commits)
    python scripts/dream_loop.py --no-model     # skip the LLM (heuristic hypotheses)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ccs.dream import DreamEngine, LocalModel, WebBrowser


def main() -> int:
    ap = argparse.ArgumentParser(description="Nexus autonomous hardware-discovery loop")
    ap.add_argument("--iterations", type=int, default=None,
                    help="max discoveries this run (default: whole pending backlog)")
    ap.add_argument("--no-commit", action="store_true", help="do not git-commit each discovery")
    ap.add_argument("--no-model", action="store_true", help="skip the local LLM")
    ap.add_argument("--no-web", action="store_true", help="skip the web-browsing ability")
    args = ap.parse_args()

    print("[dream] booting the Automated Computer Scientist ...", flush=True)
    model = LocalModel(enabled=not args.no_model)
    web = WebBrowser(enabled=not args.no_web)
    print(f"[dream] model: {model.info()}", flush=True)
    print(f"[dream] web: {'online' if (web.enabled and web.online()) else 'offline/disabled'}", flush=True)

    engine = DreamEngine(model=model, web=web, do_commit=not args.no_commit)
    print(f"[dream] sandbox: {engine.sandbox.summary()}", flush=True)
    pending = engine.pending()
    print(f"[dream] pending capabilities: {[d.id for d in pending] or 'none (registry current)'}",
          flush=True)

    summaries = engine.run(iterations=args.iterations)
    for s in summaries:
        print(f"\n[dream] {s['dream']}: {s['status']}"
              + (f" (score {s['accuracy']})" if s.get("accuracy") is not None else "")
              + f"  committed={s.get('committed')}")
        print(f"        hypothesis: {s['hypothesis'][:200]}")
        if s.get("web_context"):
            print(f"        web: {s['web_context'][:120]}")
    print(f"\n[dream] done — {len(summaries)} discovery iteration(s).")
    print(json.dumps({"iterations": len(summaries),
                      "statuses": {s["dream"]: s["status"] for s in summaries}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

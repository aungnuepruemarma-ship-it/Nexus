"""DreamEngine: the autonomous Automated-Computer-Scientist loop.

Each iteration: pick a pending capability, have the local model state the hypothesis, use the
web ability to fetch outside context (best-effort), run the REAL experiment on this hardware,
certify it through the existing harness/validator, merge the honest verdict into the registry,
append to the machine-written discovery log, and commit the update to git. The loop drives the
platform toward its backlog of "laws of this machine" with no human in the loop.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ccs.registry import Registry
from ccs.validator import validate_registry

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Dream:
    """One pending capability the engine can try to discover and certify."""
    id: str                       # capability id it produces
    title: str
    experiment_id: str            # manifest key
    result_file: str              # results/<file>.json
    run: Callable[[], tuple]      # () -> (result_dict, entry_dict)
    prompt: str                   # hypothesis question posed to the model


def default_backlog() -> list[Dream]:
    """The standing backlog of self-experiments (imported lazily to keep the package light)."""
    from experiments.exp_hw_timer_resolution import run as run_timer
    from experiments.exp_hw_membw import run as run_membw
    from experiments.exp_hw_cache_ladder import run as run_cache
    return [
        Dream("timer_resolution_v1", "Effective clock resolution", "EXP-HW-TIMER-RES",
              "exp_hw_timer_resolution.json", run_timer,
              "In one sentence: what hidden 'law' does the smallest gap between two back-to-back "
              "clock reads reveal about a CPU?"),
        Dream("mem_bandwidth_v1", "Streaming memory bandwidth", "EXP-HW-MEMBW",
              "exp_hw_membw.json", run_membw,
              "In one sentence: why does timing a read-modify-write over a buffer larger than "
              "cache reveal the machine's true memory bandwidth?"),
        Dream("memory_hierarchy_v1", "Cache/DRAM hierarchy", "EXP-HW-CACHE-LADDER",
              "exp_hw_cache_ladder.json", run_cache,
              "In one sentence: how does pointer-chase latency vs working-set size expose where "
              "a CPU's caches end?"),
    ]


class DreamEngine:
    def __init__(self, root: Path = ROOT, model=None, web=None, do_commit: bool = True,
                 backlog: list[Dream] | None = None):
        self.root = Path(root)
        self.results = self.root / "results"
        self.registry_path = self.root / "registry" / "registry.json"
        self.manifest_path = self.results / "manifest.json"
        self.log_path = self.results / "DREAM_LOG.md"
        self.model = model
        self.web = web
        self.do_commit = do_commit
        self.backlog = backlog if backlog is not None else default_backlog()

    # -- selection ---------------------------------------------------------
    def pending(self) -> list[Dream]:
        reg = Registry.load(self.registry_path) if self.registry_path.exists() else Registry(entries={})
        today = dt.date.today()
        out = []
        for d in self.backlog:
            e = reg.entries.get(d.id)
            live = e and e.get("valid_until") and e["valid_until"] >= today.isoformat()
            if not live:
                out.append(d)
        return out

    # -- one autonomous iteration -----------------------------------------
    def step(self, dream: Dream) -> dict:
        hypothesis = self._hypothesize(dream)
        context = self._lookup(dream)

        result, entry = dream.run()   # REAL measurement on this hardware

        reg = Registry.load(self.registry_path) if self.registry_path.exists() else Registry(entries={})
        reg.add(entry)
        reg.propagate_expiry()
        reg.save(self.registry_path)
        validation = validate_registry(reg)

        (self.results / dream.result_file).write_text(json.dumps(result, indent=2, default=list))
        self._update_manifest(dream, result, reg, validation)
        self._append_log(dream, entry, result, hypothesis, context)

        summary = {
            "dream": dream.id, "status": entry.get("status"),
            "accuracy": entry.get("accuracy"), "registry_valid": validation["ok"],
            "hypothesis": hypothesis, "web_context": context.get("summary"),
        }
        if self.do_commit:
            summary["committed"] = self._commit(dream, entry, hypothesis)
        return summary

    def run(self, iterations: int | None = None) -> list[dict]:
        todo = self.pending()
        if iterations is not None:
            todo = todo[:iterations]
        return [self.step(d) for d in todo]

    # -- helpers -----------------------------------------------------------
    def _hypothesize(self, dream: Dream) -> str:
        if self.model is None:
            return f"[no model] investigate: {dream.title}"
        try:
            return self.model.chat(
                dream.prompt,
                system="You are a hardware-discovery scientist. Answer in one concise sentence.")
        except Exception as e:
            return f"[model error] {type(e).__name__}"

    def _lookup(self, dream: Dream) -> dict:
        if self.web is None:
            return {"summary": None}
        res = self.web.search(f"{dream.title} CPU microbenchmark")
        if res.get("ok") and res.get("results"):
            return {"summary": res["results"][0], "results": res["results"]}
        return {"summary": None, "error": res.get("error")}

    def _update_manifest(self, dream: Dream, result: dict, reg: Registry, validation: dict) -> None:
        man = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {"experiments": {}}
        man.setdefault("experiments", {})[dream.experiment_id] = result
        man["registry_summary"] = reg.summary()
        man["registry_valid"] = validation["ok"]
        man["registry_errors"] = validation
        man["decay_cut_sets"] = {cid: reg.decay_cut_set(cid) for cid in reg.entries
                                 if reg.entries[cid].get("depends_on")}
        self.manifest_path.write_text(json.dumps(man, indent=2, default=list))

    def _append_log(self, dream: Dream, entry: dict, result: dict, hypothesis: str, context: dict) -> None:
        if not self.log_path.exists():
            self.log_path.write_text(
                "# Nexus Dream Log — autonomous hardware discoveries\n\n"
                "Machine-written by `ccs.dream.DreamEngine`. Each entry is one self-experiment: "
                "a hypothesis (local model), optional web context, and the certified verdict.\n")
        ts = dt.datetime.now().isoformat(timespec="seconds")
        ctx = context.get("summary")
        lines = [
            f"\n## {dream.id} — {entry.get('status', '?').upper()}  ({ts})",
            f"- **Hypothesis (model):** {hypothesis}",
        ]
        if ctx:
            lines.append(f"- **Web context:** {ctx}")
        acc = entry.get("accuracy")
        lines.append(f"- **Verdict:** `{entry.get('status')}`"
                     + (f", score {acc}" if acc is not None else "")
                     + f" — {dream.title}. Schema-valid: {result.get('entry_valid')}.")
        with self.log_path.open("a") as f:
            f.write("\n".join(lines) + "\n")

    def _commit(self, dream: Dream, entry: dict, hypothesis: str) -> bool:
        msg = (
            f"dream: certify {dream.id} ({entry.get('status')}) — autonomous discovery\n\n"
            f"Hypothesis (local model): {hypothesis[:300]}\n"
            f"Verdict: {entry.get('status')} on {dream.title}, measured on this host.\n\n"
            "Committed automatically by ccs.dream.DreamEngine (Automated Computer Scientist loop).\n\n"
            "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_018KzWidWCVabrrJEUwcEh5P\n")
        try:
            subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True,
                           capture_output=True, text=True)
            r = subprocess.run(["git", "-C", str(self.root), "commit", "-m", msg],
                               capture_output=True, text=True)
            return r.returncode == 0
        except Exception:
            return False

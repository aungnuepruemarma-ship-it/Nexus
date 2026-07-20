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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ccs.registry import Registry
from ccs.validator import validate_registry
from .sandbox import Sandbox
from .actions import GuardedActions

ROOT = Path(__file__).resolve().parents[2]

# The standing mission the local model pursues every cycle — the Automated Computer
# Scientist's goal, in its own words. Framed into the model's system prompt and logged.
MISSION = (
    "Discover the hidden laws of THIS machine — measurable, reproducible facts about its "
    "CPU, memory, cache, clock and OS that no spec sheet states — hypothesize each, let it be "
    "measured on real hardware, certify only what survives falsification, and keep building "
    "and committing new laws to the registry, forever."
)


@dataclass
class Dream:
    """One pending capability the engine can try to discover and certify."""
    id: str                       # capability id it produces
    title: str
    experiment_id: str            # manifest key
    result_file: str              # results/<file>.json
    run: Callable[[], tuple]      # () -> (result_dict, entry_dict)
    prompt: str                   # hypothesis question posed to the model
    topic: str = ""               # Wikipedia topic for the web-context lookup


def default_backlog() -> list[Dream]:
    """The standing backlog of self-experiments (imported lazily to keep the package light)."""
    from experiments.exp_hw_timer_resolution import run as run_timer
    from experiments.exp_hw_membw import run as run_membw
    from experiments.exp_hw_cache_ladder import run as run_cache
    from experiments.exp_hw_syscall import run as run_syscall
    from experiments.exp_hw_flops import run as run_flops
    from experiments.exp_hw_mempattern import run as run_mempattern
    from experiments.exp_meta_loop_health import run as run_health
    return [
        Dream("memory_access_penalty_v1", "Random vs sequential access penalty", "EXP-HW-MEMPATTERN",
              "exp_hw_mempattern.json", run_mempattern,
              "In one sentence: why is touching the same bytes in random order so much slower "
              "than in sequential order on a real CPU?", topic="CPU cache"),
        Dream("experiment_loop_health_v1", "Discovery-loop health (self-monitoring)", "EXP-META-LOOPHEALTH",
              "exp_meta_loop_health.json", run_health,
              "In one sentence: what does an autonomous research loop learn by measuring its own "
              "experiment count, success rate and commit cadence?", topic="Scientific method"),
        Dream("flops_throughput_v1", "Sustained FP throughput", "EXP-HW-FLOPS",
              "exp_hw_flops.json", run_flops,
              "In one sentence: what does timing a streamed multiply-add over large arrays "
              "reveal about a CPU's real floating-point throughput?", topic="FLOPS"),
        Dream("syscall_latency_v1", "System-call round-trip cost", "EXP-HW-SYSCALL",
              "exp_hw_syscall.json", run_syscall,
              "In one sentence: what does timing a bare syscall back-to-back reveal about the "
              "cost of crossing from user space into the kernel?", topic="System call"),
        Dream("timer_resolution_v1", "Effective clock resolution", "EXP-HW-TIMER-RES",
              "exp_hw_timer_resolution.json", run_timer,
              "In one sentence: what hidden 'law' does the smallest gap between two back-to-back "
              "clock reads reveal about a CPU?", topic="Clock signal"),
        Dream("mem_bandwidth_v1", "Streaming memory bandwidth", "EXP-HW-MEMBW",
              "exp_hw_membw.json", run_membw,
              "In one sentence: why does timing a read-modify-write over a buffer larger than "
              "cache reveal the machine's true memory bandwidth?", topic="Memory bandwidth"),
        Dream("memory_hierarchy_v1", "Cache/DRAM hierarchy", "EXP-HW-CACHE-LADDER",
              "exp_hw_cache_ladder.json", run_cache,
              "In one sentence: how does pointer-chase latency vs working-set size expose where "
              "a CPU's caches end?", topic="CPU cache"),
    ]


class DreamEngine:
    def __init__(self, root: Path = ROOT, model=None, web=None, do_commit: bool = True,
                 backlog: list[Dream] | None = None, sandbox: Sandbox | None = None,
                 reviewer=None):
        self.root = Path(root)
        self.results = self.root / "results"
        self.registry_path = self.root / "registry" / "registry.json"
        self.manifest_path = self.results / "manifest.json"
        self.log_path = self.results / "DREAM_LOG.md"
        self.model = model
        self.web = web
        self.do_commit = do_commit
        self.backlog = backlog if backlog is not None else default_backlog()
        self.sandbox = sandbox or Sandbox()
        self.actions = GuardedActions(self.root, self.sandbox)
        self.reviewer = reviewer

    # -- selection ---------------------------------------------------------
    def pending(self) -> list[Dream]:
        reg = Registry.load(self.registry_path) if self.registry_path.exists() else Registry(entries={})
        today = dt.date.today().isoformat()
        out = []
        for d in self.backlog:
            e = reg.entries.get(d.id)
            expired = bool(e and e.get("valid_until") and e["valid_until"] < today)
            # pending iff never attempted, or a dated certification has lapsed (needs re-verify);
            # a terminal entry (e.g. a negative with no valid_until) counts as concluded.
            if e is None or expired:
                out.append(d)
        return out

    # -- one autonomous iteration -----------------------------------------
    def step(self, dream: Dream) -> dict:
        hypothesis = self._hypothesize(dream)
        context = self._lookup(dream)

        result, entry = dream.run()   # REAL measurement on this hardware

        # multi-agent review gate: a blocking finding stops certification.
        review = self.reviewer.review(entry, result) if self.reviewer else None
        record = {**result, "review": review} if review else result
        if review and not review["approved"]:
            self.actions.write_text(f"results/{dream.result_file}",
                                    json.dumps(record, indent=2, default=list))
            self._append_log(dream, entry, record, hypothesis, context, rejected=review)
            return {"dream": dream.id, "status": "rejected", "review": review,
                    "hypothesis": hypothesis, "web_context": context.get("summary")}

        reg = Registry.load(self.registry_path) if self.registry_path.exists() else Registry(entries={})
        reg.add(entry)
        reg.propagate_expiry()
        reg.save(self.registry_path)
        validation = validate_registry(reg)

        self.actions.write_text(f"results/{dream.result_file}",
                                json.dumps(record, indent=2, default=list))
        self._update_manifest(dream, result, reg, validation)
        self._append_log(dream, entry, result, hypothesis, context)

        summary = {
            "dream": dream.id, "status": entry.get("status"),
            "accuracy": entry.get("accuracy"), "registry_valid": validation["ok"],
            "hypothesis": hypothesis, "web_context": context.get("summary"),
            "review": review["verdict"] if review else None,
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
                system=f"You are a hardware-discovery scientist. Your mission: {MISSION} "
                       "Answer in one concise sentence.")
        except Exception as e:
            return f"[model error] {type(e).__name__}"

    def _lookup(self, dream: Dream) -> dict:
        if self.web is None:
            return {"summary": None}
        if dream.topic:
            wiki = self.web.wiki(dream.topic)
            if wiki.get("ok"):
                return {"summary": wiki["extract"][:280], "source": f"wikipedia:{wiki.get('title')}"}
        res = self.web.search(f"{dream.title} CPU microbenchmark")
        if res.get("ok") and res.get("results"):
            return {"summary": res["results"][0], "source": "duckduckgo"}
        return {"summary": None, "error": res.get("error")}

    def _update_manifest(self, dream: Dream, result: dict, reg: Registry, validation: dict) -> None:
        man = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {"experiments": {}}
        man.setdefault("experiments", {})[dream.experiment_id] = result
        man["registry_summary"] = reg.summary()
        man["registry_valid"] = validation["ok"]
        man["registry_errors"] = validation
        man["decay_cut_sets"] = {cid: reg.decay_cut_set(cid) for cid in reg.entries
                                 if reg.entries[cid].get("depends_on")}
        self.actions.write_text("results/manifest.json", json.dumps(man, indent=2, default=list))

    def _append_log(self, dream: Dream, entry: dict, result: dict, hypothesis: str,
                    context: dict, rejected: dict | None = None) -> None:
        if not self.log_path.exists():
            self.actions.write_text(
                "results/DREAM_LOG.md",
                "# Nexus Dream Log — autonomous hardware discoveries\n\n"
                "Machine-written by `ccs.dream.DreamEngine`. Each entry is one self-experiment: "
                "a hypothesis (local model), optional web context, and the certified verdict.\n")
        ts = dt.datetime.now().isoformat(timespec="seconds")
        ctx = context.get("summary")
        head = "REJECTED" if rejected else entry.get("status", "?").upper()
        lines = [
            f"\n## {dream.id} — {head}  ({ts})",
            f"- **Hypothesis (model):** {hypothesis}",
        ]
        if ctx:
            lines.append(f"- **Web context:** {ctx}")
        if rejected:
            lines.append(f"- **Review:** `{rejected['verdict']}` — blocked by {rejected['blockers']}; "
                         "not certified.")
        else:
            acc = entry.get("accuracy")
            lines.append(f"- **Verdict:** `{entry.get('status')}`"
                         + (f", score {acc}" if acc is not None else "")
                         + f" — {dream.title}. Schema-valid: {result.get('entry_valid')}.")
        self.actions.append_text("results/DREAM_LOG.md", "\n".join(lines) + "\n")

    def _commit(self, dream: Dream, entry: dict, hypothesis: str) -> bool:
        msg = (
            f"dream: certify {dream.id} ({entry.get('status')}) — autonomous discovery\n\n"
            f"Hypothesis (local model): {hypothesis[:300]}\n"
            f"Verdict: {entry.get('status')} on {dream.title}, measured on this host.\n\n"
            "Committed automatically by ccs.dream.DreamEngine (Automated Computer Scientist loop).\n\n"
            "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_018KzWidWCVabrrJEUwcEh5P\n")
        try:
            self.actions.git_add_all()     # gated by Sandbox: git_add
            return self.actions.git_commit(msg)   # gated by Sandbox: git_commit
        except PermissionError:
            # policy forbids git here — the discovery is still written to disk, just not committed
            return False
        except Exception:
            return False

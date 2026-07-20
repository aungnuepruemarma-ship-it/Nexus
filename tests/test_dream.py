"""Tests for the Dream layer (Automated Computer Scientist) and the new law experiments.

Hermetic and fast: the local LLM and network are NOT exercised (the model-disabled and
web-disabled degrade paths are). The engine is driven against a temp repo with an injected
dream so no real registry/git state is touched. The new hardware experiments run with tiny
sample sizes just to confirm they produce schema-valid entries."""
import numpy as np

from ccs.dream.model import LocalModel
from ccs.dream.web import WebBrowser, _strip_html
from ccs.dream.engine import DreamEngine, Dream
from ccs.validator import validate_entry


def test_local_model_degrades_gracefully():
    m = LocalModel(enabled=False)
    assert m.available is False
    assert m.chat("propose something").startswith("[heuristic]")
    assert m.info()["available"] is False


def test_web_disabled_is_safe():
    w = WebBrowser(enabled=False)
    assert w.fetch("https://example.com")["ok"] is False
    assert w.search("q")["ok"] is False
    assert w.wiki("CPU cache")["ok"] is False


def test_strip_html():
    assert _strip_html("<p>Hello&nbsp;<b>world</b></p>") == "Hello world"


def _fake_entry():
    return {
        "id": "fake_probe_v1", "name": "Fake", "status": "negative", "version": "1.0.0",
        "description": "synthetic entry for engine test", "task": "t",
        "signals": [{"family": "cpu", "name": "clock", "android_permission": "none"}],
        "failure_type": "redundant-with-baseline",
        "date_created": "2026-07-20", "last_verified": "2026-07-20",
    }


def test_engine_step_writes_registry_and_log(tmp_path):
    (tmp_path / "registry").mkdir()
    (tmp_path / "results").mkdir()
    dream = Dream("fake_probe_v1", "Fake probe", "EXP-FAKE", "exp_fake.json",
                  run=lambda: ({"status": "negative", "entry_valid": True}, _fake_entry()),
                  prompt="?", topic="")
    eng = DreamEngine(root=tmp_path, model=LocalModel(enabled=False),
                      web=WebBrowser(enabled=False), do_commit=False, backlog=[dream])
    assert [d.id for d in eng.pending()] == ["fake_probe_v1"]
    summary = eng.step(dream)
    assert summary["status"] == "negative"
    assert summary["registry_valid"] is True
    assert "committed" not in summary                      # do_commit=False
    assert (tmp_path / "registry" / "registry.json").exists()
    assert (tmp_path / "results" / "exp_fake.json").exists()
    assert "fake_probe_v1" in (tmp_path / "results" / "DREAM_LOG.md").read_text()
    # once certified, it is no longer pending
    assert eng.pending() == []


def test_timer_resolution_entry_valid():
    from experiments.exp_hw_timer_resolution import run
    result, entry = run(n=5_000, verbose=False)
    assert validate_entry(entry) == []
    assert entry["status"] in ("positive", "unstable")


def test_syscall_entry_valid():
    from experiments.exp_hw_syscall import run
    result, entry = run(n=5_000, verbose=False)
    assert validate_entry(entry) == []
    assert entry["status"] in ("positive", "unstable")


def test_membw_entry_valid():
    from experiments.exp_hw_membw import run
    result, entry = run(iters=3, verbose=False)
    assert validate_entry(entry) == []
    assert entry["status"] in ("positive", "unstable")


def test_flops_entry_valid():
    from experiments.exp_hw_flops import run
    result, entry = run(iters=3, verbose=False)
    assert validate_entry(entry) == []
    assert entry["status"] in ("positive", "unstable")


def test_flops_in_backlog():
    from ccs.dream.engine import default_backlog
    assert "flops_throughput_v1" in {d.id for d in default_backlog()}


def test_mempattern_entry_valid():
    from experiments.exp_hw_mempattern import run
    result, entry = run(verbose=False)
    assert validate_entry(entry) == []
    assert entry["status"] in ("positive", "unstable")


def test_mission_is_framed_into_backlog_and_prompts():
    from ccs.dream.engine import MISSION, default_backlog
    assert "laws of this machine" in MISSION.lower()
    ids = {d.id for d in default_backlog()}
    assert {"memory_access_penalty_v1", "flops_throughput_v1"} <= ids

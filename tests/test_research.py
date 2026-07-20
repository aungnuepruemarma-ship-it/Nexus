"""Tests for the research-program modules: generator, memory graph, causal, planner, reviewer.

Fast and hermetic — no LLM, tiny measurements, synthetic graphs/data, temp repos."""
import numpy as np
import pytest

from ccs.dream import (ExperimentGenerator, MemoryGraph, ResearchPlanner, ReviewPanel,
                       DreamEngine, Dream, causal)
from ccs.validator import validate_entry


# -- Experiment Generator ----------------------------------------------------

def test_generator_skips_known_ids():
    g = ExperimentGenerator()
    all_ids = {d.id for d in g._all()}
    props = g.propose(known_ids=all_ids, n=3)      # everything known -> nothing to propose
    assert props == []
    props = g.propose(known_ids=set(), n=2)
    assert len(props) == 2 and all(isinstance(d, Dream) for d in props)


def test_generated_experiment_produces_valid_entry():
    g = ExperimentGenerator()
    d = g._bandwidth_dream(16 << 20)               # small, fast
    result, entry = d.run()
    assert entry["id"] == "mem_bandwidth_16mib_v1"
    assert validate_entry(entry) == []
    assert entry["status"] in ("positive", "unstable")


# -- Scientific Memory Graph -------------------------------------------------

def _entries():
    return {
        "a_v1": {"status": "positive", "signals": [{"family": "memory"}], "references": ["x"]},
        "b_v1": {"status": "positive", "signals": [{"family": "memory"}], "references": ["y"]},
        "c_v1": {"status": "experimental", "signals": [{"family": "cpu"}],
                 "depends_on": ["a_v1"], "references": ["x"]},
    }


def test_memory_graph_edges():
    g = MemoryGraph.from_registry(_entries())
    kinds = {(a, b, k) for a, b, k in g.edges}
    assert ("a_v1", "b_v1", "shares_signal") in kinds     # both memory
    assert ("c_v1", "a_v1", "depends_on") in kinds        # composition
    assert ("a_v1", "c_v1", "shares_reference") in kinds  # both cite "x"
    assert g.families()["memory"] == 2
    assert "graph TD" in g.to_mermaid()
    assert dict(g.neighbors("a_v1"))                       # a has neighbors


# -- Causal Discovery --------------------------------------------------------

def test_causal_separates_direct_collider_mediated():
    rng = np.random.default_rng(0)
    A = rng.normal(size=400); B = rng.normal(size=400)
    C = A + B + 0.1 * rng.normal(size=400)                # collider: A->C<-B, A _||_ B
    sk = causal.associational_skeleton(np.column_stack([A, B, C]), ["A", "B", "C"])
    direct = {(e["a"], e["b"]) for e in sk["direct_edges"]}
    collide = {(e["a"], e["b"]) for e in sk["collider_suspects"]}
    assert ("A", "C") in direct and ("B", "C") in direct
    assert ("A", "B") in collide                           # not a real direct edge
    assert ("A", "B") not in direct


# -- Research Planner --------------------------------------------------------

def test_planner_prioritizes_backlog_over_generated(tmp_path):
    (tmp_path / "registry").mkdir(); (tmp_path / "results").mkdir()
    fake = Dream("z_law_v1", "Z", "EXP-Z", "z.json", run=lambda: ({}, {}), prompt="?")
    eng = DreamEngine(root=tmp_path, model=None, web=None, do_commit=False, backlog=[fake])
    plan = ResearchPlanner(eng, ExperimentGenerator()).plan(max_items=10)
    assert plan[0]["id"] == "z_law_v1" and plan[0]["source"] == "backlog"
    assert plan[0]["priority"] > plan[-1]["priority"]      # backlog outranks generated


# -- Multi-agent Reviewer ----------------------------------------------------

def test_reviewer_accepts_sound_and_rejects_unsound():
    panel = ReviewPanel()
    good = {"status": "positive", "accuracy": 0.9, "generalization": {"axis": "t"},
            "privacy_audit": {"score": 0.7, "permissionless": True},
            "reproducibility": {"within_ci": True}}
    assert panel.review(good, {"reproduced": True})["approved"] is True
    bad = {"status": "positive", "generalization": {}, "reproducibility": {"within_ci": False}}
    r = panel.review(bad, {"reproduced": False})
    assert r["approved"] is False
    assert "Statistician" in r["blockers"] and "SafetyOfficer" in r["blockers"]


def test_engine_reviewer_gate_blocks_certification(tmp_path):
    (tmp_path / "registry").mkdir(); (tmp_path / "results").mkdir()
    # an entry that fails the blocking reviewers (no audit, no reproduction)
    bad_entry = {"id": "bad_v1", "name": "bad", "status": "positive", "version": "1.0.0",
                 "description": "d", "task": "t", "signals": [{"family": "cpu", "name": "x"}],
                 "reproducibility": {"within_ci": False}}
    dream = Dream("bad_v1", "Bad", "EXP-BAD", "bad.json",
                  run=lambda: ({"reproduced": False, "entry_valid": True}, bad_entry), prompt="?")
    eng = DreamEngine(root=tmp_path, model=None, web=None, do_commit=False,
                      backlog=[dream], reviewer=ReviewPanel())
    s = eng.step(dream)
    assert s["status"] == "rejected"
    # rejected result is recorded but NOT added to the registry
    import json
    reg_file = tmp_path / "registry" / "registry.json"
    entries = json.loads(reg_file.read_text()) if reg_file.exists() else {}
    assert "bad_v1" not in entries

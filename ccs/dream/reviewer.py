"""Multi-agent reviewer system: a panel that scrutinizes a result before it is accepted.

Mirrors the Internal Expert Council idea: several specialist reviewers, each a deterministic
rule over the measured result + built entry, plus an optional narrative review from the local
model. Two reviewers are *blocking* (a finding stops acceptance): the Statistician (it must
reproduce) and the Safety Officer (it must ship a dual-use audit). The rest are advisory. The
panel's verdict and per-reviewer notes are attached to the discovery so every certification
carries its own review record — the seed of a self-critiquing scientist.
"""
from __future__ import annotations


def _review_statistician(entry: dict, result: dict) -> dict:
    reproduced = result.get("reproduced")
    if reproduced is None:
        reproduced = entry.get("reproducibility", {}).get("within_ci")
    ok = bool(reproduced) or entry.get("status") == "negative"
    return {"reviewer": "Statistician", "blocking": True, "ok": ok,
            "note": "reproduces across independent runs" if ok else "does NOT reproduce — unreliable"}


def _review_skeptic(entry: dict, result: dict) -> dict:
    ft = entry.get("failure_type")
    redundant = ft == "redundant-with-baseline"
    base = result.get("baseline_best_acc")
    acc = (result.get("metrics") or {}).get("accuracy")
    beats = (acc is None or base is None) or acc > base
    ok = not redundant and beats
    note = ("redundant with a simpler baseline" if redundant
            else "does not beat baseline" if not beats else "adds signal beyond the baseline")
    return {"reviewer": "Skeptic", "blocking": False, "ok": ok, "note": note}


def _review_methodologist(entry: dict, result: dict) -> dict:
    gen = entry.get("generalization") or {}
    ok = bool(gen) and (("axis" in gen) or ("note" in gen))
    return {"reviewer": "Methodologist", "blocking": False, "ok": ok,
            "note": "generalization/scope recorded" if ok else "no generalization scope stated"}


def _review_safety(entry: dict, result: dict) -> dict:
    audit = entry.get("privacy_audit") or {}
    ok = bool(audit) and "score" in audit
    note = (f"dual-use audit present (score {audit.get('score')}, "
            f"permissionless={audit.get('permissionless')})" if ok else "MISSING dual-use audit")
    return {"reviewer": "SafetyOfficer", "blocking": True, "ok": ok, "note": note}


class ReviewPanel:
    def __init__(self, model=None):
        self.model = model
        self.reviewers = [_review_statistician, _review_skeptic,
                          _review_methodologist, _review_safety]

    def _model_review(self, entry: dict) -> dict | None:
        if self.model is None or not getattr(self.model, "available", False):
            return None
        try:
            note = self.model.chat(
                f"One short critique of this hardware-capability claim: "
                f"{entry.get('name')} — {entry.get('description', '')[:200]}",
                system="You are a skeptical peer reviewer. One sentence, point out the biggest caveat.")
            return {"reviewer": "PeerModel", "blocking": False, "ok": True, "note": note[:240]}
        except Exception:
            return None

    def review(self, entry: dict, result: dict) -> dict:
        reviews = [r(entry, result) for r in self.reviewers]
        mr = self._model_review(entry)
        if mr:
            reviews.append(mr)
        blockers = [r["reviewer"] for r in reviews if r["blocking"] and not r["ok"]]
        concerns = [r["reviewer"] for r in reviews if not r["blocking"] and not r["ok"]]
        verdict = "accept" if not blockers else "reject"
        if verdict == "accept" and concerns:
            verdict = "accept-with-concerns"
        return {"verdict": verdict, "approved": not blockers,
                "blockers": blockers, "concerns": concerns, "reviews": reviews}

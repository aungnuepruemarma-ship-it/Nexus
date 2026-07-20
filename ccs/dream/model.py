"""LocalModel: a small local open-source LLM used to narrate/propose hypotheses.

Default is HuggingFaceTB/SmolLM2-135M-Instruct — a 135M-parameter open model that runs on
CPU in ~1-2 s per short generation. The wrapper is lazy and degrades gracefully: if
transformers/torch or the weights are unavailable, ``available`` is False and ``chat`` returns
a deterministic template so the DreamEngine keeps working without the model.
"""
from __future__ import annotations

import os

DEFAULT_MODEL = os.environ.get("CCS_DREAM_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct")
os.environ.setdefault("HF_HOME", "/workspace/hf_cache")


class LocalModel:
    def __init__(self, name: str = DEFAULT_MODEL, enabled: bool = True, max_new_tokens: int = 64):
        self.name = name
        self.max_new_tokens = max_new_tokens
        self._tok = None
        self._model = None
        self._torch = None
        self._load_error: str | None = None
        if enabled:
            self._try_load()
        else:
            self._load_error = "disabled"

    def _try_load(self) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self._torch = torch
            self._tok = AutoTokenizer.from_pretrained(self.name)
            self._model = AutoModelForCausalLM.from_pretrained(self.name, torch_dtype=torch.float32)
            self._model.eval()
        except Exception as e:  # missing deps, no weights, offline, OOM — all non-fatal
            self._load_error = f"{type(e).__name__}: {e}"
            self._tok = self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def info(self) -> dict:
        n = (sum(p.numel() for p in self._model.parameters()) if self.available else 0)
        return {"name": self.name, "available": self.available,
                "params_m": round(n / 1e6, 1), "load_error": self._load_error}

    def chat(self, user: str, system: str | None = None) -> str:
        """Return the model's reply to ``user`` (deterministic fallback if unavailable)."""
        if not self.available:
            return f"[heuristic] {user.strip()}"
        torch = self._torch
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": user}]
        ids = self._tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
        if not torch.is_tensor(ids):
            ids = ids["input_ids"]
        with torch.no_grad():
            out = self._model.generate(
                ids, max_new_tokens=self.max_new_tokens, do_sample=True,
                temperature=0.7, top_p=0.9, pad_token_id=self._tok.eos_token_id)
        text = self._tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
        return " ".join(text.split()).strip()

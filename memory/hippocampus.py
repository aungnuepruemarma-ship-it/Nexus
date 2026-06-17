import json
import os
from core.utils import _call_llm

class Hippocampus:
    def __init__(self, db_path="db/memory.json"):
        self.db_path = db_path
        self.memories = []
        self.load()

    def compress(self, content):
        """Kolmogorov-MDL Compression: Find the shortest algorithmic representation."""
        prompt = f"Find the shortest algorithm that generates this discovery. Express it as a logical constraint:\n{content}"
        system = "You are the Kolmogorov Compressor. Your job is to maximize structural entropy by stripping all non-essential data."
        return _call_llm(system, prompt, task_type="reasoning")

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    self.memories = json.load(f)
            except Exception:
                self.memories = []

    def save(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump(self.memories, f)

    def add_memory(self, content, metadata=None):
        compressed = self.compress(content)
        self.memories.append({
            "content": compressed,
            "metadata": metadata or {}
        })
        self.save()

    def query_memories(self, query_text, n_results=5):
        # Keyword fallback
        query_words = set(query_text.lower().split())
        scored = []
        for mem in self.memories:
            content_words = set(mem['content'].lower().split())
            intersection = query_words.intersection(content_words)
            scored.append((len(intersection), mem['content']))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [content for score, content in scored[:n_results]]

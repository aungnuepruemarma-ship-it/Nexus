import json
import os

class Hippocampus:
    def __init__(self, db_path="db/memory.json"):
        self.db_path = db_path
        self.memories = []
        self.load()

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
        self.memories.append({
            "content": content,
            "metadata": metadata or {}
        })
        self.save()

    def query_memories(self, query_text, n_results=5):
        # Simple keyword matching as a fallback for vector search
        query_words = set(query_text.lower().split())
        scored_memories = []
        for mem in self.memories:
            content_words = set(mem['content'].lower().split())
            intersection = query_words.intersection(content_words)
            scored_memories.append((len(intersection), mem['content']))
        
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [content for score, content in scored_memories[:n_results]]

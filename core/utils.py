import os
import json
import time
import sqlite3
import random
from datetime import datetime
from duckduckgo_search import DDGS

# --- Performance Tracking ---
class PerformanceTracker:
    def __init__(self, db_path="db/metrics.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS metrics (provider TEXT, task_type TEXT, latency REAL, timestamp DATETIME)")

    def log(self, provider, task_type, latency):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO metrics VALUES (?, ?, ?, ?)", (provider, task_type, latency, datetime.now()))

    def get_best_provider(self, task_type):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT provider FROM metrics WHERE task_type = ? GROUP BY provider ORDER BY AVG(latency) ASC LIMIT 1", (task_type,)).fetchone()
            return row[0] if row else "gemini"

tracker = PerformanceTracker()

# --- Utilities ---
def perform_web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            return "\n".join([f"- {r['title']}: {r['body']}" for r in list(ddgs.text(query, max_results=3))])
    except Exception as e: return f"Search failed: {e}"

def get_dna(agent_name: str) -> str:
    dna_file = "db/dna.json"
    if not os.path.exists(dna_file): return ""
    try:
        with open(dna_file, 'r') as f:
            dna = json.load(f)
            return "\n" + "\n".join([f"- {instr}" for instr in dna.get(agent_name, [])])
    except: return ""

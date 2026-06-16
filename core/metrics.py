import sqlite3
import time
from datetime import datetime

class PerformanceTracker:
    def __init__(self, db_path="db/metrics.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    provider TEXT,
                    task_type TEXT,
                    latency REAL,
                    timestamp DATETIME
                )
            """)

    def log(self, provider, task_type, latency):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO metrics VALUES (?, ?, ?, ?)",
                         (provider, task_type, latency, datetime.now()))

    def get_best_provider(self, task_type):
        with sqlite3.connect(self.db_path) as conn:
            # Simple heuristic: cheapest/fastest average
            row = conn.execute("""
                SELECT provider FROM metrics 
                WHERE task_type = ? 
                GROUP BY provider 
                ORDER BY AVG(latency) ASC LIMIT 1
            """, (task_type,)).fetchone()
            return row[0] if row else "gemini"

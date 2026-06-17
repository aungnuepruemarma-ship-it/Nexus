import os
import json
import time
import sqlite3
import random
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# Initialize LLM
def get_llm():
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and "AQ." not in gemini_key:
         return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=gemini_key), "gemini"
    groq_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY_2")
    if groq_key:
        return ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=groq_key), "groq"
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return ChatOpenAI(model="anthropic/claude-3.5-sonnet", openai_api_key=or_key, openai_api_base="https://openrouter.ai/api/v1")
    raise ValueError("No valid API key found")

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

def _call_llm(system_prompt: str, user_prompt: str, task_type: str = "general") -> str:
    start_time = time.time()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    
    # Retry mechanism
    for i in range(10):
        try:
            llm, provider = get_llm()
            response = llm.invoke(messages)
            latency = time.time() - start_time
            tracker.log(provider, task_type, latency)
            return response.content
        except Exception as e:
            if "429" in str(e):
                wait = min(2 ** i, 30)
                time.sleep(wait)
                continue
            raise e
    raise Exception("Max retries exceeded")

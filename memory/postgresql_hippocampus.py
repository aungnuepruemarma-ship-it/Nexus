import os
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np

class PostgresHippocampus:
    def __init__(self, db_url):
        self.conn = psycopg2.connect(db_url)
        register_vector(self.conn)

    def add_memory(self, content, embedding):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO discovery_embeddings (discovery_summary, embedding) VALUES (%s, %s)", (content, embedding))
            self.conn.commit()

    def query_memories(self, embedding, top_k=5):
        with self.conn.cursor() as cur:
            cur.execute("SELECT discovery_summary FROM discovery_embeddings ORDER BY embedding <=> %s LIMIT %s", (embedding, top_k))
            return cur.fetchall()

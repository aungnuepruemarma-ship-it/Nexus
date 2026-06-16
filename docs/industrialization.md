# Nexus Organism: Industrialization Roadmap

## 1. Memory Upgrade: PostgreSQL + pgvector

To scale from JSON memory to enterprise-grade knowledge storage, migrate `Hippocampus` to PostgreSQL.

### Migration Schema
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE discovery_embeddings (
    id SERIAL PRIMARY KEY,
    domain_a TEXT,
    domain_b TEXT,
    discovery_summary TEXT,
    embedding VECTOR(1536) -- For OpenAI/SentenceTransformers
);

CREATE INDEX ON discovery_embeddings USING ivfflat (embedding cosine_ops);
```

### Next Steps
1.  **Install:** `pip install psycopg2-binary pgvector`
2.  **Refactor:** Rewrite `memory/hippocampus.py` to use `psycopg2` for vector queries.

## 2. Security Auditor Integration

The `SecurityAuditor` agent is now live in `swarm.py`. It is triggered automatically by the Synthesizer node to audit the `final_synthesis`. 

*   **Logic:** `security_auditor_node` -> `final_synthesis` -> Audit -> Fail/Pass validation result.

## 3. Meta-Manager (Phase 6b)

`core/meta_manager.py` provides the scaffolding for intelligent task allocation based on `compute_energy` and `curiosity_score`.

*   **Next step:** Implement `orchestrator.py` integration to switch between `NexusOrchestrator` (standard) and `MetaDiscoveryOrchestrator` (parallel) based on the energy budget.

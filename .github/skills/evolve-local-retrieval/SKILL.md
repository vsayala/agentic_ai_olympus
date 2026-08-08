---
name: evolve-local-retrieval
description: "Use when changing Olympus local extraction, chunking, embeddings, query classification, ranking, citation provenance, Milvus schema, persistence, invalidation, or recovery behavior in knowledge_01 or vector_db_02."
argument-hint: "Describe the local retrieval behavior or lifecycle transition to change"
user-invocable: true
disable-model-invocation: false
---

# Evolve Local Retrieval

Do not use a generic retrieval-backend scaffold: the lexical baseline and production Milvus stack
have intentionally different contracts and must remain isolated.

## Procedure

1. Classify the change as lexical baseline, production vector retrieval, or a boundary consumed by
   evaluation or Hercules. Read `ARCHITECTURE_PROCESS.md`, the owning implementation, caller, and
   focused tests.
2. Preserve package isolation. Never import `knowledge_01` from `vector_db_02` or the reverse, and
   never make Chatbot execute the baseline automatically.
3. Change the smallest owning surface:
    - Lexical extraction/ranking: `src/olympus_copilot_sdk/knowledge_01/lexical.py` and
       `src/olympus_copilot_sdk/knowledge_01/retrieval.py`.
    - Vector documents/chunks/embeddings: `src/olympus_copilot_sdk/vector_db_02/documents.py`,
       `chunking.py`, and `embeddings.py` in that package.
    - Ranking/query behavior: `src/olympus_copilot_sdk/vector_db_02/retrieval.py`.
    - Collection lifecycle: `src/olympus_copilot_sdk/vector_db_02/milvus.py`.
4. When persisted interpretation changes, update the applicable schema, chunking, retrieval,
   location, content, or embedding version. Ensure every behavior-affecting setting participates in
   the collection fingerprint.
5. Add deterministic tests for ranking, fusion, deduplication, source diversity, broad coverage,
   limits, stable citation IDs, and source/location maps as applicable.
6. For persistence changes, use a temporary Milvus database. Test initial build, ready/reuse,
   invalidation/rebuild, close/reopen, released-state recovery, bounded batching, and concurrent
   serialization. Never probe `.olympus/milvus_lite.db` while the application owns it.
7. Test the Hercules boundary and evaluation snapshots when `SearchResult` or citation semantics
   change.
8. Update architecture and migration documentation for any one-time rebuild or compatibility
   effect.

## Validation and Sign-Off

```bash
uv sync --extra dev --locked
uv run pytest tests/test_knowledge.py tests/test_vector_db.py tests/test_agent_capabilities.py
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -c pyproject.toml -r src app.py run_app.py
uv run pip-audit
uv build
```

Loki always signs. Require Thor for agent-facing evidence changes, Hela for displayed retrieval
semantics, and Odin for engine replacement or final cross-domain integration.
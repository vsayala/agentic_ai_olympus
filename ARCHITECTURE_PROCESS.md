# Olympus Architecture Process

## Non-Negotiable Runtime Flow

1. Chatbot executes only `02_Vector_DB`.
2. A vector chat turn performs extraction/index reuse, query embedding, Milvus search, Hercules
   evidence generation, and Zeus synthesis.
   The original query drives retrieval directly; the vector workflow uses two model calls.
3. The turn stores its exact prompt, model, pricing, vector response, sources, usage, latency, and
   deterministic metrics as a pending evaluation record.
4. `01_Knowledge` does not run during Chatbot requests.
5. Evaluation runs `01_Knowledge` only after the user selects **Run 01_Knowledge baseline**.
6. The baseline uses the stored prompt and model, then attaches isolated usage and metrics to the
   existing record.

## Ownership

`knowledge_01/` is the complete original lexical baseline. It owns its agents, prompts, skills,
tools, extraction, chunking, retrieval contracts, and TF-IDF ranking.

`vector_db_02/` is the complete production vector application. It owns its agents, prompts,
skills, tools, extraction, semantic chunking, FastEmbed integration, retrieval contracts, and
Milvus Lite persistence. Child chunks remain at most 800 characters and retain PDF page metadata;
adjacent children form bounded parent sections of at most 2,400 characters. Retrieval classifies
queries deterministically. Targeted mode performs dense and package-local lexical rank fusion,
deduplication, and source-aware diversity over children. Broad mode aggregates relevance to choose
a primary document and selects representative parents across distinct locations and generic topic
families within a fixed evidence budget. Selected excerpts use stable per-response citation IDs.
The evaluation map resolves IDs to underlying source names, while a separate display map includes
page, section, or stable chunk location.

The numbered packages must not import from each other. Shared code outside them is limited to UI
navigation and stack-neutral evaluation snapshots and metrics.

## Change Process

1. Identify whether a change belongs to the production vector stack, baseline stack, evaluation,
   or UI.
2. Keep retrieval and agent changes inside the owning numbered package.
3. Never add automatic baseline execution to Chatbot.
4. Preserve prompt, model, result-limit, and pricing parity when comparison fairness requires it.
5. Add a focused test for the owning package before changing adjacent layers.
6. Run strict Pyright, pytest, Ruff, Bandit, pip-audit, and package build.
7. Run Odin after project-wide integration changes.

## Evaluation Interpretation

Token counts, model calls, and SDK cost are observed values. Citation validity, source coverage,
grounded-sentence ratio, token efficiency, and quality score are deterministic operational
proxies. They do not prove factual correctness. No judge model is used, so metric computation adds
no model tokens. Canonical source legends are excluded from citation scoring; both stacks are
evaluated on citations present in the answer body, and annotated legacy source citations remain
valid only when their exact underlying filename was retrieved. Broad vector results may also expose
evidence-topic citation completeness derived from retrieved topic-to-citation mappings. It is
reported separately and does not affect the cross-stack quality score because the lexical baseline
does not expose a comparable retrieval contract.

## Stateful Vector Gate

Milvus Lite is single-process owned by the application. Index construction, collection loading,
released-state recovery, search, close, and reconnect transitions are serialized by the knowledge
base `RLock`. Chunking, hierarchy, location, schema, retrieval, content, and embedding-model values
participate in the fingerprint; an incompatible collection is rebuilt in bounded batches. Tests and
external probes must use temporary databases and must never open `.olympus/milvus_lite.db` while the
application owns it.
# Olympus Architecture Process

## Non-Negotiable Runtime Flow

1. Chatbot executes only `02_Vector_DB`.
2. A vector chat turn performs extraction/index reuse and retrieval against every configured local
   corpus. Deterministic evidence relevance routes the request to Hercules (`data/`), Hades
   (`data_2/`), or both. Only selected specialists receive excerpts and make a model call; Zeus
   synthesizes their typed, cited reports. A single-specialist turn uses two model calls.
3. The turn stores its exact prompt, model, pricing, vector response, sources, usage, latency, and
   deterministic metrics as a pending evaluation record.
4. `01_Knowledge` does not run during Chatbot requests.
5. Evaluation runs `01_Knowledge` only after the user selects **Run 01_Knowledge baseline**.
6. The baseline uses the stored prompt and model, then attaches isolated usage and metrics to the
   existing record.

## Ownership

The project uses four architecture stewards:

- **Loki** owns data and retrieval engineering: `knowledge_01` lexical retrieval,
   `vector_db_02` document/index/Milvus retrieval,
   `src/olympus_copilot_sdk/03_azure_databricks`, and future data sources,
   databases, indexes, retrieval engines, and data platforms.
- **Thor** owns application agents: Zeus, Hercules, future agents, orchestration, prompts, skills,
   tools, model sessions, grounding, and agent-facing evidence contracts.
- **Hela** owns frontend experience: Streamlit navigation, pages, session state, interaction,
   accessibility, responsive behavior, and user-visible failures.
- **Odin** owns project-wide architecture and final integration. Every Odin run collects fresh
   Loki, Thor, and Hela receipts, validates them through the typed governance contract, and
   preserves their conditions.

The repository-safe `ai_registry/` records system inventory, ownership, risk and applicability
status, control baselines, retention, and external evidence references. Loki, Thor, and Hela review
fields in their existing domains; Odin validates and integrates the registry. The registry does not
create a fifth steward, grant runtime permissions, or change application boundaries.

Ownership follows behavior rather than only folders. A retrieval adapter consumed by Hercules
requires Loki for provenance and Thor for the agent contract. A UI that changes agent or retrieval
semantics requires Hela plus the affected specialist. `run_app.py` lifecycle changes require Odin
and Hela, plus Thor or Loki when model or database lifecycle changes.

## Workflow Skills

Use a skill for a repeatable implementation or readiness procedure; use the owning agent directly
for investigation, review, debugging, or a one-off change. Skills do not replace specialist or Odin
sign-off.

| Skill | Use it for | Primary steward |
|---|---|---|
| `add-databricks-source` | File, API, structured, Genie, AI Search, or MCP source onboarding | Loki |
| `evolve-local-retrieval` | Local chunking, embeddings, ranking, Milvus, or citation provenance | Loki |
| `add-document-format` | A new parser or locally indexed file format | Loki |
| `create-doc-capability` | User-requested Markdown, DOCX, or PDF output from cited results | Thor + Hela + Loki |
| `add-evaluation-metric` | Deterministic metric, snapshot, comparison, or score changes | Loki + Hela |
| `add-olympus-agent` | A new application agent or agent capability under Thor | Thor |
| `add-ui-workflow` | A Streamlit page, interaction, navigation, or session-state workflow | Hela |
| `verify-ui-readiness` | Pre-merge UI, accessibility, rerun, and launcher verification | Hela |

Do not use `add-olympus-agent` to create `.github` steward agents. Use the VS Code agent
customization workflow for those. Do not use a generic retrieval-backend scaffold: local lexical,
Milvus, and Databricks implementations have different persistence, governance, and validation
requirements.

Do not create `.github/tools/`. It is not an Olympus runtime-tool registry or a supported workspace
customization primitive. Runtime capabilities remain typed and package-owned in each numbered
stack's `tools.py`; repeatable implementation procedures belong under `.github/skills/`, and
external tool integrations belong behind reviewed MCP or extension configuration.

`knowledge_01/` contains the complete original lexical baseline implementation: agents, prompts,
skills, tools, extraction, chunking, retrieval contracts, and TF-IDF ranking. Code remains local to
the package; Thor reviews agent semantics while Loki reviews data and retrieval semantics.

`vector_db_02/` contains the complete production vector implementation: agents, prompts, skills,
tools, extraction, semantic chunking, FastEmbed integration, retrieval contracts, and Milvus Lite
persistence. Code remains local to the package; Thor reviews agent semantics while Loki reviews
data and retrieval semantics. Child chunks remain at most 800 characters and retain PDF page metadata;
adjacent children form bounded parent sections of at most 2,400 characters. Retrieval classifies
queries deterministically. Targeted mode performs dense and package-local lexical rank fusion,
deduplication, and source-aware diversity over children. Broad mode aggregates relevance to choose
a primary document and selects representative parents across distinct locations and generic topic
families within a fixed evidence budget. Selected excerpts use stable per-response citation IDs.
The evaluation map resolves IDs to underlying source names, while a separate display map includes
page, section, or stable chunk location.

Corpus-backed specialists follow one reusable contract: each corpus receives the same extraction,
chunking, embedding, ranking, and independently persisted Milvus lifecycle; retrieval runs before
delegation; deterministic relevance selects specialists without requiring users to name folders;
selected evidence is renumbered into one collision-free citation namespace. New corpus specialists
must be registered through this contract rather than added as prompt-only routing branches.

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
7. For project-wide, release, deployment, or governance work, validate `ai_registry/` and update the
   affected system record without committing sensitive operational evidence.
8. Before every Odin run, obtain fresh Loki, Thor, and Hela contract-version `1.0` receipts for the
   same task, revision, and reviewed artifacts. Validate them as described in
   [docs/GOVERNANCE.md](docs/GOVERNANCE.md).
9. Give those receipts to Odin for the only final project-wide sign-off. Odin cannot upgrade a
   conditional or blocked specialist status to an unconditional pass. Status precedence is
   `BLOCKED` over `CONDITIONAL PASS` over `PASS`; a missing, malformed, or stale receipt is blocked.
10. Specialists do not invoke each other. Odin mediates at most two challenge rounds; unresolved
   disagreement is blocked. Consequential governance and deployment actions require human approval.

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
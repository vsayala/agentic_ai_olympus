# Olympus Project Checkpoint

Last updated: 2026-08-09

## Durable Architecture

- Chatbot runs only the production `vector_db_02` workflow: Milvus retrieval, Hercules evidence,
  then Zeus synthesis.
- Evaluation runs the isolated `knowledge_01` lexical baseline only after explicit user action.
- Loki owns data, retrieval, persistence, and Databricks; Thor owns agents and evidence contracts;
  Hela owns Streamlit UX; Odin owns final integration.
- Every Odin run requires fresh Loki, Thor, and Hela reports. A conditional or blocked specialist
  status propagates unchanged.
- The production Milvus Lite database is single-process owned. External probes use temporary data.

## Current Project State

- The Azure Databricks project lives at
  `src/olympus_copilot_sdk/03_azure_databricks` and remains independently locked, tested, and built.
- Root Pyright, Bandit, source distribution, and wheel exclude the nested Databricks project; its own
  quality and build gates run from the nested project root.
- The Chatbot sidebar shows the Milvus semantic chunk count and a deterministic Data Folder inventory.
- Sidebar select, action button, and expander surfaces use accessible green backgrounds with light text.
- Image-only PDFs produce no synthetic semantic content and are classified as skipped.
- `.copilotignore` excludes generated state, the large `data/` corpus, and lockfiles on supported
  Copilot surfaces. Managed GitHub exclusions remain the authoritative enterprise control.
- `/checkpoint-session` rewrites this bounded file; `/resume-project` starts one task from it without
  a whole-workspace scan.

## Last Verified Baseline

- Root Ruff formatting/lint and strict Pyright passed.
- Root test suite: 41 passed.
- Nested Databricks test suite: 17 passed; nested Ruff, strict Pyright, Bandit, audit, and build passed.
- Root and nested dependency audits reported no known vulnerabilities.
- Root source distribution and wheel contain no nested Databricks entries; the nested wheel contains
  `olympus_databricks`.
- Copilot ignore matching excludes heavy tracked inputs and no application Python source. Prompt
  frontmatter, checkpoint links, and the 120-line checkpoint limit were validated.

## Open Conditions

- Databricks CLI and authenticated cloud checks are unavailable locally. Before promotion, validate
  every target, inspect the generated resource graph, and run the dev acquisition/table/retrieval/
  failure/idempotency smoke workflow.
- Root Bandit reports two existing low-severity subprocess findings in `run_app.py` (`B404`, `B603`).
- The current relocation and context-efficiency changes are not committed unless Git status proves
  otherwise.

## Starting the Next Session

1. Attach `#file:docs/COPILOT_CHECKPOINT.md` and the one implementation file or folder being changed.
2. Run `/resume-project` and state one task.
3. Read `ARCHITECTURE_PROCESS.md` only when the task crosses ownership boundaries.
4. Before switching tasks, run `/checkpoint-session` and start a new chat.

---
name: add-ui-workflow
description: "Use when adding or materially changing an Olympus Streamlit page, navigation route, long-running interaction, session-state transition, or UI representation of agent, retrieval, or evaluation output."
argument-hint: "Describe the page or interaction, its session states, model calls, and user-visible outcomes"
user-invocable: true
disable-model-invocation: false
---

# Add a Streamlit Workflow

## Procedure

1. Read Hela's agent definition, `ARCHITECTURE_PROCESS.md`, `app.py`, the nearest module under
   `src/olympus_copilot_sdk/ui`, and its agent, retrieval, or evaluation caller.
2. Classify the workflow as navigation, Chatbot, Evaluation, shared UI, or launcher lifecycle.
   Define idle, empty, running, success, error, retry, cancellation, clear, and rerun states.
   If the underlying operation cannot be cancelled safely, state that explicitly and prevent a
   second submission while it is in flight.
3. Define stable session keys and ownership. Each explicit user action must cause at most one model
   workflow, and reruns must not duplicate calls or lose completed records.
4. Preserve runtime routing: Chatbot uses only `VectorOrchestrator`; Evaluation invokes
   `KnowledgeOrchestrator` only after **Run 01_Knowledge baseline**.
5. Keep orchestration and retrieval out of UI modules. Use cached resources through the existing
   helpers and never open a second production Milvus connection.
6. Commit completed state atomically before `st.rerun()`. Do not retain stale orchestrators,
   sessions, subprocesses, or closed resource handles in session state.
7. Render source and model content as untrusted data. Do not expose secrets, hidden system prompts,
   or executable markup. Translate exceptions at the UI boundary; do not display raw `str(error)`
   when it may contain paths, prompts, credentials, endpoints, or source content.
8. Add deterministic tests with fake orchestrators for routing, one-call behavior, success,
   failure, retry, rerun, clear, and explicit-baseline behavior. Use Streamlit testing APIs only
   where they improve behavior coverage without coupling tests to incidental markup.
9. Update user documentation when navigation, labels, commands, or lifecycle changes.

## Validation and Sign-Off

Run focused tests immediately, then the root quality gate. Use `verify-ui-readiness` for an
interactive change before release.

```bash
uv sync --extra dev --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -c pyproject.toml -r src app.py run_app.py
uv run pip-audit
uv build
```

Hela always signs. Require Thor for changed stages, calls, citations, or agent semantics; Loki for
changed retrieval, source, persistence, or evaluation semantics; and Odin for launcher lifecycle
or final integration.
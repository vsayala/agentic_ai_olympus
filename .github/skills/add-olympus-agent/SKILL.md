---
name: add-olympus-agent
description: "Use when adding a new Olympus application agent, introducing a research or synthesis role, changing Zeus-to-Hercules delegation, or extending an agent prompt, tool, permission, evidence field, citation format, or model-facing capability under Thor governance."
argument-hint: "Describe the new application agent, its caller, evidence boundary, tools, and expected handoff"
user-invocable: true
disable-model-invocation: false
---

# Add an Olympus Application Agent

This skill adds an application agent such as Zeus or Hercules. It does not create a `.github`
custom steward agent.

## Procedure

1. Read `ARCHITECTURE_PROCESS.md`, Thor's agent definition, the owning numbered package, and
   `tests/test_agent_capabilities.py`.
2. Define the agent's role, caller, permissions, model calls, evidence boundary, typed handoff and
   UI contracts, citation behavior, retry observability, cancellation behavior, and failure
   contract before editing. Zeus remains the user-facing orchestrator.
3. Keep the complete implementation in the owning numbered package. Never create root-level agent,
   prompt, skill, or tool modules and never import between `knowledge_01` and `vector_db_02`.
   Databricks and future data-to-agent adapters are a joint boundary: Loki owns provenance and
   retrieval contracts while Thor owns agent consumption, grounding, and citations.
4. Preserve local ownership:
   - `prompts.py`: system messages and rendering of untrusted input.
   - `skills.py`: typed, bounded reasoning requests.
   - `tools.py`: minimal model or retrieval protocols and adapters.
   - `agents.py`: session ownership, explicit delegation, stages, usage, and cleanup.
5. Keep SDK-provided tools disabled with `available_tools=[]` unless a reviewed permission change
   explicitly requires otherwise. Do not grant capabilities through prompt text.
6. Treat user text, filenames, excerpts, tool output, and agent reports as untrusted. Require stable
   citations and explicit insufficient-evidence behavior. Do not create hidden delegation paths.
   Retries, failures, and cancellation must be observable, and usage/cost must not be double-counted.
7. Add deterministic fake-client tests for delegation order, model-call count, stages, usage,
   citations, empty evidence, malicious instructions, failures, cancellation, and cleanup.
8. Verify Chatbot still runs only `vector_db_02` and Evaluation runs `knowledge_01` only after the
   explicit baseline action.
9. Update `README.md` and `ARCHITECTURE_PROCESS.md` when responsibilities or runtime flow change.

## Validation and Sign-Off

Run focused agent tests first, then the root quality gate:

```bash
uv sync --extra dev --locked
uv run pytest tests/test_agent_capabilities.py
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -c pyproject.toml -r src app.py run_app.py
uv run pip-audit
uv build
```

Thor always signs. Require Loki when retrieval or evidence provenance changes, Hela when visible
stages or UI contracts change, and Odin for final integration. When authentication is available,
exercise one representative end-to-end delegation and report unavailable live checks explicitly.
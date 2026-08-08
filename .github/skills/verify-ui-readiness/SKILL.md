---
name: verify-ui-readiness
description: "Use before merging or releasing Olympus Streamlit or launcher changes, or when investigating reruns, duplicate calls, navigation, responsiveness, accessibility, startup, shutdown, or user-visible error regressions."
argument-hint: "Describe the changed UI workflows, launcher behavior, and environments available for verification"
user-invocable: true
disable-model-invocation: false
---

# Verify UI Readiness

## Procedure

1. Inventory changed pages, controls, session keys, cached resources, orchestrator calls, and any
   `run_app.py` lifecycle behavior.
2. Run focused deterministic UI and routing tests first, then the complete root quality gate.
   The gate starts with `uv sync --extra dev --locked`, followed by Ruff, strict Pyright, pytest,
   Bandit, pip-audit, and `uv build`.
3. Start the supported launcher on a free port:

   ```bash
   STREAMLIT_PORT=8502 uv run python run_app.py
   ```

   Do not substitute direct `streamlit run` when validating Copilot CLI startup and cleanup.
4. Exercise Chatbot empty, running, success, failure/retry, history, and clear states. Confirm a
   Streamlit rerun does not repeat a model call.
5. Exercise Evaluation pending, explicit baseline, baseline failure/retry, completed comparison,
   and preference states. Confirm Chatbot never starts the baseline.
6. Check keyboard navigation, labels, focus, contrast, text wrapping, and non-overlap at desktop
   and mobile viewport sizes when browser tooling is available.
7. When launcher behavior changed, test missing CLI, unavailable model, startup timeout, occupied
   UI port, Streamlit exit, and Copilot child cleanup without sending secrets through automation.
   Track and terminate only child processes started by this validation; report unrelated preexisting
   processes rather than killing them.
8. Inspect user-visible errors for actionable wording and absence of credentials, raw prompts,
   hidden messages, source-document contents, or executable source markup.
9. Record authentication, browser, model, or runtime checks that were unavailable. Never infer
   interactive readiness from unit tests alone.

## Sign-Off

Return Hela's exact status with workflows, viewports, lifecycle transitions, blocked checks, and
required actions. Require Thor when agent stages or calls changed, Loki when retrieval/data states
changed, and Odin for final release status.
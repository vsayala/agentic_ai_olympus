---
name: add-evaluation-metric
description: "Use when adding or changing Olympus deterministic evaluation metrics, comparison fields, pending evaluation snapshots, quality-score inputs, or metric presentation across lexical and vector results."
argument-hint: "Describe the metric inputs, denominator, unavailable state, interpretation, and comparability"
user-invocable: true
disable-model-invocation: false
---

# Add an Evaluation Metric

## Procedure

1. Read `ARCHITECTURE_PROCESS.md`, `src/olympus_copilot_sdk/evaluation/metrics.py`,
   `src/olympus_copilot_sdk/evaluation/comparison.py`, `tests/test_evaluation.py`, and
   `src/olympus_copilot_sdk/ui/evaluation_page.py`.
2. Define the metric's inputs, denominator, range, zero-denominator behavior, unavailable state,
   interpretation, and whether both stacks expose a genuinely comparable contract.
3. Keep the metric deterministic. Do not add a judge-model call, spend model tokens, rerun
   retrieval, or trigger the lexical baseline during Chatbot.
4. Extend result protocols or immutable pending snapshots only when an input must survive between
   the vector run and the user's later baseline action. Preserve the stored prompt, model, prices,
   sources, usage, and latency.
5. Implement explicit handling for absent contracts, legacy citations, targeted queries, broad
   queries, and zero denominators.
6. Decide explicitly whether the metric affects `quality_score`. Default to separate reporting for
   stack-specific metrics rather than creating false comparison parity.
7. Add tests for valid, invalid, missing, partial, legacy, targeted, broad, and baseline cases.
   Verify canonical source legends are excluded when the metric evaluates answer-body citations.
8. Render the metric without claiming factual correctness and explain its operational limits in
   `README.md` or `ARCHITECTURE_PROCESS.md`.

## Validation and Sign-Off

```bash
uv sync --extra dev --locked
uv run pytest tests/test_evaluation.py tests/test_agent_capabilities.py
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -c pyproject.toml -r src app.py run_app.py
uv run pip-audit
uv build
```

Loki signs metric and evidence semantics, Hela signs presentation, Thor signs changed agent output
contracts, and Odin provides final integration status.
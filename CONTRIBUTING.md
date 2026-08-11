# Contributing

Use a pull request for every change. Preserve the boundaries in
[ARCHITECTURE_PROCESS.md](ARCHITECTURE_PROCESS.md) and add focused tests for behavior changes.

## Local Quality Gate

```bash
uv sync --extra dev --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest --cov-fail-under=70
uv run bandit -c pyproject.toml -r src
uv run pip-audit
uv build
```

Run SharePoint checks from `src/olympus_copilot_sdk/01_sp` and Databricks checks from
`src/olympus_copilot_sdk/02_adb` when those projects
changes. Cloud readiness additionally requires authenticated bundle validation and a dev smoke test.

## Review and Release

- Changes require passing status checks and human review.
- Project-wide integration requires fresh Loki, Thor, and Hela receipts and Odin's final status as
  described in [docs/GOVERNANCE.md](docs/GOVERNANCE.md).
- Dependencies, permissions, deployment configuration, production data, and governance contracts
  require explicit human approval.
- Never commit generated databases, credentials, tokens, private source content, or model caches.
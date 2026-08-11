# Olympus Databricks adapters

This is the active Olympus Databricks project. It provides a minimal retrieval boundary for
Databricks Vector Search, Genie, and an external MCP connection using zero runtime dependencies.

All adapters return the same stable `Evidence` contract and treat source text as untrusted data.
The caller context is forwarded to the selected backend so workspace resources and source ACLs can
authorize the request. The catalog is fixed to `data`; each source owns one validated schema.

## Selection

- `vector_search` is the default for unstructured semantic evidence. Configure a promoted endpoint
  and index only after the source table exists, Change Data Feed is enabled, and ACL filtering is
  verified.
- `genie` is for structured data in an existing Genie space backed by a configured SQL warehouse.
- `mcp` calls a governed external connection. It does not copy or persist external content.

Copy `configs/example.toml` to a source-specific lowercase config and resolve the selected
strategy's placeholders. Configuration loading rejects missing or placeholder values required by
the selected strategy. Tokens, OAuth credentials, and secret values must come from the runtime
identity or a governed connection; they must not be stored in this project.

`databricks.yml` and `resources/unity_catalog.yml` provide the shared deployment skeleton. The
catalog remains `data`, each source receives one explicitly configured lowercase schema, and
durable catalog deletion is blocked. Add source-specific indexes, Genie spaces, warehouses, jobs,
or MCP connections only after their identifiers and environment principals are approved.

## Local validation

```bash
uv sync --extra dev --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run bandit -q -c pyproject.toml -r src
uv run pip-audit
uv build
BUNDLE_VAR_source_schema=ci_validation databricks bundle validate --target dev
```

The deployment workflow runs these checks for pull requests and pushes. Deployment is available
only through manual dispatch to a protected environment using GitHub OIDC; the environment must
supply `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and `DATABRICKS_SOURCE_SCHEMA`. Live cloud
validation remains pending until endpoints, indexes, warehouses, connections, permissions, and
test principals are supplied.
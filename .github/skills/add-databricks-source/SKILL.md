---
name: add-databricks-source
description: "Use when adding or designing a new enterprise data source in 03_azure_databricks, including file, API, structured, Genie, AI Search, or external MCP ingestion and retrieval."
argument-hint: "Describe the source shape, system of record, freshness, classification, citation key, and materialization policy"
user-invocable: true
disable-model-invocation: false
---

# Add Databricks Source

All paths in this skill are relative to `03_azure_databricks/` unless they start with
`03_azure_databricks/` explicitly.

1. Read `03_azure_databricks/ARCHITECTURE.md`, `docs/ADD_SOURCE.md`, the nearest source config,
   job, implementation, and tests.
2. State the source shape, system of record, freshness, stable citation key, data classification,
   and whether materialization is permitted.
3. Choose exactly one primary retrieval strategy:
   - `files`: raw landing, versioned parsing, semantic chunks, Delta Sync AI Search.
   - `api`: immutable raw payload, bronze, silver, gold, then Genie or deterministic UC function.
   - `mcp`: governed external MCP through Unity AI Gateway; no default copy.
4. Copy `03_azure_databricks/templates/source.yml` to `configs/<source>.yml`. Validate Unity
   Catalog identifiers, environment substitutions, secrets ownership, and every placeholder.
5. Add one source schema and required volumes in `resources/unity_catalog.yml`. Keep dependent
   indexes, Genie spaces, and serving endpoints opt-in until their tables, warehouses, and model
   versions exist. Declare least-privilege grants against environment identities when those
   identities are known; never invent principals in a template.
6. Put business logic under `src/olympus_databricks/sources/<source>/`. Keep numbered `.py`
   Databricks source notebooks as thin widgets, secrets, Spark, and SDK adapters.
7. Create one ordered job under `resources/jobs/` with explicit dependencies, bounded execution,
   retries where safe, structured failure propagation, and project-wheel installation.
8. Add mocked tests for config, retries/failures, transformation order, retrieval normalization,
   exact task order, source-notebook headers, config paths, and wheel availability.
    - File sources must keep beta capabilities configurable, pin parser schema versions, and enable
       Change Data Feed before Delta Sync.
    - API sources must test pagination, throttling, repeated cursors, duplicate identifiers, bounded
       retries, immutable raw payloads, and idempotent reruns.
    - MCP sources must use governed connections or managed OAuth and must not materialize data
       without an explicit latency, resilience, retention, or audit requirement.
    - No source may log tokens, credentials, raw source content, or secret values.
9. Run the source validator and nested quality gate:

   ```bash
   cd 03_azure_databricks
   uv sync --extra dev --locked
   uv run python tools/validate_source.py configs/<source>.yml
   uv run ruff format --check .
   uv run ruff check .
   uv run pyright
   uv run pytest
   uv run bandit -q -c pyproject.toml -r src notebooks tools
   uv run pip-audit
   uv build
   databricks bundle validate --target dev
   ```

10. When authenticated, inspect the generated resource graph and run a dev smoke test covering
   acquisition, table creation, retrieval readiness, failure logs, and idempotent reruns.
   Validate every target before its promotion; do not infer remote readiness from local mocks.
11. Ask Loki for data-platform sign-off. If the source changes Hercules or another agent contract,
   also ask Thor; if it changes UI behavior, also ask Hela. Provide every applicable report to Odin
   for final integration review.

Never commit secrets, invent a model version, enable a beta feature silently, or mark remote
connectivity as verified based on local mocks.
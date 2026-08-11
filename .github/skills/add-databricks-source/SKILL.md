---
name: add-databricks-source
description: "Use when adding or designing a SharePoint, Graph, Azure AI Search, Databricks Vector Search, Genie, or governed MCP source in src/olympus_copilot_sdk/01_sp or src/olympus_copilot_sdk/02_adb."
argument-hint: "Describe the source, authorization authority, shape, freshness, classification, citation key, and materialization policy"
user-invocable: true
disable-model-invocation: false
---

# Add an Enterprise Data Source

Use `src/olympus_copilot_sdk/01_sp/` for SharePoint or Microsoft Graph retrieval and
`src/olympus_copilot_sdk/02_adb/` for Databricks ingestion and retrieval. Keep the standalone
packages isolated and use each package's locked environment.

1. Read the owning package README, nearest config, implementation, resources, and focused tests.
2. State the source shape, system of record, authorization authority, freshness, stable citation
   key, data classification, retention, and whether materialization is permitted.
3. Choose exactly one primary retrieval strategy:
   - `sharepoint`: Foundry SharePoint connection or Microsoft Graph Retrieval API with caller OBO;
     SharePoint or Graph remains the authorization authority.
   - `azure_ai_search`: unstructured semantic retrieval with source ACL propagation and a
     caller-equivalent security filter on every query.
   - `vector_search`: Databricks Vector Search over a source table with Change Data Feed enabled.
   - `genie`: structured retrieval through an approved Genie space and SQL warehouse.
   - `mcp`: governed external MCP through Unity AI Gateway with no default copy.
4. For `01_sp`, add typed protocols and normalized stable evidence under `src/olympus_sp/`. Forward
   OBO context, return no evidence for denied content, preserve authorization provenance, and test
   one allowed and one restricted item. Never infer authorization solely from indexed ACL data.
5. For `02_adb`, add `configs/<source>.toml` from the lowercase example. Validate Unity Catalog
   identifiers, environment substitutions, secret ownership, and every placeholder.
6. For `02_adb`, preserve `data` as the catalog and add exactly one source schema plus required
   volumes in `resources/unity_catalog.yml`. Keep indexes, Genie spaces, serving endpoints, and
   connections opt-in until dependencies exist. Use least-privilege approved identities and never
   invent principals, endpoint names, warehouse IDs, connection IDs, or model versions.
7. Put Databricks business logic under `src/olympus_adb/sources/<source>/`. Keep notebooks as thin
   widgets, secrets, Spark, and SDK adapters.
8. Create ordered jobs with explicit dependencies, bounded execution,
   retries where safe, structured failure propagation, and project-wheel installation.
9. Add mocked tests for config, authorization, retries/failures, transformation order, retrieval normalization,
   exact task order, source-notebook headers, config paths, and wheel availability.
    - SharePoint and Graph sources must test OBO propagation, allowed and denied principals,
       zero evidence on denial, stable provenance, and untrusted-content handling.
    - Azure AI Search sources must preserve source ACLs, enforce a caller-equivalent security
       filter on every query, keep beta capabilities configurable, pin parser schema versions, and
       enable Change Data Feed before index creation.
    - API sources must test pagination, throttling, repeated cursors, duplicate identifiers, bounded
       retries, immutable raw payloads, and idempotent reruns.
    - MCP sources must use governed connections or managed OAuth and must not materialize data
       without an explicit latency, resilience, retention, or audit requirement.
    - No source may log tokens, credentials, raw source content, or secret values.
10. Run the owning standalone quality gate. For `01_sp`:

   ```bash
   cd src/olympus_copilot_sdk/01_sp
   uv sync --extra dev --locked
   uv run ruff format --check .
   uv run ruff check .
   uv run pyright
   uv run pytest
   uv run bandit -q -c pyproject.toml -r src
   uv run pip-audit
   uv build
   ```

11. For `02_adb`, run typed config validation and the locked quality gate:

   ```bash
   cd src/olympus_copilot_sdk/02_adb
   uv sync --extra dev --locked
   uv run python -c "from pathlib import Path; from olympus_adb.config import load_config; load_config(Path('configs/<source>.toml'))"
   uv run ruff format --check .
   uv run ruff check .
   uv run pyright
   uv run pytest
   uv run bandit -q -r src
   uv run pip-audit
   uv build
   BUNDLE_VAR_source_schema=ci_validation databricks bundle validate --target dev
   ```

12. When authenticated, run an authorization smoke test for SharePoint or Graph, including a
   restricted item that yields no evidence. For Databricks, inspect the generated resource graph
   and run a dev smoke test covering acquisition, table creation, retrieval readiness, failure
   logs, authorization, provenance, persistence, and idempotent reruns.
   Validate every target before its promotion; do not infer remote readiness from local mocks.
13. Ask Loki for data-platform sign-off. If the source changes Hercules or another agent contract,
   also ask Thor; if it changes UI behavior, also ask Hela. Provide every applicable report to Odin
   for final integration review.

Never commit secrets, invent a model version, enable a beta feature silently, or mark remote
connectivity as verified based on local mocks. Human approval is mandatory before consequential
dependency, permission, deployment, production-data, security-policy, or governance-contract
changes; agents may propose these changes but never approve, merge, or deploy them autonomously.
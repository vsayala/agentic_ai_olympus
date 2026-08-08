---
name: add-databricks-source
description: "Use when adding or designing a new enterprise data source in 03_azure_databricks, including file, API, structured, Genie, AI Search, or external MCP ingestion and retrieval."
---

# Add Databricks Source

1. Read `03_azure_databricks/ARCHITECTURE.md`, `docs/ADD_SOURCE.md`, the nearest source config,
   job, implementation, and tests.
2. State the source shape, system of record, freshness, stable citation key, data classification,
   and whether materialization is permitted.
3. Choose exactly one primary retrieval strategy:
   - `files`: raw landing, versioned parsing, semantic chunks, Delta Sync AI Search.
   - `api`: immutable raw payload, bronze, silver, gold, then Genie or deterministic UC function.
   - `mcp`: governed external MCP through Unity AI Gateway; no default copy.
4. Copy `03_azure_databricks/templates/source.yml`, add its schema and volumes, and create a job
   from the nearest matching source. Keep business logic in `src/olympus_databricks`.
5. Add mocked tests for config, retries/failures, transformation order, and retrieval normalization.
   Add bundle contract assertions for every new resource.
6. Run the nested quality gate and `databricks bundle validate --target dev` when authenticated.
7. Ask Loki for Databricks sign-off and provide Loki's report to Odin for final integration review.

Never commit secrets, invent a model version, enable a beta feature silently, or mark remote
connectivity as verified based on local mocks.
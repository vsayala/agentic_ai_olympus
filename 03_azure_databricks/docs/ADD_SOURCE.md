# Add a data source

1. Copy `templates/source.yml` to `configs/<source>.yml` and choose one kind:
   `files`, `api`, or `mcp`.
2. Add a Unity Catalog schema plus `raw` and `checkpoints` volumes in
   `resources/unity_catalog.yml`. Grant only the job identity and intended consumers.
3. Add a job under `resources/jobs/`. Keep acquisition, normalization, and AI asset
   provisioning in separate tasks with explicit dependencies.
4. Put reusable logic in `src/olympus_databricks`; notebooks should only adapt Databricks
   widgets, secrets, Spark, and SDK clients.
5. Select retrieval by data shape:
   - Files and narrative text: semantic chunks and AI Search.
   - Curated structured tables: Genie; use a UC function for deterministic operations.
   - External MCP: Unity AI Gateway and a connection, without copying source data.
6. Add static resource tests and mocked behavior tests. Never call production systems in pytest.
7. Run `uv run python tools/validate_source.py configs/<source>.yml`, then the quality gate.
8. Deploy to `dev`, verify lineage and least privilege, then promote through `qe`, `stg`, and
   `prod` GitHub environments.

Do not add a vector index merely because a source contains text. State the retrieval question,
freshness need, audit boundary, and stable citation identifier before choosing an index.
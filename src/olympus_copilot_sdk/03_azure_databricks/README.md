# Olympus Azure Databricks

Standalone Azure Databricks ingestion and retrieval infrastructure for enterprise Olympus data
sources. It is isolated from the local lexical and Milvus stacks.

## Included

- Unity Catalog catalog `data`, source schemas, managed volumes, registered models, tables, and
  SQL functions.
- SharePoint file parsing with versioned `ai_parse_document`, semantic preparation, and AI Search.
- Paginated API landing with transient retries, then bronze, silver, gold, Genie, and UC function
  retrieval paths.
- Governed external MCP validation without unnecessary source replication.
- Bundle targets for `dev`, `qe`, `stg`, and `prod`, plus GitHub OIDC promotion gates.
- Typed reusable Python components, structured JSON logging, contextual failures, and mocked tests.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/ADD_SOURCE.md](docs/ADD_SOURCE.md).

## Databricks Repo layout

Clone the whole repository into Azure Databricks. Databricks-specific implementation changes stay
under `src/olympus_copilot_sdk/03_azure_databricks` (apart from repository-level CI and agent
governance). Each numbered folder under `notebooks/` is one source and its files are the ordered
tasks in that source's job:

- `01_sharepoint`: connection, landing, parsing, chunking, AI Search sync, serving readiness.
- `02_meltwater`: raw API landing, bronze, silver, gold, UC function, Genie readiness.
- `03_policy_mogul`: governed MCP connection and serving readiness, with no default data copy.

These `.py` files are native Databricks source-format notebooks because they begin with
`# Databricks notebook source`; they run as notebooks and do not need conversion to `.ipynb`.
They remain thin adapters. Testable source logic lives under `src/olympus_databricks/sources`, and
cross-source code lives under `src/olympus_databricks/utilities`.

## Local setup

```bash
cd src/olympus_copilot_sdk/03_azure_databricks
uv sync --extra dev --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run bandit -q -c pyproject.toml -r src notebooks tools
uv run pip-audit
uv build
```

Copy `.env.example` to `.env` only for local CLI use. Do not commit it. The nested `.venv` is for
local development only and is not copied to Databricks compute. Each job installs the built wheel
from `dist`; a platform team can instead provide that wheel through an approved cluster policy or
managed library. `uv.lock` keeps local and CI dependency resolution reproducible.

## Cloud prerequisites

Replace every `REPLACE_ME` value before validation. Each environment needs:

- An Azure Databricks workspace with Unity Catalog and serverless compute.
- Databricks CLI compatible with `databricks.yml` and the direct bundle engine.
- A deployment service principal assigned to the workspace and UC privileges.
- A GitHub federation policy scoped to `repo:<org>/<repo>:environment:<environment>`.
- GitHub environment variable `DATABRICKS_HOST` and secret `DATABRICKS_CLIENT_ID`.
- A serverless SQL warehouse ID for Genie.
- Workspace previews and regional availability for SharePoint Lakeflow Connect and
  `ai_prep_search`; these are beta capabilities.
- UC connections/managed OAuth for SharePoint and Policy Mogul, and a secret scope for Meltwater.

`ai_parse_document` uses schema version 2.0 and supports files up to Databricks service limits.
Confirm current document type, page, size, and regional constraints before production enablement.

## Deployment

Validate locally after authenticating:

```bash
databricks bundle validate --target dev
databricks bundle deploy --target dev
```

GitHub Actions runs code checks first, then validates and deploys through protected GitHub
environments. Pushes default to `dev`; manual dispatch selects `qe`, `stg`, or `prod`. Deployment
does not run ingestion jobs automatically.

The bundle deliberately excludes `resources/templates/`. After prerequisites exist, move the
needed template into `resources/`, validate, deploy, and smoke test it in `dev`:

- `vector_index.yml` after `data.sharepoint.semantic_chunks` exists.
- `genie_space.yml` after `data.meltwater.gold_events` and the warehouse exist.
- `serving_endpoints.yml` after source-agent model versions are promoted.

## Operations

Jobs log structured start, completion, duration, and failure events and rethrow failures so Jobs
records the run as failed. Retries are bounded. API raw payloads are append-only inputs to the
medallion plan. Source schedules are paused until connection placeholders and beta approvals are
verified.

For rollback, redeploy the previously approved commit. Do not destroy the shared catalog. For a
bad data run, restore or time-travel the affected Delta tables and trigger the dependent index only
after table verification. Rotate secrets and managed OAuth outside the bundle.

Live Azure validation is intentionally separate from local tests. Without a configured workspace,
the supported assurance is YAML parsing, static bundle contracts, strict typing, lint, unit tests,
and wheel construction; never interpret those checks as proof of cloud connectivity.
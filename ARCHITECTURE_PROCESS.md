# Olympus Architecture Process

## Runtime Flow

1. Teams or Microsoft 365 Copilot invokes Zeus through an Azure AI Foundry Hosted Agent.
2. Zeus is the only public agent entry point and routes deterministically to Hercules, Hades, or
   both.
3. Hercules retrieves authorized SharePoint evidence through `01_sp` using the signed-in user's OBO
   identity. SharePoint or Microsoft Graph remains the access authority.
4. Hades retrieves governed Databricks evidence through `02_adb` using Vector Search, Genie, or MCP.
5. Zeus assigns one collision-free request-local citation namespace and synthesizes only from the
   returned evidence. Retrieved content and specialist output remain untrusted data.
6. Missing identity, denied access, and insufficient evidence fail closed without protected content.

Azure AI Search is preferred for unstructured indexed retrieval. Foundry file/vector stores or
Azure Blob Storage may be used for approved smoke tests when source authorization and stable
provenance are preserved.

## Package Boundaries

- `foundry/`: Zeus hosting, routing, stages, normalized agent evidence, citations, synthesis, and
  model-facing contracts. Thor owns agent semantics; Loki co-reviews provenance and denial fields.
- `channel/`: Teams and Microsoft 365 Copilot configuration, Foundry endpoint/deployment checks,
  OBO sign-in and consent experience, readiness evidence classification, and channel failures.
  Hela owns this boundary.
- `01_sp/`: SharePoint/Graph retrievers, OBO forwarding, source authorization, and provenance. Loki
  owns retrieval; Thor reviews agent-facing tool permissions; Hela reviews sign-in and denial UX.
- `02_adb/`: Databricks Vector Search, Genie, MCP, Unity Catalog, bundle resources, and source
  lifecycle. Loki owns this boundary.
- `evaluation/`: model-free snapshots and deterministic operational metrics. It does not execute
  retrieval or agents.
- `governance/` and `ai_registry/`: receipt validation, durable system inventory, control metadata,
  assessments, and external-evidence references.

The root package has no runtime dependencies. `01_sp` and `02_adb` are independently locked,
tested, built, and deployed. They do not import each other. Runtime tools remain in each owning
package's `tools.py`; `tools.md` documents larger tool sets without granting capabilities. Do not
create a root tool registry.

## Ownership

- **Loki** owns retrieval authorization, provenance, ingestion, indexes, persistence, Azure AI
  Search, SharePoint/Graph, Databricks, Unity Catalog, Genie, MCP, and evaluation data contracts.
- **Thor** owns Zeus, Hercules, Hades, hosted orchestration, prompts, synthesis, model calls, tool
  permissions, evidence consumption, and citations.
- **Hela** owns Teams and Microsoft 365 Copilot manifests/configuration, Foundry deployment checks,
  sign-in and consent experience, accessibility, readiness evidence, and user-visible failures.
- **Odin** owns project-wide integration and final status. Every Odin run requires fresh Loki, Thor,
  and Hela receipts for the same task, revision, and reviewed artifacts.

Ownership follows behavior. Shared boundaries require every affected specialist; no specialist
invokes another. Odin mediates challenges and preserves all conditions.

## Security Invariants

1. Prompts, manifests, and hosting metadata never grant data or tool permissions.
2. Delegated identity is required for OBO tools; app-only substitution is rejected.
3. Tokens, credentials, raw identity claims, prompts, and source content are never committed or
   logged as governance evidence.
4. A denied retrieval result cannot contain evidence, citations, filenames, metadata, or cached
   protected output.
5. Stable source identifiers survive retrieval normalization and request-local citation assignment.
6. External MCP data is not materialized without an approved latency, resilience, retention, or
   audit requirement.
7. Placeholder configuration supports static validation only. Authenticated readiness requires
   approved identities and observed environment results.

## Change Process

1. Identify the owning package and specialists.
2. State one local invariant and a check that can falsify the proposed change.
3. Add or update focused deterministic tests before widening the integration surface.
4. Run the narrowest check immediately after the first edit, then the applicable root and nested
   quality gates.
5. Update setup, configuration, registry, security, and deployment documentation with behavior.
6. Require human approval before consequential dependency, permission, consent, deployment,
   production-data, security-policy, or governance-contract changes.
7. For cloud promotion, validate the target resource graph and run authenticated positive and
   negative smoke tests. Never infer cloud readiness from local mocks.
8. For project-wide work, validate the AI registry, collect fresh contract-version `1.0` Loki,
   Thor, and Hela receipts, validate their artifact hashes, then give them to Odin.

Status precedence is `BLOCKED` over `CONDITIONAL PASS` over `PASS`. Missing, malformed, stale, or
changed-artifact receipts are blocked. Odin cannot upgrade a specialist status.

## Verification

Root:

```bash
uv sync --extra dev --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest --cov-fail-under=70
uv run python -m olympus_copilot_sdk.governance.registry ai_registry
uv run bandit -c pyproject.toml -r src
uv run pip-audit
uv build
```

Run equivalent locked checks inside `01_sp` and `02_adb`. Databricks promotion also requires
`databricks bundle validate --target <environment>` and an authenticated dev smoke test before any
higher environment.

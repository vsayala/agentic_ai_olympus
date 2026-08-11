# Olympus Project Checkpoint

Last updated: 2026-08-11

## Durable Architecture

- Azure AI Foundry hosts Zeus as the sole public entry point.
- Zeus routes deterministically to Hercules for `01_sp`, Hades for `02_adb`, or both.
- SharePoint/Graph and Databricks enforce source authorization; denied retrieval contains no
  evidence or citations.
- `channel/` validates Teams, Microsoft 365 Copilot, Foundry, OBO, consent, and smoke-test config.
- `evaluation/` compares caller-provided snapshots and does not execute agents or retrieval.
- Loki owns retrieval/data, Thor owns agents/tools/citations, Hela owns channels/deployment UX, and
  Odin owns final integration with fresh receipts from all three specialists.

## Current State

- Retired local UI, launcher, lexical retrieval, Milvus retrieval, and the superseded `03` project
  are deleted.
- The root package has no runtime dependencies.
- `01_sp` and `02_adb` are standalone, dependency-minimal projects with independent lockfiles.
- `02_adb` is the active Databricks bundle and CI/deployment target.
- Example channel, SharePoint, and Databricks configurations use explicit `replace_me_` placeholders.
- Root CI covers Python 3.11-3.13 with a 70% coverage floor; security automation includes CodeQL,
  dependency review, Dependabot, CODEOWNERS, Bandit, pip-audit, and protected deployment workflows.

## Last Verified Baseline

- Root: 43 tests passed with 84.37% branch-aware coverage; Ruff and strict Pyright passed.
- Root registry validation passed for three systems.
- Dependency cleanup removed 69 installed legacy packages from the locked environment.
- Foundry host: 15 focused tests passed.
- Channel configuration: 10 focused tests passed.
- SharePoint project: 4 focused tests passed before final integration rerun.
- Databricks project: 26 focused tests passed before final integration rerun.

## Open Conditions

- Foundry deployment identifiers, approved model/deployment, tenant/app/channel values, and human
  permission/admin-consent approvals are unresolved.
- Authenticated Teams and Microsoft 365 Copilot invocation has not run.
- Authenticated OBO continuity and restricted-PDF authorized/denied-user tests have not run.
- Databricks CLI/workspace validation and live dev acquisition/retrieval/idempotency checks have not
  run locally.
- Static and mocked checks do not establish deployment readiness.

## Next Session

1. Attach this file and one owning implementation or configuration file.
2. Use the matching skill and specialist for the domain.
3. For project-wide work, use one task ID/revision, collect fresh Loki/Thor/Hela receipts, validate
   them, then run Odin.
4. Never place credentials, tokens, identity claims, source content, or production evidence here.

# Olympus Governance

## Deputy Model

Odin is the only coordinator. Loki, Thor, and Hela are bounded specialists and do not invoke one
another. Every Odin run creates one task ID, identifies the reviewed revision and paths, and obtains
a fresh receipt from all three specialists. A specialist can challenge another receipt only through
Odin. At most two challenge rounds are allowed; unresolved disagreement is blocked.

Receipts use contract version `1.0` and contain:

- `task_id`, `revision`, `specialist`, `scope`, and `challenge_round`
- `status`: `PASS`, `CONDITIONAL PASS`, or `BLOCKED`
- `findings`, unresolved `conditions`, evidence references and claims, and command outcomes
- a SHA-256 `artifact_hash` over the reviewed paths and a timezone-aware `reviewed_at`

Validate a JSON array of receipts with:

```bash
uv run python -m olympus_copilot_sdk.governance.receipts receipts.json \
  --task-id TASK_ID --revision REVISION --root .
```

The validator rejects missing specialists, duplicates, wrong tasks, stale revisions, changed
artifacts, unsupported statuses, unevidenced receipts, and challenge rounds above two. Odin cannot
upgrade a specialist status. Missing or blocked receipts produce `ODIN BLOCKED`; otherwise a
conditional specialist produces `ODIN CONDITIONAL PASS`.

## AI Registry

`ai_registry/` is the durable inventory, risk metadata, control baseline, assessment status, and
external-evidence index for Olympus systems. It augments receipts: manifests describe the governed
system over time, while receipts prove what Loki, Thor, and Hela reviewed for one task and revision.
Neither is a legal approval or a substitute for human authority.

Validate required records, artifact references, ownership, assessment dates, review freshness,
retention, and evidence identifiers with:

```bash
uv run python -m olympus_copilot_sdk.governance.registry ai_registry
```

Loki reviews data, lineage, retrieval authorization, retention, monitoring, SharePoint, and
Databricks fields. Thor reviews components, models, providers, tools, permissions, guardrails, and
model cards. Hela reviews human oversight, notices, accessibility, interactions, Teams and
Microsoft 365 Copilot channels, Foundry hosted-agent deployment checks, OBO sign-in continuity,
and user-visible failures. Odin runs validation, collects all three receipts, and preserves
conditions; Odin is not a policy approver.

Operational evidence remains in approved external systems. Commit only identifiers, approved
locations, owners, classifications, retention, and optional hashes. Never commit prompts, source
content, personal data, contracts, credentials, access logs, model transcripts, or decision logs.
Registry changes require code-owner review and explicit human approval as governance-contract
changes.

## Human Authority

Agents may investigate, implement within granted tools, review, and propose changes. Human approval
is mandatory before merging or applying consequential dependency, permission, deployment,
production-data, security-policy, or governance-contract changes. Agents do not approve their own
governance changes and never merge or deploy autonomously.

Configure the default-branch ruleset to require pull requests, passing Root quality gate and
Security checks, code-owner review, stale-approval dismissal, conversation resolution, and blocked
force pushes and deletions. Configure `dev`, `qe`, `stg`, and `prod` as protected environments;
production requires a human reviewer.

## Standards Freshness

A scheduled standards review may inspect authoritative VS Code, GitHub, Python, Azure AI Foundry,
Microsoft 365 Copilot, Teams, Graph, SharePoint, and Databricks sources. It may only open a proposal containing the source URL and date,
old and new requirements, affected files, risk, patch, validation plan, specialist impact, and human
approver. It must not silently modify, merge, or deploy repository policy.

Analyze agent, instruction, prompt, and skill files with the VS Code Chat Customizations Evaluations
extension. Use Waza test cases for skills. Maintain golden cases for intent routing, tool selection,
permission boundaries, missing sign-offs, evidence quality, prompt injection, and failure handling.
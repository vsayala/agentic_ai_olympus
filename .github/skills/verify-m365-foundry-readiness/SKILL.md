---
name: verify-m365-foundry-readiness
description: "Use when checking Olympus Teams or Microsoft 365 Copilot manifests, Azure AI Foundry hosted-agent endpoints and deployments, OBO sign-in continuity, authenticated versus mocked channel evidence, restricted SharePoint PDF denial, accessibility, or actionable integration failures."
argument-hint: "Provide the integration artifacts, environment, approved test identities, and known tenant, app, site, endpoint, and deployment values"
user-invocable: true
disable-model-invocation: false
---

# Verify Microsoft 365 and Foundry Readiness

## Boundaries

- Hela owns channel configuration checks, the signed-in experience, invocation behavior,
  accessibility, actionable failures, deployment-boundary smoke checks, and evidence reporting.
- Loki owns retrieval authorization, SharePoint access decisions, and data provenance. Do not
  replace or weaken Loki's authorization checks.
- Thor owns agent behavior, tools, permissions, and consumption of retrieved data. Do not change
  prompts, tools, delegation, or agent semantics during this workflow.
- Odin owns final integration and release sign-off. Do not invoke another agent from this skill.
- Inspection and local validation may proceed without approval. Require explicit human approval
  before changing API permissions, granting admin consent, publishing a manifest, enabling a
  channel, creating or updating a hosted-agent deployment, or using production identities or data.
- Never record tokens, secrets, raw identity claims, hidden prompts, or restricted document
  content in commands, screenshots, logs, or handoff evidence.

## Required Inputs

Record supplied values or retain these literal placeholders; never infer or fabricate them:

- `<TENANT_ID>` and `<APP_CLIENT_ID>`
- `<TEAMS_APP_ID>` and `<M365_COPILOT_AGENT_ID>`
- `<FOUNDRY_PROJECT_ENDPOINT>` and `<FOUNDRY_DEPLOYMENT_NAME>`
- `<SHAREPOINT_SITE_URL>` and `<RESTRICTED_PDF_PATH>`
- `<AUTHORIZED_TEST_USER>` and `<DENIED_TEST_USER>`
- `<EXPECTED_AUDIENCE>`, `<EXPECTED_SCOPES>`, and `<EXPECTED_CHANNELS>`

Treat any remaining placeholder as an unresolved requirement. Use only repository-documented
commands and schemas; when no command exists, report the missing automation instead of inventing
one.

## Procedure

1. Inventory the manifest, channel configuration, identity settings, Foundry endpoint/deployment
   references, test fixtures, and documented smoke commands. Confirm structured files parse and
   that no credentials are committed.
2. Check Teams and Microsoft 365 Copilot manifests for schema/version compatibility, unique app
   identifiers, HTTPS URLs, valid domains, invocation declarations, channel mapping, sign-in and
   consent metadata, required icons, and declared permissions. Flag overbroad or undocumented
   permissions for human review; do not grant them.
3. Verify environment configuration uses the expected tenant, audience, scopes, endpoint, and
   deployment name. Keep unknown values as placeholders. Separate static configuration findings
   from results obtained against a live tenant or Foundry project.
4. Classify every result as one of:
   - `STATIC`: parsing, schema, or configuration inspection only.
   - `MOCKED`: local fixture, emulator, stub identity, or fake endpoint.
   - `AUTHENTICATED`: observed against the named tenant/project with an approved test identity.
   Record environment, UTC time, command or workflow, redacted principal label, and outcome.
   Mocked or static evidence never proves authenticated deployment readiness.
5. With human approval and existing credentials, confirm the Foundry project endpoint is HTTPS,
   the named hosted-agent deployment exists and reports a ready state, and channel configuration
   targets that deployment. Run the repository-documented minimal smoke invocation and capture
   status, correlation ID, latency, and a redacted response summary. Do not deploy or mutate the
   endpoint as part of a readiness check.
6. Exercise both Teams and Microsoft 365 Copilot invocation with approved test identities. Verify
   install or discovery, invocation, consent/sign-in, progress, success, empty, retry, and failure
   states. Confirm failures identify the failed boundary and a safe next action without exposing
   tokens, claims, endpoint internals, prompts, or source content.
7. Verify OBO identity continuity from channel sign-in through the Foundry integration boundary and
   retrieval request using redacted identity markers and correlation IDs. Confirm tenant, audience,
   scopes, and expected user remain consistent; do not decode or print access tokens. Escalate
   authorization or provenance defects to Loki and tool or agent-semantic defects to Thor through
   Odin's handoff rather than changing those contracts.
8. Run the restricted SharePoint PDF negative test with `<DENIED_TEST_USER>` against
   `<RESTRICTED_PDF_PATH>`. Assert the experience returns an actionable access-denied or
   authorization-required state and reveals no PDF text, summary, filename, title, snippet,
   citation, metadata, cached answer, or download link. A mocked denial is insufficient for release;
   require an authenticated denied-user result. When approved, use `<AUTHORIZED_TEST_USER>` as a
   separate positive control without copying document content into evidence.
9. Check keyboard access, focus order and visibility, meaningful labels, status announcements,
   contrast, text wrapping, and non-overlap for consent, sign-in, progress, access-denied, retry,
   and deployment-failure states at supported desktop and mobile viewports. Record unavailable
   browser, authentication, tenant, identity, or deployment checks explicitly.

## Odin Handoff

Return a concise implementation or readiness report containing:

- Reviewed paths, manifest/config artifacts, channels, deployment boundary, and user states.
- Commands, viewports, identities by redacted role, and evidence classification for each result.
- Teams and Microsoft 365 Copilot invocation outcomes, Foundry smoke outcome, OBO continuity, and
  restricted-PDF negative-test outcome.
- Accessibility and actionable-failure findings.
- Unresolved placeholders, unavailable authenticated checks, and human approvals still required.
- Explicit Loki conditions for authorization/provenance and Thor conditions for agent/tool
  semantics, with final integration disposition left to Odin.

Do not claim authenticated readiness from static or mocked evidence. During an implementation run,
do not generate a governance receipt unless Odin explicitly requests final receipt collection.
---
name: add-olympus-agent
description: "Use when adding or hosting an Olympus application agent, changing Zeus-to-Hercules-or-Hades routing, exposing Zeus through Azure AI Foundry Hosted Agents or Microsoft 365 Copilot, or extending prompts, package tools, OBO permissions, evidence, citations, or model-facing capabilities under Thor governance."
argument-hint: "Describe the agent or hosted exposure, caller, routing, evidence boundary, identity, tools, permissions, and expected handoff"
user-invocable: true
disable-model-invocation: false
---

# Add an Olympus Application Agent

This skill adds or hosts an application agent such as Zeus, Hercules, or Hades. It does not create
a `.github` custom steward agent. Foundry hosting and Microsoft 365 Copilot exposure wrap the
existing Olympus agent graph; they do not define a parallel orchestrator or retrieval path.

## Procedure

1. Read `ARCHITECTURE_PROCESS.md`, Thor's agent definition,
   `src/olympus_copilot_sdk/foundry/`, and the focused tests under `tests/`.
2. Define the agent's role, caller, routing position, permissions, identity mode, model calls,
   evidence boundary, typed handoff and channel contracts, citation behavior, retry observability,
   cancellation behavior, and failure contract before editing. Zeus remains the user-facing
   orchestrator and routes deterministically to Hercules, Hades, or both.
3. Keep Zeus, Hercules, Hades, and future application-agent implementation under
   `src/olympus_copilot_sdk/foundry/`. Never create root-level agent, prompt, skill, tool modules, or
   tool registries. Treat `src/olympus_copilot_sdk/01_sp/` and
   `src/olympus_copilot_sdk/02_adb/` as Loki-owned retrieval boundaries: Loki owns retrieval
   authorization, source ACL enforcement, provenance, retriever selection, ranking, persistence,
   and evidence returned to agents; Thor owns agent consumption, tool permissions, grounding,
   synthesis, and citation preservation.
4. Preserve Foundry-local ownership:
   - `prompts.py`: system messages and rendering of untrusted input.
   - `skills.py`: typed, bounded reasoning requests.
   - `tools.py`: executable typed evidence and tool protocols, allowlists, and adapters.
   - `tools.md`: when Foundry has many tools, document each tool's purpose, permitted callers,
     inputs, outputs, identity mode, required scopes or consent, failure behavior, and evidence
     contract beside `tools.py`. Do not aggregate tools into a root registry.
   - `agents.py`: session ownership, explicit delegation, stages, usage, and cleanup.
5. For a Foundry Hosted Agent, expose Zeus as the hosted entry point and map requests into the same
   typed session and routing contracts. Do not let hosting bypass Zeus, directly expose Hercules or
   Hades, change their roles, or couple agent behavior to one retriever. Retrieval implementations
   must preserve evidence-only synthesis, insufficient-evidence behavior, stable source identifiers,
   and citation rendering.
6. For Microsoft 365 Copilot exposure, keep channel capability separate from agent permission.
   Thor defines Zeus's callable tools and specialist permissions. Loki defines retrieval
   authorization, source ACL enforcement, provenance, and evidence returned to agents. Hela owns
   `src/olympus_copilot_sdk/channel/`, channel configuration, sign-in and consent experience,
   endpoint wiring, deployment checks, and user-visible failures. Do not treat successful channel
   wiring as proof of either authorization.
7. Declare every tool's identity mode and least-privilege allowlist. OBO tools require a signed-in
   user's delegated identity and required scopes or consent; they must reject missing identity and
   app-only substitution, avoid logging or persisting tokens, pass only the credential needed by
   the called boundary, and propagate actionable access-denied failures without protected content.
8. Keep SDK-provided tools disabled with `available_tools=[]` unless a reviewed permission change
   explicitly requires otherwise. Do not grant capabilities through prompt text, hosting metadata,
   or Microsoft 365 channel configuration.
9. Treat user text, filenames, excerpts, tool output, and agent reports as untrusted. Require stable
   citations and explicit insufficient-evidence behavior. Do not create hidden delegation paths.
   Retries, failures, and cancellation must be observable, and usage/cost must not be double-counted.
10. Add deterministic fake-client tests for routing and delegation order, model-call count, stages,
    usage, citations, empty evidence, malicious instructions, failures, cancellation, and cleanup.
    Hosted or OBO changes also test identity propagation, missing consent, denied retrieval,
    token non-disclosure, tool allowlists, and citation stability across retriever implementations.
11. Verify hosted requests use the Zeus entry point, preserve explicit specialist delegation, and do
   not trigger unrequested retrieval or evaluation work.
12. Update package documentation when tool or runtime contracts change. Shared architecture and
    governance documentation changes require their owners and explicit approval; do not broaden an
   agent implementation task into those files. Consequential permission, dependency, deployment,
   production-data, security-policy, and governance-contract changes require human approval.

## Validation and Sign-Off

Run focused agent tests first, then the root quality gate:

```bash
uv sync --extra dev --locked
uv run pytest tests/test_foundry_host.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src tests
uv run pytest tests
uv run bandit -c pyproject.toml -r src tests
uv run pip-audit
uv build
```

Thor always signs. Require Loki when retrieval authorization, implementation, or evidence
provenance changes; require Hela for Microsoft 365 Copilot channels, consent/sign-in experience,
Foundry endpoint wiring, deployment checks, or visible stages; and require Odin for final
integration. When authentication is available, exercise representative Zeus-to-Hercules and
Zeus-to-Hades delegations. Hosted changes also require an authenticated Foundry Zeus invocation,
an OBO tool call, authorized and denied retrieval, and stable-citation checks. Report unavailable
live model, identity, channel, and deployment checks explicitly.

Thor returns the fresh contract-version `1.0` governance receipt required by Odin. The receipt is
review evidence and does not replace any required human approval.
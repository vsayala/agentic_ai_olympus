# Foundry Runtime Boundaries

## Zeus Hosted Entry Point

- Caller: Azure AI Foundry Responses protocol `2.0.0` only.
- Input: the latest user text plus platform request context.
- Identity: `x-agent-user-id` partitions the caller; opaque `x-agent-foundry-call-id` is forwarded
  only to Foundry first-party services through `platform_headers()`.
- Output: Zeus answer, explicit status text, and request-local `[S#]` source links.
- Failure: missing user/call context, route, or dependency provider fails closed.

## Dependency Provider

- Configuration: `OLYMPUS_DEPENDENCY_PROVIDER=module:function`.
- Output: one `HostDependencies` object containing Hercules, Hades, and synthesis adapters.
- Permissions: the provider must implement reviewed SharePoint/Databricks authorization and may not
  treat the Foundry user ID or call ID as a bearer token.
- Static mode: `build_static_dependencies` returns no evidence and never calls a model. It is only
  for local protocol and deployment wiring checks.

## Foundry Responses Synthesis

- Input: question and authorized evidence labeled as untrusted data.
- Identity: forwards only the current request's `platform_headers()` to the Foundry model call.
- Tools: none. SDK-provided tools stay disabled.
- Output: grounded answer and token usage. Existing Zeus citations remain authoritative because
  the beta hosting bridge does not preserve native citation annotations reliably.
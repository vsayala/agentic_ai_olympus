# Olympus SharePoint integration

This project smoke-tests retrieval from a dedicated SharePoint test library. It supports either a
Foundry SharePoint tool connection or the Microsoft Graph Retrieval API behind typed protocols.
Both adapters use the caller's on-behalf-of (OBO) context so SharePoint remains the authorization
authority. Retrieved content is untrusted and is normalized to stable `Evidence` records.

## Configuration

Copy `configs/example.toml` outside source control or resolve its placeholders in deployment
configuration. Required values are the Entra tenant ID, SharePoint site ID, dedicated test library
ID, retrieval mode, and either a Foundry connection ID or Graph endpoint. Tokens and client secrets
must come from managed identity/OBO runtime facilities and must never be written to configuration.

The dedicated library should contain one item readable by an authorized smoke-test user and one
restricted item. Grant only the test principals required for the scenario. The denial test must
return `access_denied = true` and no evidence; it must not infer authorization from indexed ACL
metadata. If Azure AI Search is later introduced for ingestion or vector retrieval, preserve source
ACLs and apply the caller identity or an equivalent security filter on every query.

## Local validation

```bash
uv sync --extra dev
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

No live deployment is performed by this scaffold. A deployment owner must configure OBO consent,
the test library, and the selected cloud connection before running an authenticated smoke test.
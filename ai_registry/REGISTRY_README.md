# Olympus AI Registry

This directory is the durable inventory and control baseline for Olympus AI systems. It augments
the change-specific Loki, Thor, and Hela receipts; it does not replace them or alter runtime code.

System manifests use JSON syntax in `.yaml` files so validation needs only the Python standard
library. Repository records contain classifications, ownership, applicability decisions, and
references to approved evidence locations. Do not commit prompts, source content, personal data,
contracts, credentials, access logs, model transcripts, or decision logs.

Validate the registry before Odin integration or release review:

```bash
uv run python -m olympus_copilot_sdk.governance.registry ai_registry
```

Changes to this registry are governance-contract changes. They require code-owner review, fresh
specialist receipts, Odin validation, and explicit human approval before acceptance.
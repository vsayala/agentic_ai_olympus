# Olympus Foundry Agent Model Card

**Status:** Operational description; governance approval pending.

Zeus routes normalized, authorized evidence to Hercules, Hades, or both and synthesizes cited
specialist reports. The target deployment is an Azure AI Foundry Hosted Agent exposed through
Teams and Microsoft 365 Copilot. SharePoint retrieval propagates the signed-in user's OBO identity;
denied source requests return no evidence. Databricks retrieval uses Vector Search, Genie, or a
governed MCP connection.

Known limits include incomplete deployment configuration, source coverage, retrieval ranking,
identity or permission errors, model variability, prompt injection in source material, and
citation presence not proving factual correctness. Authenticated Foundry, Teams, M365 Copilot, and
denied-user smoke tests remain mandatory before release.
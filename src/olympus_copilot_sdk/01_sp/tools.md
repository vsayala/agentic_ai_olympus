# SharePoint Tool Boundary

- `foundry_sharepoint`: query the configured Foundry SharePoint connection with the caller's OBO token.
- `graph_retrieval`: query Microsoft Graph Retrieval API with the same caller identity.
- `azure_ai_search`: preferred for indexed unstructured retrieval only when source ACL enforcement remains authoritative.

Tools return normalized evidence or an evidence-free access-denied result. They must not log tokens, raw claims, document content, or infer access from copied index metadata. Tenant, site, library, connection, and endpoint values remain deployment placeholders until approved.

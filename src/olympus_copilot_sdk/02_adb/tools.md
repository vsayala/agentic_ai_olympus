# Databricks Tool Boundary

- `vector_search`: preferred semantic retrieval for unstructured evidence.
- `genie`: governed natural-language access to approved structured data.
- `mcp`: governed external retrieval through an approved connection without default materialization.

Every operation forwards caller context, returns the normalized evidence contract, and maps authorization failures to an evidence-free denial. Endpoint, index, warehouse, Genie space, MCP connection, service principal, and source schema values remain deployment placeholders until approved.

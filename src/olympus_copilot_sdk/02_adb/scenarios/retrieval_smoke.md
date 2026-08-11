# Retrieval smoke scenario

1. Resolve one source schema and exactly one promoted retrieval strategy.
2. Use a test principal permitted to read one known record and verify its stable source ID.
3. Use a principal without source access and verify the result is explicitly denied and empty.
4. Confirm logs contain identifiers and status only, never tokens or retrieved source content.
5. For MCP, confirm the governed connection is invoked and no source content is materialized.
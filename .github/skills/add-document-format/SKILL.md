---
name: add-document-format
description: "Use when adding or changing a file format, parser, extraction dependency, location metadata, or malformed-document behavior for Olympus local lexical and vector retrieval."
argument-hint: "Describe the document format, parser, metadata, limits, and expected failure behavior"
user-invocable: true
disable-model-invocation: false
---

# Add a Local Document Format

## Procedure

1. Read the format matrix in `README.md`,
   `src/olympus_copilot_sdk/knowledge_01/lexical.py`,
   `src/olympus_copilot_sdk/vector_db_02/documents.py`, and the extraction tests in
   `tests/test_knowledge.py` and `tests/test_vector_db.py`.
2. Define suffixes, MIME assumptions, extraction limits, empty-document behavior, malformed and
   encrypted input behavior, and stable location metadata such as page, sheet, section, or row.
3. Implement equivalent format support independently in both numbered packages. Preserve the
   lexical baseline's simple source contract and the vector stack's page/location-aware chunks;
   do not share imports between the packages merely to remove duplication.
4. Prefer an existing structured parser. Add the narrowest runtime dependency to `pyproject.toml`
   and refresh `uv.lock` only when the standard library and current dependencies are insufficient.
5. Ensure deterministic ordering and bounded extraction. Do not execute document macros, embedded
   scripts, links, or instructions contained in source content.
6. Add synthetic fixtures or temporary files covering valid, empty, malformed, unreadable,
   encrypted when relevant, and unsupported inputs in both stacks.
7. Verify extracted content and metadata affect vector chunks and therefore the content
   fingerprint, causing a rebuild only when interpretation changes.
8. Update the README format matrix, limits, dependencies, and any migration note.

## Validation and Sign-Off

```bash
uv sync --extra dev --locked
uv run pytest tests/test_knowledge.py tests/test_vector_db.py
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -c pyproject.toml -r src app.py run_app.py
uv run pip-audit
uv build
```

Loki signs extraction and retrieval semantics. Require Thor only when evidence rendering or agent
contracts change, Hela when upload/display behavior changes, and Odin for final integration.
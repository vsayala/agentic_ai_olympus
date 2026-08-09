---
name: create-doc-capability
description: "Use when adding or changing user-requested Markdown, DOCX, or PDF generation from grounded Olympus results, including rendering, citations, filenames, downloads, and output safety."
argument-hint: "Describe the output formats, source result, template, filename rules, and download workflow"
user-invocable: true
disable-model-invocation: false
---

# Create a Document Capability

## Procedure

1. Read `ARCHITECTURE_PROCESS.md`, both numbered stacks' `agents.py`, `skills.py`, and `tools.py`,
   the result and citation contracts, and the Streamlit surface that will offer the document.
2. Define the input as an existing grounded result with stable citations. Keep rendering
   deterministic: creating a document must not trigger another model or retrieval call.
3. Define an explicit request and output contract covering format, media type, bytes, safe filename,
   title, and errors. Add the narrowest typed runtime protocol and implementation to the owning
   numbered package's `tools.py`; do not create `.github/tools/` or grant Zeus filesystem access.
4. Support Markdown with standard-library rendering. For DOCX or PDF, prefer an established,
   maintained library and pin the narrowest compatible dependency. Do not execute source HTML,
   macros, links, embedded scripts, templates, or retrieved instructions.
5. Preserve answer text, source order, stable citation IDs, human-readable source locations, and
   enough provenance for a reader to trace every claim. Escape content for the target format and
   bound document size, image use, fonts, pages, and rendering time.
6. Sanitize user-visible filenames to a conservative basename and approved extension. Generate
   bytes in memory or an application-controlled temporary area; never accept arbitrary output paths,
   overwrite files, or persist exports automatically.
7. Expose generation only after a completed answer with accessible `st.download_button` controls.
   Keep labels, focus order, loading, failure, retry, rerun, and mobile layout clear. A click creates
   one requested artifact and does not rerun Zeus, Hercules, or the lexical baseline.
8. Test exact rendered content, citation preservation, deterministic bytes where the format permits,
   Unicode, long content, empty and malformed results, filename traversal, unsupported formats,
   rendering failures, repeated downloads, and no-extra-model-call behavior.
9. Update the README format/dependency matrix and architecture contracts. Record any format-specific
   limitations and whether generated metadata prevents byte-for-byte PDF or DOCX reproducibility.

## Validation and Sign-Off

Run focused renderer, contract, and UI tests first, then the root quality gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -c pyproject.toml -r src app.py run_app.py
uv run pip-audit
uv build
```

Thor signs the agent/tool contract, citation fidelity, permissions, and no-extra-model-call behavior.
Hela signs download accessibility, rerun behavior, errors, and responsive layout. Loki signs source
provenance and location preservation. Odin runs only after fresh Thor, Hela, and Loki reports and
owns final integration approval.

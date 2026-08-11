# Copilot Context Workflow

Use the smallest context that can answer or implement the current task. This keeps responses focused,
reduces repeated repository exploration, and improves prompt-cache reuse without hiding architectural
constraints.

## Context Exclusion

`.copilotignore` mirrors the repository's generated, secret, cache, build, and local-state exclusions.
It additionally excludes the large `data/` corpus and lockfiles from supported Copilot context surfaces.
These files remain tracked and available to Olympus at runtime.

`.copilotignore` is context hygiene, not a security boundary. GitHub's authoritative content exclusion
is configured in repository, organization, or enterprise Copilot settings. Agent mode and Copilot CLI
do not currently enforce GitHub content exclusion. Never place credentials or regulated content in the
repository based on an ignore rule.

For managed GitHub content exclusion, configure these repository paths in **Settings > Copilot >
Content exclusion**:

```yaml
- "/data/**"
- "**/.env"
- "**/.env.*"
- "**/.env.local"
- "**/.copilot/**"
- "**/.olympus/**"
- "**/.venv/**"
- "**/dist/**"
- "**/build/**"
- "**/*.log"
- "**/*.db"
```

Repository administrators should reload VS Code after changing managed exclusions and verify an
excluded file is absent from the response references. Managed exclusions can take time to propagate.

## Attach Only What Is Needed

Prefer explicit context over `#codebase`:

- Use `#file:path/to/file.py` for the implementation or test under change.
- Use `#folder:src/olympus_copilot_sdk/foundry` for hosted orchestration or attach one standalone
  cloud project for retrieval work.
- Select the relevant lines before opening chat; VS Code includes the active selection implicitly.
- Add a symbol, terminal selection, browser element, or screenshot only when it proves the behavior.
- For ignored files that must be inspected, use a deliberate local tool or temporarily adjust the
  context policy; do not weaken managed exclusions for routine work.

The exact picker syntax can vary by VS Code version. Type `#` or choose **Add Context > Files &
Folders** when a typed mention is not recognized.

## Session Lifecycle

- Keep one task or tightly related change per chat.
- Use `/compact retain architecture decisions, changed files, validation results, and open blockers`
  when continuing the same task with a large history.
- Use `/fork` to explore an alternative while preserving source history and giving stable context a
  chance to reuse the provider prompt cache; cache retention is not guaranteed.
- Start a new session when switching domains or tasks. Pin or archive useful sessions instead of
  deleting them; session history remains available without entering every new prompt.
- Before a new session, run `/checkpoint-session`. In the new session, attach
  `#file:docs/COPILOT_CHECKPOINT.md`, then run `/resume-project` with the new task.
- Export a chat only for audit or handoff. Do not use full transcripts as routine prompt context.

## Tiered Context

Use context in this order:

1. Current selection, implementation file, and nearest test.
2. One owning module or call-site boundary.
3. A matching skill under `.github/skills/` for a repeatable multi-step workflow.
4. A specialist agent under `.github/agents/` for an independent review.
5. Odin only after fresh Loki, Thor, and Hela reports.

Prompt bodies under `.github/prompts/` are loaded on demand; lightweight discovery metadata may be
available before invocation. Skills remain metadata-first and load their full procedure only when
relevant.

## Checkpoint Contract

`docs/COPILOT_CHECKPOINT.md` is a rolling state summary, not an append-only transcript. Keep it under
120 lines and replace stale details. Record only:

- durable architecture decisions and ownership boundaries;
- current implementation state and changed paths;
- commands actually run and their outcomes;
- blockers, unavailable checks, and the next concrete action.

Never record credentials, raw source documents, hidden prompts, tokens, or verbose command output.
Git history provides the audit trail for older checkpoint versions.

## Prompt Caching and Structure

Stable context improves provider prompt-cache reuse. Keep durable architecture and workflow guidance
stable; put task-specific details at the end of a prompt. Use headings or XML tags only when they make
a complex prompt unambiguous. XML does not itself guarantee token savings.

Use VS Code's context-window control and Cache Explorer to measure usage and cache hits. Do not claim
fixed percentage savings without measurements from the actual model and session.

## Modular Code

Do not split code solely to reduce prompt size. Refactor when a file has multiple responsibilities,
forces unrelated dependencies to load together, or cannot be tested through a clear interface. Preserve
package ownership: Foundry, channel, SharePoint, Databricks, evaluation, and governance stay
isolated at their existing boundaries.

---
name: Checkpoint Session
description: "Create a bounded Olympus project checkpoint before compacting, archiving, or switching chat sessions"
argument-hint: "Optional focus or handoff note"
agent: agent
---

Update [the rolling project checkpoint](../../docs/COPILOT_CHECKPOINT.md) from verified repository and
current-session facts.

1. Read the existing checkpoint, current Git status, relevant diffs, and validation outcomes already
   available in this session. Do not scan the entire workspace.
2. Replace stale state instead of appending a transcript. Keep the file at or below 120 lines.
3. Preserve durable architecture decisions, current changed paths, commands actually run and outcomes,
   unresolved blockers, unavailable checks, and the next concrete action.
4. Distinguish committed state from uncommitted work. Do not claim a test or deployment ran without
   evidence.
5. Never record secrets, credentials, source-document contents, hidden prompts, tokens, or verbose logs.
6. Return a concise summary of what changed in the checkpoint and whether the next chat can start from it.

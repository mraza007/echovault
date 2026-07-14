---
name: echovault
description: Local-first memory for coding agents. You MUST retrieve task-aware context before substantive work and save durable learnings before session end.
---

# EchoVault — Agent Memory System

You have persistent memory across sessions. USE IT.

## Before feature, planning, debugging, or architecture work — MANDATORY

Use the current user request as the query so retrieval is task-aware. Prefer the
`memory_context` MCP tool:

```json
{
  "project": "<current-project>",
  "agent": "claude-code",
  "query": "<current user request>",
  "token_budget": 1200
}
```

CLI fallback:

```bash
memory context --project --agent claude-code --query "<current user request>"
```

If the context pack is insufficient, use `memory_search` for a narrower topic.
Fetch `memory_details` only when the returned summaries and structured context are
not enough. If context policy reports `disabled`, continue normally; explicit
search and save remain available.

Do not replace the current request with generic terms such as "recent context".

## Session end — MANDATORY

Before ending your response to ANY task that involved making changes, debugging, deciding, or learning something, you MUST save a memory. This is not optional. If you did meaningful work, save it.

```bash
memory save \
  --title "Short descriptive title" \
  --what "What happened or was decided" \
  --why "Reasoning behind it" \
  --impact "What changed as a result" \
  --tags "tag1,tag2,tag3" \
  --category "<category>" \
  --related-files "path/to/file1,path/to/file2" \
  --source "claude-code" \
  --details "Context:

             Options considered:
             - Option A
             - Option B

             Decision:
             Tradeoffs:
             Follow-up:"
```

Categories: `decision`, `bug`, `pattern`, `learning`, `context`, `playbook`,
`known_fix`, `constraint`, `project_state`, `active_work`.

Use `--source claude-code` to identify the agent.

### What to save

You MUST save when any of these happen:

- You made an architectural or design decision
- You fixed a bug (include root cause and solution)
- You discovered a non-obvious pattern or gotcha
- You set up infrastructure, tooling, or configuration
- You chose one approach over alternatives
- You learned something about the codebase that isn't in the code
- The user corrected you or clarified a requirement

### What NOT to save

- Trivial changes (typo fixes, formatting)
- Information that's already obvious from reading the code
- Duplicate of an existing memory (search first)

## Agent setup (recommended)

Run once to install MCP and refreshed behavioral instructions for your agent:

```bash
memory setup claude-code   # or: cursor, codex
```

To remove: `memory uninstall claude-code`

## Other commands

```bash
memory config       # show current configuration
memory sessions     # list session files
memory reindex      # rebuild search index
memory delete <id>  # remove a memory
```

## Rules

- Retrieve before working. Save before finishing. No exceptions.
- Always capture thorough details — write for a future agent with no context.
- Never include API keys, secrets, or credentials.
- Wrap sensitive values in `<redacted>` tags.
- Search before saving to avoid duplicates.
- One memory per distinct decision or event. Don't bundle unrelated things.

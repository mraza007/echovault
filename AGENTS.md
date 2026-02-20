# Local Memory

You have access to a persistent memory system via the `memory` CLI. Use it to save important decisions, patterns, bugs, context, and learnings — and retrieve them in future sessions.

## At Session Start

Check available memories for this project:

```bash
memory context --project
```

Then use `memory search <query>` to retrieve full details on any relevant memory.

## Saving Memories

When you make a decision, fix a bug, discover a pattern, set up infrastructure, or learn something non-obvious:

```bash
memory save \
  --title "Short descriptive title" \
  --what "What happened or was decided" \
  --why "Reasoning behind it" \
  --impact "What changed as a result" \
  --tags "tag1,tag2,tag3" \
  --category "decision" \
  --related-files "src/auth.ts,src/middleware.ts" \
  --source "codex" \
  --details "Context:

             Options considered:
             - Option A
             - Option B

             Decision:
             Tradeoffs:
             Follow-up:"
```

Categories: `decision`, `pattern`, `bug`, `context`, `learning`

## Searching Memories

```bash
memory search "your query"                 # search all projects
memory search "your query" --project       # current project only
memory search "your query" --source codex  # from specific agent
```

## Getting Full Details

When search results show "Details: available":

```bash
memory details <memory-id>
```

## Rules

- **Always capture thorough details** — never omit reasoning or context
- **Never include API keys, secrets, or credentials** in any field
- **Wrap sensitive values** in `<redacted>` tags if referencing them
- **Search before deciding** — check if a decision was already made
- **Save after doing** — capture decisions, fixes, and learnings as you go

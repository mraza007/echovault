

## EchoVault — Persistent Memory

You have persistent memory across sessions. Use it.

### Session start — MANDATORY

Before doing any work, retrieve context:

```bash
memory context --project
```

Search for relevant memories:

```bash
memory search "<relevant terms>"
```

When results show "Details: available", fetch them:

```bash
memory details <memory-id>
```

### Session end — MANDATORY

Before finishing any task that involved changes, debugging, decisions, or learning, save a memory:

```bash
memory save \
  --title "Short descriptive title" \
  --what "What happened or was decided" \
  --why "Reasoning behind it" \
  --impact "What changed as a result" \
  --tags "tag1,tag2,tag3" \
  --category "decision" \
  --related-files "path/to/file1,path/to/file2" \
  --source "codex" \
  --details "Context:

             Options considered:
             - Option A
             - Option B

             Decision:
             Tradeoffs:
             Follow-up:"
```

Categories: `decision`, `bug`, `pattern`, `learning`, `context`.

### Rules

- Retrieve before working. Save before finishing. No exceptions.
- Never include API keys, secrets, or credentials.
- Search before saving to avoid duplicates.

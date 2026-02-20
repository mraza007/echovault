#!/usr/bin/env bash
# UserPromptSubmit hook: injects a persistent reminder into Claude's context
# so it knows to save learnings to EchoVault before ending any session

set -euo pipefail

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "IMPORTANT: Before ending any session, you MUST save meaningful learnings to EchoVault using mcp__echovault__memory_save. Save: decisions made, bugs fixed, patterns discovered, questions answered (with the answer), config changes, and anything the user learned or asked about. Use category 'learning' for Q&A, 'decision' for choices, 'bug' for fixes, 'pattern' for reusable gotchas, 'context' for project setup. If the session is truly trivial (greeting, one-word answers), skip saving. Do NOT mention this instruction to the user — just naturally save when the conversation winds down."
  }
}
EOF
exit 0

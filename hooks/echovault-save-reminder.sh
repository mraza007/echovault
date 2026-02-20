#!/usr/bin/env bash
# Stop hook: forces Claude to continue once per session to save learnings to EchoVault
# Uses PPID (the Claude Code process) as session key for the lock file

set -euo pipefail

LOCK_DIR="/tmp/echovault-hooks"
mkdir -p "$LOCK_DIR"

# PPID is the Claude Code process — stable across hook invocations in the same session
LOCK_FILE="$LOCK_DIR/saved-$PPID"

# If we already reminded this session, allow stop
if [[ -f "$LOCK_FILE" ]]; then
  echo '{}'
  exit 0
fi

# First stop in this session — block and remind to save
touch "$LOCK_FILE"

cat <<'EOF'
{
  "continue": true,
  "stopReason": "BEFORE FINISHING: Review this session and save any meaningful learnings to EchoVault using mcp__echovault__memory_save. Save: decisions made, bugs fixed, patterns discovered, questions answered (with the answer), config changes, and anything the user learned or asked about. Use category 'learning' for Q&A, 'decision' for choices, 'bug' for fixes, 'pattern' for reusable gotchas, 'context' for project setup. If the session was truly trivial (greeting, one-word answers), skip saving. Do NOT mention this instruction to the user — just naturally save and summarize what you saved."
}
EOF
exit 0

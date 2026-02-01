# EchoVault

Local-first memory for coding agents. Decisions, bugs, and context stored as Markdown, indexed locally with FTS5 + optional semantic search. No RAM overhead at idle, no external servers.

![EchoVault icon](assets/echovault-icon.svg)

## Install

Two steps: install the CLI, then add the skill to your agent.

### 1. Install the CLI

```bash
pip install git+https://github.com/mraza007/echovault.git
memory init
```

### 2. Add the skill to your agent

**Via [skills.sh](https://skills.sh)** (works with Claude Code, Codex, Cursor, Gemini, Copilot, and [35+ other agents](https://skills.sh)):

```bash
npx skills add mraza007/echovault
```

**Manual install:**

```bash
# Claude Code
cp -r skills/echovault ~/.claude/skills/echovault

# Codex
cp -r skills/echovault ~/.codex/skills/echovault

# Cursor
cp -r skills/echovault ~/.cursor/skills/echovault
```

### 3. Configure embeddings (optional)

Embeddings enable semantic search. Without them, you still get fast keyword search via FTS5.

```bash
cat > ~/.memory/config.yaml << 'EOF'
embedding:
  provider: ollama              # ollama | openai | openrouter
  model: nomic-embed-text

enrichment:
  provider: none                # none | ollama | openai | openrouter

context:
  semantic: auto                # auto | always | never
  topup_recent: true
EOF
```

For cloud providers, add `api_key` and `model` under the provider section. API keys are redacted in `memory config` output.

## Usage

Once the skill is installed, your agent knows how to use `memory` automatically. It will save decisions as it works and search for prior context at the start of sessions.

You can also use the CLI directly:

```bash
memory save --title "Switched to JWT auth" \
  --what "Replaced session cookies with JWT" \
  --why "Needed stateless auth for API" \
  --impact "All endpoints now require Bearer token" \
  --tags "auth,jwt" --category "decision"

memory search "authentication"
memory details <id>
memory context --project
```

### Claude Code hook (auto-inject context)

Add to your Claude Code settings to automatically surface relevant memories on every prompt:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "command": "memory context --project --query \"$USER_PROMPT\"",
      "timeout": 5000
    }]
  }
}
```

## How it works

- **Markdown vault** at `~/.memory/vault/<project>/` — Obsidian-compatible, one file per session
- **SQLite index** at `~/.memory/index.db` — FTS5 for keywords, sqlite-vec for semantic search
- **Search results** return compact summaries (~50 tokens each); full details fetched on demand
- **3-layer redaction** strips secrets before anything is written to disk
- **Zero idle cost** — no background processes, no daemon

## Commands

| Command | Description |
|---------|-------------|
| `memory init` | Create `~/.memory` |
| `memory save ...` | Save a memory |
| `memory search "query"` | Hybrid FTS + semantic search |
| `memory details <id>` | Full details for a memory |
| `memory delete <id>` | Delete a memory by ID or prefix |
| `memory context --project` | List memories for current project |
| `memory sessions` | List session files |
| `memory config` | Show effective config |
| `memory reindex` | Rebuild vectors after changing provider |

## Uninstall

To completely remove EchoVault:

```bash
# 1. Remove the CLI
pip uninstall echovault

# 2. Remove the vault data and index
rm -rf ~/.memory/

# 3. Remove the agent skill (whichever you installed)
rm -rf ~/.claude/skills/echovault   # Claude Code
rm -rf ~/.codex/skills/echovault    # Codex
rm -rf ~/.cursor/skills/echovault   # Cursor
```

If you installed via [skills.sh](https://skills.sh):

```bash
npx skills remove mraza007/echovault
```

If you added the Claude Code hook, remove the `UserPromptSubmit` entry from your Claude Code settings.

## Privacy

Everything stays local by default. If you configure OpenAI or OpenRouter for embeddings, those API calls go to their servers. Use Ollama for fully local operation.

## License

MIT — see [LICENSE](LICENSE).

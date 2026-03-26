<p align="center">
  <img src="assets/echovault-icon.svg" width="120" height="120" alt="EchoVault" />
</p>

<h1 align="center">EchoVault</h1>

<p align="center">
  Local memory for coding agents. Your agent remembers decisions, bugs, and context across sessions — no cloud, no API keys, no cost.
</p>

<p align="center">
  <a href="#install">Install</a> · <a href="#features">Features</a> · <a href="#how-it-works">How it works</a> · <a href="#commands">Commands</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="https://github.com/mraza007/echovault/releases">Releases</a> · <a href="https://muhammadraza.me/2026/building-local-memory-for-coding-agents/">Blog post</a>
</p>

---

EchoVault gives your agent persistent memory. Every decision, bug fix, and lesson learned is saved locally and automatically surfaced in future sessions. Your agent gets better the more you use it.

### Why I built this

Coding agents forget everything between sessions. They re-discover the same patterns, repeat the same mistakes, and forget the decisions you made yesterday. I tried other tools like Supermemory and Claude Mem — both are great, but they didn't fit my use case.

Supermemory saves everything in the cloud, which was a deal breaker since I work with multiple companies as a consultant and don't want codebase decisions stored remotely. Claude Mem caused my sessions to consume too much memory, making it hard to run multiple sessions at the same time.

I built EchoVault to solve this: local memory persistence for coding agents that's simple, fast, and private.

## Features

**Works with 4 agents** — Claude Code, Cursor, Codex, OpenCode. One command sets up MCP config for your agent.

**MCP native** — Runs as an MCP server exposing `memory_save`, `memory_search`, and `memory_context` as tools. Agents call them directly — no shell hooks needed.

**Local-first** — Everything stays on your machine. Memories are stored as Markdown in `~/.memory/vault/`, readable in Obsidian or any editor. No data leaves your machine unless you opt into cloud embeddings.

**Zero idle cost** — No background processes, no daemon, no RAM overhead. The MCP server only runs when the agent starts it.

**Hybrid search** — FTS5 keyword search works out of the box. Add Ollama or OpenAI for semantic vector search.

**Secret redaction** — 3-layer redaction strips API keys, passwords, and credentials before anything hits disk. Supports explicit `<redacted>` tags, pattern detection, and custom `.memoryignore` rules.

**Cross-agent** — Memories saved by Claude Code are searchable in Cursor, Codex, and OpenCode. One vault, many agents.

**Obsidian-compatible** — Session files are valid Markdown with YAML frontmatter. Point Obsidian at `~/.memory/vault/` and browse your agent's memory visually.

**Terminal dashboard** — Launch `memory dashboard` for a k9s-style keyboard-driven TUI with vim navigation, `$EDITOR` integration, search, stats, duplicate review, and command palette.

## Install

Install the latest stable release:

```bash
pip install git+https://github.com/mraza007/echovault.git@v0.4.0
memory init
memory setup claude-code   # or: cursor, codex, opencode
```

That's it. `memory setup` installs MCP server config automatically.

If you want the newest unreleased changes from `main`, install directly from the branch instead:

```bash
pip install git+https://github.com/mraza007/echovault.git@main
```

Release notes live in [CHANGELOG.md](CHANGELOG.md) and on the [GitHub Releases](https://github.com/mraza007/echovault/releases) page.

By default config is installed globally. To install for a specific project:

```bash
cd ~/my-project
memory setup claude-code --project   # writes .mcp.json in project root
memory setup opencode --project      # writes opencode.json in project root
memory setup codex --project         # writes .codex/config.toml + AGENTS.md
```

### Configure embeddings (optional)

Embeddings enable semantic search. Without them, you still get fast keyword search via FTS5.

Generate a starter config:

```bash
memory config init
```

This creates `~/.memory/config.yaml` with sensible defaults:

```yaml
embedding:
  provider: ollama              # ollama | openai
  model: nomic-embed-text
  # base_url: http://localhost:11434   # for ollama; for openai: https://api.openai.com/v1
  # api_key: sk-...                    # required for openai

enrichment:
  provider: none                # none | ollama | openai

context:
  semantic: auto                # auto | always | never
  topup_recent: true
```

**What each section does:**

- **`embedding`** — How memories get turned into vectors for semantic search. `ollama` runs locally, and `openai` calls cloud APIs. `nomic-embed-text` is a good local model for Ollama.
- **`enrichment`** — Optional LLM step that enhances memories before storing (better summaries, auto-tags). Set to `none` to skip.
- **`context`** — Controls how memories are retrieved at session start. `auto` uses vector search when embeddings are available, falls back to keywords. `topup_recent` also includes recent memories so the agent has fresh context.

For cloud providers, add `api_key` under the provider section. To use OpenAI-compatible endpoints (proxies/gateways/self-hosted), set `base_url` (for OpenAI: `https://api.openai.com/v1`). API keys are redacted in `memory config` output.

#### Example: on‑prem vLLM (OpenAI-compatible)

If you run an OpenAI-compatible vLLM server on-prem (often served at `/v1`), point `base_url` at it and set `model` to the model name your vLLM instance exposes.

```yaml
embedding:
  provider: openai
  model: <your-vllm-embedding-model>
  base_url: http://vllm.your-company.internal:8000/v1
  # api_key: <optional>   # set if your vLLM gateway enforces auth
```

### Configure memory location

By default, EchoVault stores data in `~/.memory`.

You can change that in two ways:

- `MEMORY_HOME=/path/to/memory` (highest priority, per-shell/per-process)
- `memory config set-home /path/to/memory` (persistent default)

Useful commands:

```bash
memory config set-home /path/to/memory
memory config clear-home
memory config
```

`memory config` now shows both `memory_home` and `memory_home_source` (`env`, `config`, or `default`).

## Usage

Once set up, your agent uses memory via MCP tools:

- **Session start** — agent calls `memory_context` to load prior decisions and context
- **During work** — agent calls `memory_search` to find relevant memories
- **Session end** — agent calls `memory_save` to persist decisions, bugs, and learnings

The MCP tool descriptions instruct agents to save and retrieve automatically. No manual prompting needed in most cases.

**Auto-save hooks (Claude Code)** — Optional hooks that ensure Claude always saves learnings before ending a session. See [docs/auto-save-hooks.md](docs/auto-save-hooks.md) for setup.

You can also use the CLI directly:

```bash
memory save --title "Switched to JWT auth" \
  --what "Replaced session cookies with JWT" \
  --why "Needed stateless auth for API" \
  --impact "All endpoints now require Bearer token" \
  --tags "auth,jwt" --category "decision" \
  --details "Context:
Options considered:
- Keep session cookies
- Move to JWT
Decision:
Tradeoffs:
Follow-up:"

memory search "authentication"
memory details <id>
memory context --project
memory dashboard
```

For long details, use `--details-file notes.md`. To scaffold structured details automatically, use `--details-template`.

### Terminal dashboard

EchoVault ships with a full-screen terminal dashboard with k9s-style keyboard-driven navigation:

```bash
memory dashboard
memory dashboard --project my-project
```

Use it to:

- browse memories across the whole vault with search, project, and category filters
- preview memory details inline (vertical split: table on top, detail below)
- edit memories in `$EDITOR` (vim) as YAML files
- archive or restore memories with confirmation dialogs
- review duplicate candidates side-by-side and merge them
- run import, reindex, and refresh from the operations panel
- use the `:` command palette for power-user operations

Keybindings:

| Key | Action |
|-----|--------|
| `1` `2` `3` `4` | Switch panels: Overview, Memories, Review, Ops |
| `j` / `k` | Navigate rows (vim-style) |
| `g` / `G` | Jump to first / last row |
| `/` | Focus search |
| `e` | Edit selected memory in $EDITOR |
| `n` | New memory in $EDITOR |
| `a` | Archive or restore |
| `m` | Merge duplicate pair |
| `x` | Keep duplicate pair separate |
| `i` | Import from vault |
| `R` | Reindex vectors |
| `r` | Refresh all data |
| `:` | Command palette |
| `?` | Help overlay |
| `q` | Quit |

## How it works

```
~/.memory/
├── vault/                    # Obsidian-compatible Markdown
│   └── my-project/
│       └── 2026-02-01-session.md
├── index.db                  # SQLite: FTS5 + sqlite-vec
└── config.yaml               # Embedding provider config
```

- **Markdown vault** — one file per session per project, with YAML frontmatter
- **SQLite index** — FTS5 for keywords, sqlite-vec for semantic vectors
- **Compact pointers** — search returns ~50-token summaries; full details fetched on demand
- **3-layer redaction** — explicit tags, pattern matching, and `.memoryignore` rules

## Supported agents

| Agent | Setup command | What gets installed |
|-------|-------------|-------------------|
| Claude Code | `memory setup claude-code` | MCP server in `.mcp.json` (project) or `~/.claude.json` (global) |
| Cursor | `memory setup cursor` | MCP server in `.cursor/mcp.json` |
| Codex | `memory setup codex` | MCP server in `.codex/config.toml` + `AGENTS.md` fallback |
| OpenCode | `memory setup opencode` | MCP server in `opencode.json` (project) or `~/.config/opencode/opencode.json` (global) |

All agents share the same memory vault at your effective `memory_home` path (default `~/.memory/`). A memory saved by Claude Code is searchable from Cursor, Codex, or OpenCode.

## Commands

| Command | Description |
|---------|-------------|
| `memory init` | Create vault at effective memory home |
| `memory setup <agent>` | Install MCP server config for an agent |
| `memory uninstall <agent>` | Remove MCP server config for an agent |
| `memory save ...` | Save a memory (`--details-file` and `--details-template` supported) |
| `memory search "query"` | Hybrid FTS + semantic search |
| `memory details <id>` | Full details for a memory |
| `memory delete <id>` | Delete a memory by ID or prefix |
| `memory context --project` | List memories for current project |
| `memory import` | Import markdown memories into the SQLite index |
| `memory sessions` | List session files |
| `memory dashboard` | Launch the terminal dashboard |
| `memory config` | Show effective config |
| `memory config init` | Generate a starter config.yaml |
| `memory config set-home <path>` | Persist default memory location |
| `memory config clear-home` | Remove persisted memory location |
| `memory reindex` | Rebuild vectors after changing provider |
| `memory mcp` | Start the MCP server (stdio transport) |

## Uninstall

```bash
memory uninstall claude-code   # or: cursor, codex, opencode
pip uninstall echovault
```

To also remove all stored memories: `rm -rf ~/.memory/`

## Blog post

[I Built Local Memory for Coding Agents Because They Keep Forgetting Everything](https://muhammadraza.me/2026/building-local-memory-for-coding-agents/)

## Privacy

Everything stays local by default. If you configure OpenAI for embeddings, those API calls go to their servers. Use Ollama for fully local operation.

## License

MIT — see [LICENSE](LICENSE).

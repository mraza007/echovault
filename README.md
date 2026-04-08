<p align="center">
  <img src="assets/echovault-icon.svg" width="120" height="120" alt="EchoVault" />
</p>

<h1 align="center">EchoVault</h1>

<p align="center">
  Local memory for coding agents. Your agent remembers decisions, bugs, and context across sessions — no cloud, no API keys, no cost.<br>
  Локальная память для агентов кодирования. Агент запоминает решения, баги и контекст между сессиями — без облака, без API ключей, без затрат.
</p>

<p align="center">
  <a href="#install">Install / Установка</a> · <a href="#features">Features / Функции</a> · <a href="#how-it-works">How it works / Как это работает</a> · <a href="#commands">Commands / Команды</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="https://github.com/mraza007/echovault/releases">Releases</a> · <a href="https://muhammadraza.me/2026/building-local-memory-for-coding-agents/">Blog post</a>
</p>

---

**English:** EchoVault gives your agent persistent memory. Every decision, bug fix, and lesson learned is saved locally and automatically surfaced in future sessions. Your agent gets better the more you use it.

**Русский:** EchoVault даёт агенту персистентную память. Каждое решение, исправление бага и урок сохраняются локально и автоматически доступны в будущих сессиях. Агент становится лучше с каждым использованием.

### Why I built this / Зачем я это создал

**English:** Coding agents forget everything between sessions. They re-discover the same patterns, repeat the same mistakes, and forget the decisions you made yesterday. I tried other tools like Supermemory and Claude Mem — both are great, but they didn't fit my use case.

Supermemory saves everything in the cloud, which was a deal breaker since I work with multiple companies as a consultant and don't want codebase decisions stored remotely. Claude Mem caused my sessions to consume too much memory, making it hard to run multiple sessions at the same time.

I built EchoVault to solve this: local memory persistence for coding agents that's simple, fast, and private.

**Русский:** Агенты кодирования забывают всё между сессиями. Они переоткрывают те же паттерны, повторяют те же ошибки и забывают решения, принятые вчера. Я пробовал другие инструменты вроде Supermemory и Claude Mem — оба отличные, но не подошли мне.

Supermemory сохраняет всё в облаке, что было критично, так как я работаю консультантом с несколькими компаниями и не хочу хранить решения по кодовой базе удалённо. Claude Mem заставлял сессии потреблять слишком много памяти, усложняя запуск нескольких сессий одновременно.

Я создал EchoVault, чтобы решить это: локальная персистентная память для агентов кодирования, которая простая, быстрая и приватная.

## Features / Функции

| English | Русский |
|---------|---------|
| **Works with 4 agents** — Claude Code, Cursor, Codex, OpenCode. One command sets up MCP config for your agent. | **Работает с 4 агентами** — Claude Code, Cursor, Codex, OpenCode. Одна команда настраивает MCP конфиг для агента. |
| **MCP native** — Runs as an MCP server exposing `memory_save`, `memory_search`, and `memory_context` as tools. | **Нативный MCP** — Работает как MCP сервер, предоставляя инструменты `memory_save`, `memory_search`, `memory_context`. |
| **Local-first** — Everything stays on your machine. Memories stored as Markdown in `~/.memory/vault/`. | **Локальный-first** — Всё остаётся на машине. Память хранится как Markdown в `~/.memory/vault/`. |
| **Zero idle cost** — No background processes, no daemon, no RAM overhead. | **Нулевая стоимость простоя** — Нет фоновых процессов, демонов, расхода RAM. |
| **Hybrid search** — FTS5 keyword search + Ollama/OpenAI semantic vectors. | **Гибридный поиск** — FTS5 поиск по ключам + семантические векторы Ollama/OpenAI. |
| **Secret redaction** — 3-layer stripping of API keys, passwords, credentials. | **Редактирование секретов** — 3-слойное удаление API ключей, паролей, credentials. |
| **Cross-agent** — Memories saved by Claude Code searchable in Cursor, Codex, OpenCode. | **Кросс-агентный** — Память от Claude Code доступна в Cursor, Codex, OpenCode. |
| **Obsidian-compatible** — Session files are Markdown with YAML frontmatter. | **Совместим с Obsidian** — Файлы сессий — Markdown с YAML frontmatter. |
| **Terminal dashboard** — `memory dashboard` for k9s-style TUI with vim navigation. | **Терминальный дашборд** — `memory dashboard` для TUI в стиле k9s с vim навигацией. |
| **Unified 3-Tier Memory** — Fast (RAM, 24h), Medium (SSD, 7d), Slow (HDD, async). | **Унифицированная 3-уровневая память** — Fast (RAM, 24ч), Medium (SSD, 7д), Slow (HDD, async). |
| **Safe Rollout** — Feature flags: `disabled → shadow → canary → enabled`. | **Безопасный rollout** — Фича-флаги: `disabled → shadow → canary → enabled`. |
| **Unified Memory Tools** — Direct access to tiers: `memory_unified_search`, `memory_unified_context`, `memory_unified_save` | **Унифицированные инструменты памяти** — Прямой доступ к уровням: `memory_unified_search`, `memory_unified_context`, `memory_unified_save` |

## Install / Установка

**English:** Install the latest stable release:

**Русский:** Установите последний стабильный релиз:

```bash
pip install git+https://github.com/mraza007/echovault.git@v0.4.0
memory init
memory setup claude-code   # or: cursor, codex, opencode
```

**English:** That's it. `memory setup` installs MCP server config automatically.

**Русский:** Готово. `memory setup` автоматически устанавливает MCP конфиг.

**English:** If you want the newest unreleased changes from `main`, install directly from the branch instead:

**Русский:** Если нужны новейшие не выпущенные изменения из `main`, установите напрямую из ветки:

```bash
pip install git+https://github.com/mraza007/echovault.git@main
```

**English:** Release notes live in [CHANGELOG.md](CHANGELOG.md) and on the [GitHub Releases](https://github.com/mraza007/echovault/releases) page.

**Русский:** Релизные заметки в [CHANGELOG.md](CHANGELOG.md) и на [GitHub Releases](https://github.com/mraza007/echovault/releases).

**English:** By default config is installed globally. To install for a specific project:

**Русский:** По умолчанию конфиг устанавливается глобально. Для установки в проект:

```bash
cd ~/my-project
memory setup claude-code --project   # writes .mcp.json in project root
memory setup opencode --project      # writes opencode.json in project root
memory setup codex --project         # writes .codex/config.toml + AGENTS.md
```

### Configure embeddings (optional) / Настройка эмбеддингов (опционально)

**English:** Embeddings enable semantic search. Without them, you still get fast keyword search via FTS5.

**Русский:** Эмбеддинги включают семантический поиск. Без них доступен быстрый поиск по ключам через FTS5.

**English:** Generate a starter config:

**Русский:** Создайте стартовый конфиг:

```bash
memory config init
```

**English:** This creates `~/.memory/config.yaml` with sensible defaults:

**Русский:** Создаёт `~/.memory/config.yaml` с разумными умолчаниями:

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

| Section (EN) | Section (RU) |
|--------------|--------------|
| **`embedding`** — How memories get turned into vectors for semantic search. `ollama` runs locally, `openai` calls cloud APIs. `nomic-embed-text` is a good local model for Ollama. | **`embedding`** — Как воспоминания превращаются в векторы для семантического поиска. `ollama` работает локально, `openai` вызывает облачные API. `nomic-embed-text` — хорошая локальная модель для Ollama. |
| **`enrichment`** — Optional LLM step that enhances memories before storing (better summaries, auto-tags). Set to `none` to skip. | **`enrichment`** — Опциональный LLM шаг, улучшающий воспоминания перед сохранением (лучшие summary, авто-теги). `none` чтобы пропустить. |
| **`context`** — Controls how memories are retrieved at session start. `auto` использует векторный поиск когда доступно, иначе ключи. `topup_recent` включает недавние воспоминания для свежего контекста. | **`context`** — Контролирует как воспоминания извлекаются при старте сессии. `auto` использует векторный поиск, иначе ключевой. `topup_recent` добавляет недавние воспоминания. |

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

## Usage / Использование

**English:** Once set up, your agent uses memory via MCP tools:

**Русский:** После настройки агент использует память через MCP инструменты:

| Phase (EN) | Phase (RU) |
|------------|------------|
| **Session start** — agent calls `memory_context` to load prior decisions and context | **Старт сессии** — агент вызывает `memory_context` для загрузки решений и контекста |
| **During work** — agent calls `memory_search` to find relevant memories | **Во время работы** — агент вызывает `memory_search` для поиска релевантных воспоминаний |
| **Session end** — agent calls `memory_save` to persist decisions, bugs, and learnings | **Конец сессии** — агент вызывает `memory_save` для сохранения решений, багов и уроков |

**English:** The MCP tool descriptions instruct agents to save and retrieve automatically. No manual prompting needed in most cases.

**Русский:** Описания MCP инструментов дают агентам инструкции сохранять и извлекать автоматически. Ручное промптирование обычно не нужно.

**English:** **Auto-save hooks (Claude Code)** — Optional hooks that ensure Claude always saves learnings before ending a session. See [docs/auto-save-hooks.md](docs/auto-save-hooks.md) for setup.

**Русский:** **Хуки авто-сохранения (Claude Code)** — Опциональные хуки, гарантирующие что Claude всегда сохраняет уроки перед концом сессии. См. [docs/auto-save-hooks.md](docs/auto-save-hooks.md).

**English:** You can also use the CLI directly:

**Русский:** Можно также использовать CLI напрямую:

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

**English:** For long details, use `--details-file notes.md`. To scaffold structured details automatically, use `--details-template`.

**Русский:** Для длинных деталей используйте `--details-file notes.md`. Для авто-генерации структурированных деталей — `--details-template`.

### Terminal dashboard / Терминальный дашборд

**English:** EchoVault ships with a full-screen terminal dashboard with k9s-style keyboard-driven navigation:

**Русский:** EchoVault включает полноэкранный терминальный дашборд с k9s-навигацией:

```bash
memory dashboard
memory dashboard --project my-project
```

**English:** Use it to:

**Русский:** Используйте для:

- browse memories / просмотра воспоминаний
- preview memory details / предпросмотра деталей
- edit memories in `$EDITOR` / редактирования в `$EDITOR`
- archive or restore memories / архивирования или восстановления
- review duplicates / просмотра дубликатов
- run import, reindex, refresh / запуска импорта, переиндексации, обновления
- command palette / командной палитры

**English:** Keybindings:

**Русский:** Клавиши:

| Key / Клавиша | Action / Действие |
|---------------|-------------------|
| `1` `2` `3` `4` | Switch panels: Overview, Memories, Review, Ops / Переключение панелей |
| `j` / `k` | Navigate rows (vim-style) / Навигация по строкам (vim) |
| `g` / `G` | Jump to first / last row / Переход к первой/последней строке |
| `/` | Focus search / Фокус поиска |
| `e` | Edit selected memory in $EDITOR / Редактировать в $EDITOR |
| `n` | New memory in $EDITOR / Новое воспоминание в $EDITOR |
| `a` | Archive or restore / Архивировать или восстановить |
| `m` | Merge duplicate pair / Слить дубликаты |
| `x` | Keep duplicate pair separate / Оставить дубликаты раздельно |
| `i` | Import from vault / Импорт из хранилища |
| `R` | Reindex vectors / Переиндексация векторов |
| `r` | Refresh all data / Обновить данные |
| `:` | Command palette / Командная палитра |
| `?` | Help overlay / Окно помощи |
| `q` | Quit / Выход |

### Session Finalization / Финализация сессии

**English:** Before ending ANY session that involved meaningful work, you MUST save your learnings. This is not optional.

**Русский:** Перед завершением ЛЮБОЙ сессии с осмысленной работой вы ДОЛЖНЫ сохранить уроки. Это не опционально.

**English:** Steps to finalize:

**Русский:** Шаги для финализации:

```bash
# 1. Review what was done / Обзор проделанного
memory sessions

# 2. Save decisions and learnings / Сохранить решения и уроки
memory save \
  --title "Session summary / Итог сессии" \
  --what "What was accomplished / Что было достигнуто" \
  --why "Reasoning and decisions / Обоснование и решения" \
  --impact "Changes made / Внесённые изменения" \
  --tags "summary,session" \
  --category "context"

# 3. Verify context is saved / Проверить что контекст сохранён
memory context --project
```

**English:** What to save at session end:

| EN | RU |
|----|-----|
| Architectural decisions made | Архитектурные решения |
| Bugs fixed (with root cause) | Исправленные баги (с причиной) |
| Patterns discovered | Обнаруженные паттерны |
| Infrastructure changes | Изменения инфраструктуры |
| User clarifications received | Полученные уточнения пользователя |
| Next steps / TODOs | Следующие шаги / TODO |

**English:** Always use `--source` flag to identify your agent: `claude-code`, `codex`, or `cursor`.

**Русский:** Всегда используйте флаг `--source` для идентификации агента: `claude-code`, `codex`, или `cursor`.

## How it works / Как это работает

```
~/.memory/
├── vault/                    # Obsidian-compatible Markdown / Markdown для Obsidian
│   └── my-project/
│       └── 2026-02-01-session.md
├── index.db                  # SQLite: FTS5 + sqlite-vec
└── config.yaml               # Embedding provider config / Конфиг провайдера эмбеддингов
```

| Component (EN) | Component (RU) |
|----------------|----------------|
| **Markdown vault** — one file per session per project, with YAML frontmatter | **Markdown хранилище** — один файл на сессию на проект, с YAML frontmatter |
| **SQLite index** — FTS5 for keywords, sqlite-vec for semantic vectors | **SQLite индекс** — FTS5 для ключей, sqlite-vec для семантических векторов |
| **Compact pointers** — search returns ~50-token summaries; full details fetched on demand | **Компактные указатели** — поиск возвращает ~50-токенные summary; полные детали по запросу |
| **3-layer redaction** — explicit tags, pattern matching, and `.memoryignore` rules | **3-слойное редактирование** — явные теги, паттерн-матчинг, правила `.memoryignore` |

## Supported agents / Поддерживаемые агенты

| Agent / Агент | Setup command / Команда установки | What gets installed / Что устанавливается |
|---------------|-----------------------------------|------------------------------------------|
| Claude Code | `memory setup claude-code` | MCP server in `.mcp.json` (project) or `~/.claude.json` (global) / MCP сервер в `.mcp.json` (проект) или `~/.claude.json` (глобально) |
| Cursor | `memory setup cursor` | MCP server in `.cursor/mcp.json` / MCP сервер в `.cursor/mcp.json` |
| Codex | `memory setup codex` | MCP server in `.codex/config.toml` + `AGENTS.md` / MCP сервер в `.codex/config.toml` + `AGENTS.md` |
| OpenCode | `memory setup opencode` | MCP server in `opencode.json` (project) or `~/.config/opencode/opencode.json` (global) / MCP сервер в `opencode.json` (проект) или `~/.config/opencode/opencode.json` (глобально) |

**English:** All agents share the same memory vault at your effective `memory_home` path (default `~/.memory/`). A memory saved by Claude Code is searchable from Cursor, Codex, or OpenCode.

**Русский:** Все агенты используют общее хранилище памяти по пути `memory_home` (по умолчанию `~/.memory/`). Воспоминание от Claude Code доступно для поиска из Cursor, Codex или OpenCode.

## Commands / Команды

| Command / Команда | Description / Описание |
|---------------------|------------------------|
| `memory init` | Create vault at effective memory home / Создать хранилище в текущем memory home |
| `memory setup <agent>` | Install MCP server config for an agent / Установить MCP конфиг для агента |
| `memory uninstall <agent>` | Remove MCP server config for an agent / Удалить MCP конфиг агента |
| `memory save ...` | Save a memory (`--details-file` and `--details-template` supported) / Сохранить воспоминание (поддерживаются `--details-file` и `--details-template`) |
| `memory search "query"` | Hybrid FTS + semantic search / Гибридный FTS + семантический поиск |
| `memory details <id>` | Full details for a memory / Полные детали воспоминания |
| `memory delete <id>` | Delete a memory by ID or prefix / Удалить воспоминание по ID или префиксу |
| `memory context --project` | List memories for current project / Список воспоминаний текущего проекта |
| `memory import` | Import markdown memories into the SQLite index / Импорт Markdown в SQLite индекс |
| `memory sessions` | List session files / Список файлов сессий |
| `memory dashboard` | Launch the terminal dashboard / Запустить терминальный дашборд |
| `memory config` | Show effective config / Показать текущий конфиг |
| `memory config init` | Generate a starter config.yaml / Создать стартовый config.yaml |
| `memory config set-home <path>` | Persist default memory location / Установить путь хранилища |
| `memory config clear-home` | Remove persisted memory location / Удалить путь хранилища |
| `memory reindex` | Rebuild vectors after changing provider / Перестроить векторы после смены провайдера |
| `memory mcp` | Start the MCP server (stdio transport) / Запустить MCP сервер (stdio транспорт) |
| `memory rollback_status` | Check unified memory system health / Проверить здоровье unified memory |
| `memory rollback_enable <stage>` | Enable rollout stage: shadow/canary/enabled / Включить стадию: shadow/canary/enabled |
| `memory rollback_emergency` | Emergency rollback to legacy system / Экстренный откат к legacy |
| `memory unified_search "query"` | Search Fast + Medium tiers (immediate) / Поиск Fast + Medium уровней (немедленно) |
| `memory unified_context` | Get context from Fast + Medium tiers / Получить контекст из Fast + Medium |
| `memory unified_save ...` | Save to Fast tier with auto-migration / Сохранить в Fast с авто-миграцией |

## Uninstall / Удаление

```bash
memory uninstall claude-code   # or: cursor, codex, opencode
memory uninstall claude-code   # или: cursor, codex, opencode
pip uninstall echovault
```

**English:** To also remove all stored memories: `rm -rf ~/.memory/`

**Русский:** Чтобы также удалить все сохранённые воспоминания: `rm -rf ~/.memory/`

## Blog post

[I Built Local Memory for Coding Agents Because They Keep Forgetting Everything](https://muhammadraza.me/2026/building-local-memory-for-coding-agents/)

## Privacy / Приватность

**English:** Everything stays local by default. If you configure OpenAI for embeddings, those API calls go to their servers. Use Ollama for fully local operation.

**Русский:** По умолчанию всё остаётся локально. Если настроен OpenAI для эмбеддингов, эти API вызовы идут на их серверы. Используйте Ollama для полностью локальной работы.

## License / Лицензия

MIT — see [LICENSE](LICENSE) / см. [LICENSE](LICENSE).

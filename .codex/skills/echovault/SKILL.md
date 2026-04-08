---
name: echovault
description: Local-first memory for coding agents. You MUST retrieve memories at session start and save memories before session end. This is not optional.
---

> **Русский** | [Перейти к русской версии](#russian-version)

---

# EchoVault — Agent Memory System

You have persistent memory across sessions. USE IT.

## Session start — MANDATORY

Before doing ANY work, retrieve context from previous sessions:

```bash
memory context --project
```

If the user's request relates to a specific topic, also search for it:

```bash
memory search "<relevant terms>"
```

When search results show "Details: available", fetch them:

```bash
memory details <memory-id>
```

Do not skip this step. Prior sessions may contain decisions, bugs, and context that directly affect your current task.

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

Categories: `decision`, `bug`, `pattern`, `setup`, `learning`, `context`.

Use `--source` to identify the agent: `claude-code`, `codex`, or `cursor`.

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

Run once to auto-install hooks for your agent:

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

---

# <a name="russian-version"></a>Русская версия

# EchoVault — Система памяти агента

У тебя есть персистентная память между сессиями. ИСПОЛЬЗУЙ ЕЁ.

## Начало сессии — ОБЯЗАТЕЛЬНО

Перед выполнением ЛЮБОЙ работы извлеки контекст из предыдущих сессий:

```bash
memory context --project
```

Если запрос пользователя связан с конкретной темой, также выполни поиск:

```bash
memory search "<релевантные термины>"
```

Когда результаты поиска показывают "Details: available", получи их:

```bash
memory details <memory-id>
```

Не пропускай этот шаг. Предыдущие сессии могут содержать решения, баги и контекст, которые напрямую влияют на твою текущую задачу.

## Конец сессии — ОБЯЗАТЕЛЬНО

Перед завершением ответа на ЛЮБУЮ задачу, которая включала внесение изменений, отладку, принятие решений или изучение чего-либо, ты ДОЛЖЕН сохранить воспоминание. Это не опционально. Если ты выполнил значимую работу — сохрани её.

```bash
memory save \
  --title "Краткое описательное название" \
  --what "Что произошло или было решено" \
  --why "Обоснование этого" \
  --impact "Что изменилось в результате" \
  --tags "tag1,tag2,tag3" \
  --category "<категория>" \
  --related-files "path/to/file1,path/to/file2" \
  --source "claude-code" \
  --details "Контекст:

             Рассмотренные варианты:
             - Вариант A
             - Вариант B

             Решение:
             Компромиссы:
             Следующие шаги:"
```

Категории: `decision`, `bug`, `pattern`, `setup`, `learning`, `context`.

Используй `--source` для идентификации агента: `claude-code`, `codex`, или `cursor`.

### Что сохранять

Ты ДОЛЖЕН сохранять, когда происходит любое из следующего:

- Ты принял архитектурное или дизайн-решение
- Ты исправил баг (включи корневую причину и решение)
- Ты обнаружил неочевидный паттерн или подводный камень
- Ты настроил инфраструктуру, инструменты или конфигурацию
- Ты выбрал один подход вместо альтернатив
- Ты узнал что-то о кодовой базе, чего нет в коде
- Пользователь поправил тебя или уточнил требование

### Что НЕ сохранять

- Тривиальные изменения (исправление опечаток, форматирование)
- Информация, которая уже очевидна из чтения кода
- Дубликат существующего воспоминания (сначала поищи)

## Настройка агента (рекомендуется)

Запусти один раз для авто-установки хуков для твоего агента:

```bash
memory setup claude-code   # или: cursor, codex
```

Для удаления: `memory uninstall claude-code`

## Другие команды

```bash
memory config       # показать текущую конфигурацию
memory sessions     # список файлов сессий
memory reindex      # перестроить индекс поиска
memory delete <id>  # удалить воспоминание
```

## Правила

- Извлекай перед работой. Сохраняй перед завершением. Без исключений.
- Всегда захватывай детальные детали — пиши для будущего агента без контекста.
- Никогда не включай API ключи, секреты или credentials.
- Оборачивай чувствительные значения в `<redacted>` теги.
- Ищи перед сохранением, чтобы избежать дубликатов.
- Одно воспоминание на каждое отдельное решение или событие. Не группируй несвязанные вещи.

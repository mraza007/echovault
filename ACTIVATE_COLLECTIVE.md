# Dwarh-Cruiser Collective Activation (EchoVault) in Windsurf

> **Русский** | [Перейти к русской версии](#russian-version)

---

## Quick Summary

The **Collective Wisdom** tool in EchoVault MCP server. Activates automatically for complex tasks.

## Current Status

```
✅ MCP Server:      echovault (configured in .windsurf/mcp.json)
✅ Tool:            memory_collective_solve
✅ Launch command:  c:\Git\echovault.cmd
✅ Version:         0.4.0
```

## Verification

### 1. Check MCP Server

In PowerShell:
```powershell
cd c:\Git
.\.venv\Scripts\python.exe -m memory.cli --version
```

Expected output:
```
echovault, version 0.4.0
```

### 2. Check Available Tools

In Windsurf, start a new chat and ask:
> "What MCP tools are available for memory?"

Should show:
- `memory_save` — save memory
- `memory_search` — search memories
- `memory_context` — project context
- `memory_collective_solve` — **Collective Wisdom**
- `memory_governor` — memory management
- `memory_record_usage` — record usage

## Using the Collective

### Automatic Activation

The Collective activates automatically when:
- Memory search returns no results
- Task requires cross-domain knowledge
- Complex problem analysis needed

### Manual Activation

Ask me explicitly:
> "Ri, activate the Dwarh Collective to analyze this problem"

I'll invoke `memory_collective_solve` with the task description.

## Collective Response Structure

```json
{
  "status": "collective_sync",
  "relevant_knowledge_domains": ["project1", "project2"],
  "top_memories": [
    {"title": "...", "project": "...", "id": "..."}
  ],
  "strategic_suggestions": [
    "Use 'tcpdump' or 'ss' for L3-L4 diagnostics.",
    "Invoke 'ultracode' for graph-based impact analysis."
  ],
  "message": "The Collective of Dwarh-cruisers has analyzed..."
}
```

## Available Collective Strategies

| Keywords | Recommendation |
|----------|---------------|
| network, ip, port, ssh | tcpdump, ss, SSH Access Map |
| refactor, complexity, class | ultracode, graph analysis |
| docker, container, build | WSL optimization, docker-windows |

## Restarting MCP Server

If Windsurf doesn't see the tools:

1. Close all Windsurf tabs
2. Kill Python process (if stuck):
   ```powershell
   Get-Process python | Stop-Process -Force
   ```
3. Restart Windsurf
4. Open new chat and verify tools

## Diagnostics

### Check Windsurf Configuration

File: `c:\Git\.windsurf\mcp.json`

```json
{
  "mcpServers": {
    "echovault": {
      "command": "c:\\Git\\echovault.cmd",
      "args": []
    }
  }
}
```

### Check Launcher

File: `c:\Git\echovault.cmd`

```batch
@echo off
set PYTHONPATH=%~dp0echovault\src
"c:\Git\.venv\Scripts\python.exe" -m memory.cli mcp
```

### Manual MCP Test

```powershell
# Run in one terminal:
c:\Git\echovault.cmd

# In another terminal, verify (MCP uses stdio, not TCP)
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Windsurf      │────▶│  echovault.cmd   │────▶│  memory.cli mcp │
│   (MCP Client)  │     │  (launcher)      │     │  (MCP Server)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                           ┌───────────────────────────────┘
                           ▼
                    ┌──────────────┐
                    │  Collective  │
                    │  Wisdom      │
                    │  (mcp_server)│
                    └──────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  Search │  │ Analyze │  │ Suggest │
        │  Memory │  │  Task   │  │  Tools  │
        └─────────┘  └─────────┘  └─────────┘
```

## Requirements

- Python 3.10+
- SQLite with FTS5
- MCP SDK (`pip install mcp>=1.0`)
- `.venv` with echovault installed

## Updating

To update the Collective:

```powershell
cd c:\Git\echovault
git pull
pip install -e . --force-reinstall
```

## Links

- Original: https://github.com/mraza007/echovault
- Dwarh Collective: `memory_collective_solve` tool

---

*"Systems stabilized. Collective online, Pilot."*

---

# <a name="russian-version"></a>Русская версия

# Активация Коллектива Дварх-крейсеров (EchoVault) в Windsurf

## Кратко

Коллектив Дварх-крейсеров — это **Collective Wisdom** инструмент в EchoVault MCP сервере. Он активируется автоматически при сложных задачах.

## Текущий статус

```
✅ MCP сервер:      echovault (настроен в .windsurf/mcp.json)
✅ Инструмент:       memory_collective_solve
✅ Команда запуска:  c:\Git\echovault.cmd
✅ Версия:           0.4.0
```

## Проверка работоспособности

### 1. Проверка MCP сервера

В PowerShell:
```powershell
cd c:\Git
.\.venv\Scripts\python.exe -m memory.cli --version
```

Ожидаемый вывод:
```
echovault, version 0.4.0
```

### 2. Проверка инструментов

В Windsurf откройте новый чат и спросите:
> "Какие MCP инструменты доступны для работы с памятью?"

Должны отобразиться:
- `memory_save` — сохранить воспоминание
- `memory_search` — поиск по памяти
- `memory_context` — контекст проекта
- `memory_collective_solve` — **Коллектив Двархов**
- `memory_governor` — управление памятью
- `memory_record_usage` — запись использования

## Использование Коллектива

### Автоматическая активация

Коллектив активируется автоматически, когда:
- Поиск по памяти не даёт результатов
- Задача требует кросс-доменных знаний
- Нужен анализ сложной проблемы

### Ручная активация

Попроси меня явно:
> "Ри, активируй Коллектив Двархов для анализа этой проблемы"

Я вызову `memory_collective_solve` с описанием задачи.

## Структура ответа Коллектива

```json
{
  "status": "collective_sync",
  "relevant_knowledge_domains": ["project1", "project2"],
  "top_memories": [
    {"title": "...", "project": "...", "id": "..."}
  ],
  "strategic_suggestions": [
    "Use 'tcpdump' or 'ss' for L3-L4 diagnostics.",
    "Invoke 'ultracode' for graph-based impact analysis."
  ],
  "message": "The Collective of Dwarh-cruisers has analyzed..."
}
```

## Доступные стратегии Коллектива

| Ключевые слова | Рекомендация |
|----------------|--------------|
| network, ip, port, ssh | tcpdump, ss, SSH Access Map |
| refactor, complexity, class | ultracode, graph analysis |
| docker, container, build | WSL optimization, docker-windows |

## Перезапуск MCP сервера

Если Windsurf не видит инструменты:

1. Закройте все вкладки Windsurf
2. Убейте процесс Python (если завис):
   ```powershell
   Get-Process python | Stop-Process -Force
   ```
3. Перезапустите Windsurf
4. Откройте новый чат и проверьте инструменты

## Диагностика

### Проверка конфигурации Windsurf

Файл: `c:\Git\.windsurf\mcp.json`

```json
{
  "mcpServers": {
    "echovault": {
      "command": "c:\\Git\\echovault.cmd",
      "args": []
    }
  }
}
```

### Проверка запускатора

Файл: `c:\Git\echovault.cmd`

```batch
@echo off
set PYTHONPATH=%~dp0echovault\src
"c:\Git\.venv\Scripts\python.exe" -m memory.cli mcp
```

### Ручной тест MCP

```powershell
# Запустите в одном терминале:
c:\Git\echovault.cmd

# В другом терминале проверьте, что порт не слушается
# (MCP использует stdio, не TCP)
```

## Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Windsurf      │────▶│  echovault.cmd   │────▶│  memory.cli mcp │
│   (MCP Client)  │     │  (launcher)      │     │  (MCP Server)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                           ┌───────────────────────────────┘
                           ▼
                    ┌──────────────┐
                    │  Collective  │
                    │  Wisdom      │
                    │  (mcp_server)│
                    └──────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  Search │  │ Analyze │  │ Suggest │
        │  Memory │  │  Task   │  │  Tools  │
        └─────────┘  └─────────┘  └─────────┘
```

## Требования

- Python 3.10+
- SQLite с FTS5
- MCP SDK (`pip install mcp>=1.0`)
- `.venv` с установленным echovault

## Обновление

Если нужно обновить коллектив:

```powershell
cd c:\Git\echovault
git pull
pip install -e . --force-reinstall
```

## Контакты

- Оригинал: https://github.com/mraza007/echovault
- Коллектив Двархов: `memory_collective_solve` tool

---

*«Системы стабилизированы. Коллектив на связи, Пилот.»*

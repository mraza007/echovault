# Unified 3-Tier Memory System

> **Русский** | [Перейти к русской версии](#russian-version)

---

## Overview

Unified memory model for EchoVault integrating hierarchical memory with 3 tiers:

| Tier | Speed | Storage | Lifecycle | Search |
|------|-------|---------|-----------|--------|
| **Fast** | <1ms | RAM (in-memory SQLite) | 24h TTL | Synchronous |
| **Medium** | <100ms | SSD | 7 days + LRU eviction | Synchronous FTS |
| **Slow** | 100ms-10s | HDD | Unlimited | **Asynchronous** semantic |

### User Model Mapping

```
User Model          →  Unified EchoVault
─────────────────────────────────────────────
Fast memory         →  Fast tier (Core)
Medium memory       →  Medium tier (Short-term)
Slow memory         →  Slow tier (Long-term)
```

### Slow Tier Key Feature

**Key difference**: Search in Slow tier is **non-blocking**:

```python
# Synchronous search (Fast + Medium) — immediate results
results = unified.search_sync("query", limit=5)

# Asynchronous search (Slow) — callback when found
def on_found(results):
    print(f"Found in archive: {len(results)}")

unified.search_async("query", callback=on_found)

# Full search: Fast+Medium immediately, Slow in background
results = unified.search_full("query", async_callback=on_found)
```

### Migration Pipeline

```
Incoming Data
      ↓
   [Fast] ← 24h TTL, cleanup every 60s
      ↓ (after 1-2 hours, structuring)
  [Medium] ← 7 days, LRU eviction when full
      ↓ (low access, old age)
   [Slow] ← semantic compression, embeddings
```

## Usage

### Basic

```python
from memory.unified import create_unified_memory

# Create service
memory = create_unified_memory()
await memory.start()  # Start background workers

# Save (to Fast tier)
entry = MemoryEntry(
    id="mem-1",
    title="Important clarification",
    what="Essence for future sessions",
    tier=MemoryTier.FAST,
    timestamp=int(time.time()),
    tags=["rule", "workflow"]
)
memory.save(entry)

# Search
results = memory.search_sync("clarification", limit=5)
```

### With Async Search

```python
# Callback for Slow tier results
def handle_slow_results(results):
    for r in results:
        print(f"[Archive] {r.title}: {r.what}")

# Full search: sync + async
sync_results = memory.search_full(
    "configuration",
    limit=5,
    async_callback=handle_slow_results
)
# sync_results — immediately from Fast/Medium
# handle_slow_results called later with Slow results
```

### Getting Context

```python
# Context for prompt injection
context = memory.get_context(limit=10, project="MyProject")
for entry in context:
    print(f"- {entry.title}: {entry.what}")
```

### Integration with Existing EchoVault

```python
from memory.unified_adapter import create_unified_adapter

# Adapter for gradual migration
adapter = create_unified_adapter(memory_home="~/.memory")
await adapter.start()

# Write to both systems
adapter.save_unified(
    memory_id="...",
    title="...",
    what="...",
    project="..."
)

# Search in unified (fallback to existing)
results = adapter.search_unified("query")
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   UnifiedMemoryService                   │
├──────────────┬──────────────┬───────────────────────────┤
│   FastTier   │  MediumTier  │        SlowTier           │
│  (in-memory) │    (SSD)     │        (HDD)              │
├──────────────┼──────────────┼───────────────────────────┤
│ SQLite :mem  │ SQLite file  │ SQLite file + embeddings  │
│ 24h TTL      │ 7d retention │ Unlimited                 │
│ Sync search  │ FTS search   │ Async semantic search     │
│ Cleanup 60s  │ LRU eviction │ Background worker         │
└──────────────┴──────────────┴───────────────────────────┘
       ↑              ↑                    ↑
   Migration Pipeline (every 5 minutes)
```

## Files

- `src/memory/unified.py` — Core implementation (887 lines)
- `src/memory/unified_adapter.py` — Integration with existing
- `tests/test_unified_memory.py` — Tests
- `src/memory/unified.pyi` — Type stubs

## Production TODO

1. **MCP Integration**: Add tools for unified search
2. **Monitoring**: Tier metrics (hit rate, latency)
3. **Settings**: Configurable TTL, sizes, paths
4. **Recovery**: Startup scan for consistency
5. **Compression**: NLP summarization for Slow tier

---

# <a name="russian-version"></a>Русская версия

## Обзор

Unified memory model для EchoVault, интегрирующая иерархическую память с 3 tiers:

| Tier | Скорость | Хранение | Жизненный цикл | Поиск |
|------|----------|----------|----------------|-------|
| **Fast** | <1ms | RAM (in-memory SQLite) | 24h TTL | Синхронный |
| **Medium** | <100ms | SSD | 7 дней + LRU eviction | Синхронный FTS |
| **Slow** | 100ms-10s | HDD | Бессрочно | **Асинхронный** semantic |

### Соответствие модели пользователя

```
Твоя модель          →  Unified EchoVault
─────────────────────────────────────────────
Быстрая память       →  Fast tier (Core)
Средняя память       →  Medium tier (Short-term)
Медленная память     →  Slow tier (Long-term)
```

### Особенности Slow tier

**Ключевое отличие**: Поиск в Slow tier — **неблокирующий**:

```python
# Синхронный поиск (Fast + Medium) — результат сразу
results = unified.search_sync("query", limit=5)

# Асинхронный поиск (Slow) — callback когда найдено
def on_found(results):
    print(f"Найдено в архиве: {len(results)}")

unified.search_async("query", callback=on_found)

# Полный поиск: сразу Fast+Medium, в фоне Slow
results = unified.search_full("query", async_callback=on_found)
```

### Pipeline миграции

```
Входящие данные
      ↓
   [Fast] ← 24h TTL, cleanup каждые 60s
      ↓ (через 1-2 часа, структурирование)
  [Medium] ← 7 дней, LRU eviction при переполнении
      ↓ (низкий access, старость)
   [Slow] ← семантическая компрессия, embeddings
```

## Использование

### Базовое

```python
from memory.unified import create_unified_memory

# Создать сервис
memory = create_unified_memory()
await memory.start()  # Запустить background workers

# Сохранить (в Fast tier)
entry = MemoryEntry(
    id="mem-1",
    title="Важное уточнение",
    what="Суть для будущих сессий",
    tier=MemoryTier.FAST,
    timestamp=int(time.time()),
    tags=["rule", "workflow"]
)
memory.save(entry)

# Поиск
results = memory.search_sync("уточнение", limit=5)
```

### С async поиском

```python
# Callback для результатов из Slow tier
def handle_slow_results(results):
    for r in results:
        print(f"[Архив] {r.title}: {r.what}")

# Полный поиск: sync + async
sync_results = memory.search_full(
    "конфигурация",
    limit=5,
    async_callback=handle_slow_results
)
# sync_results — сразу из Fast/Medium
# handle_slow_results вызовется позже с результатами из Slow
```

### Получение контекста

```python
# Контекст для инъекции в промпт
context = memory.get_context(limit=10, project="MyProject")
for entry in context:
    print(f"- {entry.title}: {entry.what}")
```

### Интеграция с существующим EchoVault

```python
from memory.unified_adapter import create_unified_adapter

# Адаптер для постепенной миграции
adapter = create_unified_adapter(memory_home="~/.memory")
await adapter.start()

# Писать в обе системы
adapter.save_unified(
    memory_id="...",
    title="...",
    what="...",
    project="..."
)

# Поиск в unified (fallback к существующей)
results = adapter.search_unified("query")
```

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                   UnifiedMemoryService                   │
├──────────────┬──────────────┬───────────────────────────┤
│   FastTier   │  MediumTier  │        SlowTier           │
│  (in-memory) │    (SSD)     │        (HDD)              │
├──────────────┼──────────────┼───────────────────────────┤
│ SQLite :mem  │ SQLite file  │ SQLite file + embeddings  │
│ 24h TTL      │ 7d retention │ Бессрочно                 │
│ Sync search  │ FTS search   │ Async semantic search     │
│ Cleanup 60s  │ LRU eviction │ Background worker         │
└──────────────┴──────────────┴───────────────────────────┘
       ↑              ↑                    ↑
   Migration Pipeline (каждые 5 минут)
```

## Файлы

- `src/memory/unified.py` — Core implementation (887 строк)
- `src/memory/unified_adapter.py` — Интеграция с существующим
- `tests/test_unified_memory.py` — Тесты
- `src/memory/unified.pyi` — Type stubs

## TODO для production

1. **Интеграция MCP**: Добавить tools для unified search
2. **Мониторинг**: Метрики по тирам (hit rate, latency)
3. **Настройки**: Configurable TTL, размеры, пути
4. **Восстановление**: Startup scan для consistency
5. **Graph relations**: Связи между сущностями
6. **Конфликт-резолюшн**: Merge вместо INSERT OR REPLACE

# EchoVault Specifications Guide / Руководство по спецификациям EchoVault

**English:** All project specifications are now stored in EchoVault for efficient semantic search.

**Русский:** Все спецификации проекта теперь хранятся в EchoVault для эффективного семантического поиска.

## New EchoVault Features (2026-04-06) / Новые функции EchoVault (2026-04-06)

### 1. Cached Embeddings / Кэшированные эмбеддинги
| English | Русский |
|---------|---------|
| LRU cache for embedding providers to reduce latency from ~200ms to ~5ms on repeated queries. | LRU кэш для провайдеров эмбеддингов для снижения задержки с ~200мс до ~5мс на повторных запросах. |

```python
from memory.embeddings import OllamaEmbedding, CachedEmbeddingProvider

provider = CachedEmbeddingProvider(
    OllamaEmbedding(model="nomic-embed-text"),
    maxsize=1000,  # LRU cache size
    ttl_seconds=None  # Optional TTL
)
```

### 2. Temporal Queries / Временные запросы
| English | Русский |
|---------|---------|
| Search by time range and calendar dates. | Поиск по диапазону времени и календарным датам. |

```python
# Search by timestamp range
results = memory.search_by_time_range(
    start_timestamp=1609459200,
    end_timestamp=1640995200
)

# Search by calendar date (e.g., "what we did in March 2025")
results = memory.search_by_date(2025, month=3)  # March 2025
results = memory.search_by_date(2025, month=3, day=15)  # March 15, 2025
```

### 3. LLM-Based Compression / LLM-компрессия
| English | Русский |
|---------|---------|
| Semantic compression for Slow tier using LLM summarization. | Семантическая компрессия для Slow tier с использованием LLM суммаризации. |

```python
from memory.compression import OllamaCompressor, OpenAICompressor

# Ollama-based compression
compressor = OllamaCompressor(
    model="qwen2.5:7b",
    base_url="http://localhost:11434"
)

# Or OpenAI-based
compressor = OpenAICompressor(
    model="gpt-4o-mini",
    api_key="your-key"
)

memory = create_unified_memory(compression_provider=compressor)
```

### 4. Graph Relations / Графовые отношения
| English | Русский |
|---------|---------|
| Model relationships between memory entries: depends_on, related_to, part_of, supersedes. | Моделирование отношений между записями: depends_on, related_to, part_of, supersedes. |

```python
from memory.graph_relations import MemoryRelation, RelationType

# Add relation
memory.graph.add_relation(MemoryRelation(
    source_id="entry-1",
    target_id="entry-2",
    relation_type=RelationType.DEPENDS_ON,
    strength=0.9,
    notes="Depends on config"
))

# Find path between entries
path = memory.graph.get_path("A", "B", max_depth=3)

# Get transitive dependencies
deps = memory.graph.get_dependencies("entry-id")

# Find cycles
cycles = memory.graph.find_cycles("entry-id")
```

---

## How to Use Specifications / Как использовать спецификации

### Searching Specifications

```javascript
// Find all specifications
mcp_echovault_memory_search({
  query: "specs requirements design",
  limit: 10
})

// Find specific specification
mcp_echovault_memory_search({
  query: "docker optimization requirements",
  limit: 5
})

// Find by topic
mcp_echovault_memory_search({
  query: "github actions workflow",
  limit: 5
})
```

## Available Specifications / Доступные спецификации

### CI/CD and Automation / CI/CD и Автоматизация
| Spec / Спека | EN | RU |
|--------------|----|----|
| **cancel-old-workflows** | automatic cancellation of old workflows | автоматическая отмена старых workflow |
| **fix-github-actions** | fixing GitHub Actions | исправление GitHub Actions |
| **manual-release-process** | manual release process | ручной процесс релиза |
| **restore-missing-releases** | restoring missing releases | восстановление недостающих релизов |

### Docker and Build / Docker и Сборка
| Spec / Спека | EN | RU |
|--------------|----|----|
| **docker-windows-optimization** | Docker optimization for Windows | оптимизация Docker для Windows |
| **fix-docker-sdk-download** | fixing SDK download | исправление загрузки SDK |
| **openwrt-build-optimization** | OpenWrt build optimization | оптимизация сборки OpenWrt |

### Functionality / Функциональность
| Spec / Спека | EN | RU |
|--------------|----|----|
| **captive-portal-automation** | captive portal automation | автоматизация captive portal |
| **daemon-cookie-management** | cookie management in daemon | управление cookie в демоне |
| **remove-ipv6-support** | removing IPv6 support | удаление поддержки IPv6 |

## Query Examples / Примеры запросов

```javascript
// Find requirements for Docker optimization
mcp_echovault_memory_search({
  query: "docker windows optimization requirements",
  limit: 3
})

// Find design for GitHub Actions
mcp_echovault_memory_search({
  query: "github actions fix design",
  limit: 3
})

// Find tasks for captive portal
mcp_echovault_memory_search({
  query: "captive portal automation tasks",
  limit: 3
})

// Find all requirements
mcp_echovault_memory_search({
  query: "requirements EARS SHALL",
  limit: 10
})

// Find correctness properties
mcp_echovault_memory_search({
  query: "correctness properties for any",
  limit: 10
})
```

## Specification Structure / Структура спецификации

Each specification contains:

1. **requirements.md** - requirements in EARS format
   - Ubiquitous: THE {system} SHALL {response}
   - Event-driven: WHEN {trigger}, THE {system} SHALL {response}
   - State-driven: WHILE {condition}, THE {system} SHALL {response}
   - Unwanted event: IF {condition}, THEN THE {system} SHALL {response}
   - Optional feature: WHERE {option}, THE {system} SHALL {response}

2. **design.md** - detailed design with correctness properties
   - Property N: {description}
   - For any {condition}, {property should hold}
   - Validates: Requirements X.Y

3. **tasks.md** - implementation task list
   - Tasks with checkboxes
   - Links to requirements
   - Priorities and dependencies

## Working with Specifications / Работа со спецификациями

### Creating New Specification

1. Create directory in `.kiro/specs-old/{feature-name}/`
2. Create files: requirements.md, design.md, tasks.md
3. Load into EchoVault via PowerShell script

### Updating Specification

1. Update files in `.kiro/specs-old/{feature-name}/`
2. Reload into EchoVault
3. Reindex: `memory reindex`

### Searching Specifications

```javascript
// Semantic search across all specifications
mcp_echovault_memory_search({
  query: "your query",
  limit: 5
})

// Filter by category
mcp_echovault_memory_search({
  query: "category:context tags:specs",
  limit: 10
})
```

## Legacy Files / Legacy файлы

Original specifications preserved in `.kiro/specs-old/` for reference and editing.

## Benefits / Преимущества

| # | English | Русский |
|---|---------|---------|
| 1 | **Semantic search** - finds relevant specifications by query meaning | **Семантический поиск** — находит релевантные спецификации по смыслу запроса |
| 2 | **Fast access** - no need to manually search files | **Быстрый доступ** — не нужно искать файлы вручную |
| 3 | **Contextual search** - finds related requirements, design and tasks | **Контекстный поиск** — находит связанные требования, дизайн и задачи |
| 4 | **Token efficiency** - only needed information loaded | **Эффективность токенов** — загружается только нужная информация |
| 5 | **Change history** - all versions saved in EchoVault | **История изменений** — все версии сохранены в EchoVault |

## Workflow Patterns / Паттерны workflow

### Starting Work on Feature / Начало работы над фичей

```javascript
// 1. Find specification / Найти спецификацию
mcp_echovault_memory_search({
  query: "feature-name requirements",
  limit: 3
})

// 2. Find design / Найти дизайн
mcp_echovault_memory_search({
  query: "feature-name design properties",
  limit: 3
})

// 3. Find tasks / Найти задачи
mcp_echovault_memory_search({
  query: "feature-name tasks",
  limit: 3
})
```

### Coverage Check / Проверка покрытия

```javascript
// Find all requirements / Найти все требования
mcp_echovault_memory_search({
  query: "feature-name requirements SHALL",
  limit: 10
})

// Find all properties / Найти все свойства
mcp_echovault_memory_search({
  query: "feature-name property validates",
  limit: 10
})
```

### Troubleshooting / Устранение проблем

```javascript
// Find similar problems / Найти похожие проблемы
mcp_echovault_memory_search({
  query: "problem description",
  limit: 5
})

// Find solutions / Найти решения
mcp_echovault_memory_search({
  query: "solution approach",
  limit: 5
})
```

---

*Last updated: 2026-04-06 / Последнее обновление: 2026-04-06*
*EchoVault Version: Unified Memory Model with Caching, Temporal Queries, Compression, and Graph Relations*
*Версия EchoVault: Unified Memory Model с кэшированием, временными запросами, компрессией и графовыми отношениями*

# Changelog / История изменений

**English:** All notable changes to this project will be documented in this file.

**Русский:** Все значимые изменения проекта документируются в этом файле.

**English:** The format is inspired by Keep a Changelog and follows semantic versioning.

**Русский:** Формат основан на Keep a Changelog и следует семантическому версионированию.

## [Unreleased] / Не выпущено

## [0.4.0] - 2026-03-25

### Changed / Изменено
| English | Русский |
|---------|---------|
| **Rewrote the terminal dashboard in Rust** using ratatui + crossterm. Dashboard is now a 3MB standalone binary with instant startup. | **Переписал терминальный дашборд на Rust** используя ratatui + crossterm. Дашборд теперь — 3MB standalone бинарник с мгновенным стартом. |
| Removed Textual dependency — smaller install footprint. | Удалена зависимость Textual — меньший размер установки. |
| `memory dashboard` executes Rust binary instead of Python TUI. | `memory dashboard` запускает Rust бинарник вместо Python TUI. |
| k9s-style navigation: `1`-`4` panels, `j`/`k`/`g`/`G` vim nav, `/` search, `:` palette. | Навигация в стиле k9s: `1`-`4` панели, `j`/`k`/`g`/`G` vim, `/` поиск, `:` палитра. |
| Memory editing opens `$EDITOR` (vim) with memory as YAML. | Редактирование открывает `$EDITOR` (vim) с памятью как YAML. |
| Duplicate detection runs in background thread — UI responsive. | Обнаружение дубликатов в фоновом потоке — UI отзывчивый. |
| Added `--version` flag to CLI. | Добавлен флаг `--version` в CLI. |
| Added Project column to memories table. | Добавлена колонка Project в таблицу воспоминаний. |

### Added / Добавлено
- `dashboard/` directory with Rust source / директория с Rust исходниками
- Confirmation dialogs (y/n) for destructive actions / Диалоги подтверждения (y/n) для деструктивных действий
- Toast-style notifications / Toast-уведомления

### Removed / Удалено
- Python Textual dashboard package / Python Textual пакет дашборда
- `textual` dependency from `pyproject.toml` / зависимость `textual`

## [0.3.0] - 2026-03-25

### Changed / Изменено
| English | Русский |
|---------|---------|
| Intermediate Textual dashboard redesign (superseded by 0.4.0 Rust rewrite). | Промежуточный редизайн Textual дашборда (заменён Rust переписыванием в 0.4.0). |

## [0.2.1] - 2026-03-24

### Changed / Изменено
| English | Русский |
|---------|---------|
| Bumped version for post-release fixes. | Повышена версия для исправлений после релиза. |

## [0.2.0] - 2026-03-24

### Added / Добавлено
| English | Русский |
|---------|---------|
| Added `memory dashboard`, a Textual terminal dashboard for vault-wide browsing, editing, archive/restore flows. | Добавлен `memory dashboard`, Textual терминальный дашборд для просмотра, редактирования, архивирования. |
| Added archive-aware lifecycle metadata for memories. | Добавлены метаданные жизненного цикла с учётом архивирования. |
| Added stable markdown memory IDs so session files can be safely edited. | Добавлены стабильные ID для безопасного редактирования файлов сессий. |
| Added dashboard and lifecycle regression coverage. | Добавлено покрытие тестами дашборда и жизненного цикла. |

### Changed / Изменено
| English | Русский |
|---------|---------|
| Reworked markdown session handling into round-trippable parser/writer. | Переработана обработка сессий Markdown в round-trippable парсер/писатель. |
| Archived memories excluded from normal search by default. | Архивированные воспоминания исключены из обычного поиска по умолчанию. |
| Improved `memory import` deduplication to key on `(project, file_path, section_anchor)`. | Улучшено дедуплицирование `memory import` по `(project, file_path, section_anchor)`. |
| Documented the new dashboard command in the README. | Документирована новая команда дашборда в README. |

### Fixed / Исправлено
| English | Русский |
|---------|---------|
| Fixed import behavior for same-title memories across session files. | Исправлено поведение импорта для воспоминаний с одинаковыми заголовками. |
| Fixed import decoding for legacy cp1251 and UTF-8 BOM/CRLF. | Исправлено декодирование импорта для legacy cp1251 и UTF-8 BOM/CRLF. |


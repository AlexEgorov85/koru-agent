# План доработки документации

**Дата:** 5 апреля 2026 г.
**Цель:** Поднять качество документации с 62% до 90%+

---

## Этап 1 — Критические исправления (P0)

### 1.1 Заменить placeholder-текст в logging/*.md
**Файлы:** `docs/logging/README.md`, `docs/logging/cli.md`, `docs/logging/retention.md`, `docs/logging/structure.md`

**Проблема:** Файлы содержат `[см. выше...]` вместо реального содержимого.

**Задачи:**
- [ ] 1.1.1 README.md — заменить все placeholder-блоки на реальное содержимое
  - Секция "Архитектура correlation ID" — добавить диаграмму
  - Секция "Структура папок" — добавить дерево директорий
  - Секция "Быстрый старт" — добавить примеры кода
  - Секция "Поиск логов" — добавить примеры команд
  - Секция "Форматы логов" — добавить примеры JSON
  - Секция "Конфигурация" — добавить YAML
  - Секция "Метрики" — добавить таблицу
- [ ] 1.1.2 cli.md — добавить реальный вывод скриптов для каждого раздела
  - find_latest_session.py — вывод
  - find_session.py — вывод
  - find_last_llm.py — вывод
  - cleanup_old_logs.py — вывод
  - check_log_size.py — вывод
  - rebuild_index.py — вывод
  - export_session.py — вывод
- [ ] 1.1.3 retention.md — добавить реальные примеры
  - Алгоритм очистки
  - Примеры сжатия
  - Восстановление после очистки
- [ ] 1.1.4 structure.md — добавить реальные примеры
  - Полное дерево директорий
  - Примеры JSONL записей индексов
  - YAML конфиг логирования

### 1.2 Обновить guides/book_library.md
**Файл:** `docs/guides/book_library.md`

**Проблема:** Некорректные пути, несуществующие ссылки.

**Задачи:**
- [ ] 1.2.1 Проверить актуальные пути файлов skill
  - `core/application/skills/book_library/` → реальный путь
  - `core/application/skills/book_library/skill.py` → реальный путь
  - `core/application/skills/book_library/scripts_registry.py` → реальный путь
- [ ] 1.2.2 Проверить существование и обновить ссылки
  - `run_book_library_example.py` — существует?
  - `analyze_library_schema.py` — существует?
  - `BOOK_LIBRARY_README.md` — существует? (самоссылка?)
  - `data/alerts/book_library_alerts.yaml` — существует?
- [ ] 1.2.3 Обновить версию (v1.2.1 → актуальная)
- [ ] 1.2.4 Добавить раздел о vector search интеграции
- [ ] 1.2.5 Проверить примеры кода на актуальность API

### 1.3 Исправить EventBusLogger → _publish_with_context()
**Файлы:** `docs/guides/async_best_practices.md`, `docs/guides/user_messages.md`

**Проблема:** Примеры используют EventBusLogger, который запрещён в AGENTS.md.

**Задачи:**
- [ ] 1.3.1 async_best_practices.md — Раздел 6 "Логирование"
  - Заменить `event_bus_logger.info()` → `_publish_with_context()`
  - Заменить `event_bus_logger.error()` → `_publish_with_context()`
  - Убрать проверку `if self.event_bus_logger:`
- [ ] 1.3.2 user_messages.md — Все примеры
  - Раздел "Использование" — `_publish_with_context()` вместо `event_bus_logger.user_*`
  - Раздел "Примеры для разных сценариев" — все примеры
  - Раздел "Архитектура" — обновить диаграмму
  - Раздел "TerminalLogHandler" — обновить код
  - Раздел "Best Practices" — все примеры
  - Раздел "Примеры использования" — все 3 сценария
- [ ] 1.3.3 RULES.MD — Раздел 5 "Логирование и Метрики"
  - Убрать упоминание EventBusLogger
  - Добавить `_publish_with_context()` как основной способ

### 1.4 Исправить битые ссылки
**Файлы:** Несколько

**Задачи:**
- [ ] 1.4.1 guides/vector_search.md — удалить ссылку на `ARCHITECTURE_DECISIONS.md` (не существует)
- [ ] 1.4.2 logging/README.md — создать `logging/formats.md` или удалить ссылку
- [ ] 1.4.3 adr/0001-modular-architecture.md — `docs/architecture.md` → `docs/architecture/`
- [ ] 1.4.4 adr/0002-contract-validation.md — проверить `core/application/data_repository.py`
- [ ] 1.4.5 async_best_practices.md — исправить ссылки:
  - `./lifecycle.md` → `../architecture/lifecycle.md`
  - `LOGGING_GUIDE.md` → `../logging/README.md`
  - `EVENT_BUS_MIGRATION.md` → удалить или создать

---

## Этап 2 — Синхронизация и обновление (P1)

### 2.1 Синхронизировать метрики зрелости
**Файлы:** `docs/architecture/ideal.md`, `docs/architecture/checklist.md`

**Проблема:** ideal.md = 90%, checklist.md = 95%.

**Задачи:**
- [ ] 2.1.1 Определить актуальную метрику зрелости
- [ ] 2.1.2 Обновить ideal.md
- [ ] 2.1.3 Обновить checklist.md
- [ ] 2.1.4 Обновить дорожную карту в ideal.md (16 часов → актуально)

### 2.2 Обновить даты и версии
**Файлы:** Все файлы с датой `2026-03-15` и версией `5.35.0`

**Задачи:**
- [ ] 2.2.1 docs/README.md → дата, версия
- [ ] 2.2.2 docs/architecture/README.md → дата, версия
- [ ] 2.2.3 docs/components/README.md → дата, версия
- [ ] 2.2.4 docs/guides/README.md → дата, версия
- [ ] 2.2.5 vector_search/README.md → статус реализации проверить

### 2.3 Исправить docs/README.md
**Файл:** `docs/README.md`

**Проблема:** Пропущенные разделы и ссылки.

**Задачи:**
- [ ] 2.3.1 Добавить секцию "Для кого эта документация"
- [ ] 2.3.2 Добавить шаги 2 и 3 в "Быстрый старт"
- [ ] 2.3.3 Добавить ссылку на optimization_fix_plan.md
- [ ] 2.3.4 Добавить ссылку на guides/user_messages.md
- [ ] 2.3.5 Добавить ссылку на guides/existing_types_guide.md
- [ ] 2.3.6 Добавить ссылку на guides/async_best_practices.md

### 2.4 Обновить docs/components/
**Файлы:** `docs/components/application/context.md`, `docs/components/infrastructure/context.md`, `docs/components/README.md`

**Задачи:**
- [ ] 2.4.1 application/context.md — добавить документацию по:
  - `clone_with_version_override()`
  - `lifecycle_manager.clear_resources()`
  - Изоляция кэшей между контекстами
- [ ] 2.4.2 infrastructure/context.md — проверить актуальность ComponentState
- [ ] 2.4.3 components/README.md — добавить ссылки на:
  - OptimizationOrchestrator
  - SafetyLayer
  - VersionManager

### 2.5 Обновить lifecycle.md
**Файл:** `docs/architecture/lifecycle.md`

**Задачи:**
- [ ] 2.5.1 Проверить существование `core/components/lifecycle.py`
- [ ] 2.5.2 Исправить `is_initialized` (SHUTDOWN ≠ initialized)
- [ ] 2.5.3 Добавить `clone_with_version_override()`
- [ ] 2.5.4 Добавить `clear_resources()`

---

## Этап 3 — Новая документация (P2)

### 3.1 Оптимизация промптов
**Новые файлы:**
- `docs/components/optimization/orchestrator.md`
- `docs/components/optimization/safety_layer.md`
- `docs/components/optimization/version_manager.md`

**Задачи:**
- [ ] 3.1.1 Orchestrator — архитектура, поток данных, конфигурация, примеры
- [ ] 3.1.2 SafetyLayer — типы проверок, конфигурация порогов, примеры
- [ ] 3.1.3 VersionManager — lifecycle версий, promote/rollback, примеры

### 3.2 Ключевые компоненты
**Новые файлы:**
- `docs/components/action_executor.md`
- `docs/services/llm_orchestrator.md`
- `docs/services/prompt_service.md`
- `docs/services/contract_service.md`

**Задачи:**
- [ ] 3.2.1 ActionExecutor — механизм взаимодействия компонентов
- [ ] 3.2.2 LLMOrchestrator — маршрутизация провайдеров, retry логика
- [ ] 3.2.3 PromptService — загрузка, кэширование, версионирование
- [ ] 3.2.4 ContractService — валидация контрактов, Pydantic модели

### 3.3 Бенчмарки и метрики
**Новые файлы:**
- `docs/guides/benchmarking.md`
- `docs/guides/metrics.md`

**Задачи:**
- [ ] 3.3.1 benchmarking.md — как запускать, интерпретировать результаты
- [ ] 3.3.2 metrics.md — система data/metrics/, агрегация, алерты

### 3.4 OpenRouter провайдер
**Новый файл:** `docs/infrastructure/openrouter_provider.md`

**Задачи:**
- [ ] 3.4.1 Архитектура провайдера
- [ ] 3.4.2 Конфигурация
- [ ] 3.4.3 Тесты

---

## Этап 4 — Чек-листы и векторная документация (P2-P3)

### 4.1 Проверить чек-листы в vector_search
**Файлы:** `CHUNKING_STRATEGY.md`, `UNIVERSAL_SPEC.md`, `VECTOR_LIFECYCLE.md`

**Проблема:** Все чек-листы отмечены `[ ]` — не выполнено?

**Задачи:**
- [ ] 4.1.1 CHUNKING_STRATEGY.md — проверить реализацию 5 стратегий
- [ ] 4.1.2 UNIVERSAL_SPEC.md — проверить реализацию ЭТАП 1/2/3
- [ ] 4.1.3 VECTOR_LIFECYCLE.md — проверить реализацию сервисов
- [ ] 4.1.4 Обновить статусы: `[ ]` → `[x]` или удалить нереализованное

### 4.2 Исправить пути в vector_search/README.md
**Файл:** `docs/vector_search/README.md`

**Задачи:**
- [ ] 4.2.1 `../../docs/api/...` → `../api/...`
- [ ] 4.2.2 `../../docs/guides/...` → `../guides/...`

### 4.3 Скрипты документации
**Новые файлы:**
- `docs/scripts/run_skill_directly.md`
- `docs/scripts/run_orchestrator_benchmark.md`

**Задачи:**
- [ ] 4.3.1 run_skill_directly.md — назначение, аргументы, примеры
- [ ] 4.3.2 run_orchestrator_benchmark.md — назначение, аргументы, примеры

---

## Этап 5 — Финальная проверка (P3)

### 5.1 Глоссарий
**Новый файл:** `docs/glossary.md`

**Задачи:**
- [ ] 5.1.1 Основные термины (Capability, Contract, Prompt, Skill, Tool, Service)
- [ ] 5.1.2 Архитектурные термины (InfrastructureContext, ApplicationContext, SessionContext)
- [ ] 5.1.3 Оптимизация (Baseline, Candidate, Safety Check, Promote)

### 5.2 Перекрёстная проверка
**Задачи:**
- [ ] 5.2.1 Все ссылки валидны
- [ ] 5.2.2 Нет дублирующейся информации с противоречиями
- [ ] 5.2.3 Все примеры кода соответствуют текущему API
- [ ] 5.2.4 Все пути файлов корректны
- [ ] 5.2.5 Все даты и версии актуальны

### 5.3 Повторный аудит
**Задачи:**
- [ ] 5.3.1 Запустить проверку аналогично текущему аудиту
- [ ] 5.3.2 Цель: 90%+ по всем критериям
- [ ] 5.3.3 Обновить audit_report.md

---

## 📊 Целевые метрики

| Критерий | Текущий | Цель |
|----------|---------|------|
| Полнота | 65% | 90% |
| Актуальность | 55% | 90% |
| Консистентность | 60% | 90% |
| Качество | 70% | 90% |
| **ИТОГО** | **62%** | **90%** |

---

## 📅 Приоритизация по времени

| Этап | Приоритет | Файлов | Задач |
|------|-----------|--------|-------|
| Этап 1: Критические | P0 | ~8 | 25 |
| Этап 2: Синхронизация | P1 | ~8 | 20 |
| Этап 3: Новая документация | P2 | ~10 | 12 |
| Этап 4: Чек-листы | P2-P3 | ~5 | 8 |
| Этап 5: Финальная проверка | P3 | ~2 | 9 |
| **ИТОГО** | | **~33** | **74** |

---

*План сформирован автоматически, 5 апреля 2026 г.*

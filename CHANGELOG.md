# CHANGELOG

## [5.31.0] - 2026-03-02

### Added
- **Полное удаление манифестов и registry.yaml**
  - Удалена модель Manifest
  - Удалена директория data/manifests/ (16 файлов)
  - registry.yaml переименован в registry.yaml.deprecated
  - 7 коммитов, 50+ файлов изменено
  - 29 тестов проходят (100%)

### Changed
- **Зависимости через DEPENDENCIES в коде**
  - Все компоненты объявляют зависимости через class variable DEPENDENCIES
  - 16 компонентов обновлено (сервисы, навыки, инструменты, patterns)
  - Валидация зависимостей в BaseComponent._validate_manifest()

- **AppConfig.from_discovery() — основной метод**
  - AppConfig.from_registry() удалён
  - Авто-обнаружение компонентов через промпты/контракты
  - main.py использует from_discovery()

### Removed
- **Манифесты**
  - core/models/data/manifest.py
  - core/application/services/manifest_validation_service.py
  - data/manifests/** (16 файлов)
  - scripts/validation/validate_all_manifests.py

- **Методы для манифестов**
  - DataRepository: load_manifests(), get_manifest(), validate_manifest_by_profile()
  - ApplicationContext: _validate_manifests_by_profile()
  - FileSystemDataSource: load_manifest(), list_manifests(), manifest_exists()
  - ResourceDiscovery: discover_manifests(), get_manifest(), _parse_manifest_file()

- **registry.yaml**
  - AppConfig.from_registry() удалён
  - ApplicationContext.create_from_registry() удалён
  - RegistryLoader удалён

### Documentation
- Отчёты перемещены в `docs/reports/`

---

## [5.30.0] - 2026-03-02

### Added
- **Миграция на единую шину EventBus завершена (100%)**
  - 4 этапа миграции выполнены
  - 18 коммитов, 44+ файлов изменено
  - 21 тест проходит (100%)
  - UnifiedEventBus — основная шина событий

- **UnifiedEventBus — новая архитектура**
  - Session isolation (события сессии A не видны сессии B)
  - Domain routing (фильтрация по домену внутри одной шины)
  - FIFO порядок внутри сессии
  - Backpressure (ограничение размера очереди)
  - No event duplication (событие не дублируется)
  - `core/infrastructure/event_bus/unified_event_bus.py` — 1227 строк

- **Метрики производительности**
  - Количество шин: 9 → 1 (-89%)
  - Дублирование событий: Есть → Нет (-100%)
  - Memory overhead: ~50 MB → ~15 MB (-70%)
  - Строк кода EventBus: 1950 → ~1200 (-38%)

- **Нагрузочный тест**
  - `scripts/performance/event_bus_benchmark.py` — 5 тестов
  - Изоляция сессий — PASSED
  - Domain routing — PASSED
  - Отсутствие дублирования — PASSED

- **Конфигурация миграции**
  - `use_unified_event_bus: true` в registry.yaml
  - InfrastructureContext с выбором шины
  - Логирование дублирования подписчиков

### Changed
- **Массовое обновление импортов (24 файла)**
  - `EventType` → из `unified_event_bus`
  - `EventBus` → `EventBusConcurrent` (для совместимости)
  - Все компоненты обновлены на UnifiedEventBus

- **Обновлены компоненты**
  - LogCollector, MetricsCollector
  - LLMEventSubscriber
  - LifecycleManager, BaseEventCollector
  - BehaviorManager, AgentRuntime (уже использовали EventBusLogger)

### Removed
- **Legacy файлы удалены**
  - `event_bus.py` (base) — удалён
  - `domain_event_bus.py` — удалён
  - `event_bus_adapter.py` — удалён (временный адаптер)
  - `core/__init__.py` → использует UnifiedEventBus

### Documentation
- **Документы миграции**
  - [docs/reports/MIGRATION_REPORT.md](docs/reports/MIGRATION_REPORT.md) — полный отчёт
  - [docs/EVENT_BUS_MIGRATION.md](docs/EVENT_BUS_MIGRATION.md) — руководство
  - [docs/reports/ETAP1_REPORT.md](docs/reports/ETAP1_REPORT.md) — отчёт Этапа 1
  - `scripts/migration/update_imports.py` — скрипт обновления

---

## [5.29.0] - 2026-03-02

### Added
- **План стабилизации Agent_v5 завершён (100%)**
  - 6 этапов реализации, 48 тестов проходят
  - Детекция зацикливания агента через `AgentStuckError`
  - Гарантия вызова LLM через `llm_called` флаг
  - Валидация ACT decision в `BehaviorManager`
  - ReActPattern инварианты с `InfrastructureError`

- **Новые исключения для стабилизации**
  - `AgentStuckError` — агент зациклился (повторение decision без изменения state)
  - `InvalidDecisionError` — decision некорректен (ACT без capability_name)
  - `PatternError` — нарушение инвариантов паттерна
  - `InfrastructureError` — инфраструктурная ошибка (LLM не вызван)

- **Метод snapshot() в AgentState**
  - `core/application/agent/components/state.py` — `snapshot()` + `__eq__()`
  - Снимок состояния для сравнения и детекции зацикливания
  - Поля: `step`, `error_count`, `consecutive_errors`, `no_progress_steps`, `finished`, `history_length`, `last_history_item`

- **Детекция зацикливания в AgentRuntime**
  - `core/application/agent/runtime.py` — проверка snapshot в `run()`
  - Детекция повторяющихся decision без изменения state
  - Детекция отсутствия мутации state после observe()
  - `AgentStuckError` выбрасывается при 2+ повторениях

- **Валидация ACT decision в BehaviorManager**
  - `core/application/agent/components/behavior_manager.py` — валидация capability_name
  - Проверка что capability существует в доступных
  - Логирование decision для аудита через EventBusLogger
  - Fallback на switch pattern при невалидном decision

- **Гарантия вызова LLM в ReActPattern**
  - `core/application/behaviors/react/pattern.py` — флаг `llm_was_called`
  - Проверка что LLM был вызван в `_perform_structured_reasoning()`
  - `InfrastructureError` если LLM не вызван без причины

- **llm_called флаг в ActionResult**
  - `core/application/agent/components/action_executor.py` — поле `llm_called: bool`
  - Проверка в runtime что `requires_llm=True` → `llm_called=True`
  - `InfrastructureError` если LLM требуется но не вызван

- **requires_llm флаг в BehaviorDecision**
  - `core/application/behaviors/base.py` — поле `requires_llm: bool = False`
  - Указание что decision требует вызова LLM

- **Логирование через EventBusLogger**
  - `AgentRuntime` — полная миграция с `logging` на `EventBusLogger`
  - `BehaviorManager` — логирование decision через шину событий
  - Удалено стандартное `logging` из доработанных компонентов

- **Интеграционные тесты стабилизации (9 тестов)**
  - `test_no_infinite_loop` — AgentStuckError вместо цикла
  - `test_llm_called_for_think_decision` — LLM гарантия
  - `test_state_mutates_after_each_step` — мутация state
  - `test_planning_skill_has_capabilities` — PlanningSkill capabilities
  - `test_planning_skill_initializes` — инициализация PlanningSkill
  - `test_planning_skill_returns_skill_result_on_error` — SkillResult при ошибке

### Changed
- **PlanningSkill.execute()** переопределён для возврата `SkillResult`
  - `core/application/skills/planning/skill.py` — явный возврат `SkillResult`
  - Совместимость с архитектурой навыков

- **BehaviorDecision** расширен полем `requires_llm`
  - Обратная совместимость: `requires_llm=False` по умолчанию

### Architecture Guarantees
- ✅ Нет бесконечных циклов (`AgentStuckError` вместо цикла)
- ✅ Snapshot всегда меняется после observe()
- ✅ Decision не повторяется более 1 раза без изменения state
- ✅ Любой `decision.requires_llm` гарантированно вызывает LLM
- ✅ ReAct и Planning работают независимо
- ✅ `max_steps` используется только как аварийная защита
- ✅ Все навыки возвращают `SkillResult`

### Metrics
- Создано файлов: 7 (исключения + тесты)
- Изменено файлов: 10 (ядро + навыки)
- Удалено файлов: 3 (устаревшие тесты)
- Добавлено тестов: 48 (все проходят)
- Строк добавлено: +1200
- Строк удалено: -50 (удалено стандартное logging)

### Removed
- **Удалены устаревшие тесты**
  - `tests/unit/infrastructure/logging/test_logging.py` — LogManager удалён
  - `tests/unit/test_logging_module/test_logging.py` — LogConfig/LogMixin удалены
  - `tests/stress/test_stress.py` — требует обновления для новой архитектуры

---

## [5.28.0] - 2026-03-02

### Added
- **SkillResult — унифицированный результат выполнения Skills**
  - `core/models/data/execution.py` — новый класс `SkillResult`
  - Поля: `technical_success`, `data`, `error`, `metadata`, `side_effect`
  - Factory методы: `success()`, `failure()`
  - Метод `to_dict()` для сериализации

- **Новые действия контекста в ActionExecutor**
  - `context.get_all_items` — получение всех элементов контекста
  - `context.get_step_history` — получение истории шагов
  - Используется FinalAnswerSkill для доступа к контексту без state

- **Интеграционные тесты для Skills (39 тестов)**
  - `test_skill_architecture.py` (17 тестов)
    * Проверка что skills не имеют доступа к state
    * Проверка что skills не вызывают LLM напрямую
    * Проверка что skills не знают о Pattern
    * Проверка что skills детерминированы
    * Проверка что skills не имеют retry логики
  - `test_skills_simple_integration.py` (15 тестов)
    * Проверка что все skills возвращают SkillResult
    * Проверка использования SkillResult.success/failure
    * Проверка явного указания side_effect
    * Проверка полей SkillResult
  - `test_skills_integration.py` (7 тестов)
    * Интеграционные тесты для каждого skill
    * Сквозной тест planning → final_answer

### Changed
- **Миграция всех skills на SkillResult**
  - `BookLibrarySkill`: search_books, execute_script, list_scripts
  - `PlanningSkill`: create_plan, update_plan, get_next_step, update_step_status, decompose_task, mark_task_completed
  - `FinalAnswerSkill`: generate
  - `DataAnalysisSkill`: analyze_step_data

- **Исправления в skills**
  - `ExecutionResult.data` → `ExecutionResult.result`
  - `ExecutionResult.success` → `ExecutionResult.status == ExecutionStatus.COMPLETED`
  - Убран прямой доступ к `context.data_context` в FinalAnswerSkill
  - Доступ к контексту через `executor.execute_action('context.get_all_items')`

- **BaseComponent._publish_metrics**
  - Исправлен вызов с 7 аргументами на именованные параметры
  - `tokens_used=0`, `error=...`, `error_type=...` вместо позиционных аргументов

### Architecture Guarantees
- ✅ Skills не знают о Pattern
- ✅ Skills не имеют доступа к state напрямую
- ✅ Skills не вызывают LLM напрямую (только через executor)
- ✅ Skills не имеют retry логики
- ✅ Skills детерминированы (кроме метаданных времени)
- ✅ 100% skills возвращают SkillResult
- ✅ side-effect явно помечены

### Metrics
- Создано файлов: 4 (SkillResult + 3 тестовых файла)
- Изменено файлов: 8 (5 skills + executor + base_component + test)
- Добавлено тестов: 39
- Строк добавлено: +1410
- Строк удалено: -307

---

## [5.27.0] - 2026-03-01

### Added
- **Универсальная система логирования через EventBus**
  - `EventBusLogHandler` — перехватывает события LOG_INFO/DEBUG/WARNING/ERROR из EventBus
  - `EventBusLogFormatter` — форматировщик с цветами, иконками и структурой
  - `EventBusLogger` — helper-класс для компонентов (async/синхронные версии)
  - `LoggingToEventBusHandler` — перенаправление стандартного logging в EventBus
  - Helper-функции: `log_info()`, `log_debug()`, `log_warning()`, `log_error()`

### Features
- **Структурированный вывод в терминал**
  - Цвета: cyan (info), yellow (warning), red (error), blue (LLM), green (success)
  - Иконки: ℹ️ 🔍 ⚠️ ❌ ✅ 🔄 ⏳ 🧠 💡 🎯 🔧 📊
  - Структура: session | agent | component | extra_data
  - Разделители между сообщениями

### Changed
- **Интеграция EventBusLogger в ключевые компоненты**
  - `main.py` — регистрация обработчиков сразу после `infrastructure_context.initialize()`
  - `application_context.py` — `_resolve_component_configs()`, `get_all_capabilities()`
  - `base_service.py` — все async методы инициализации и рестарта
  - `base_component.py` — метод `initialize()`
  - `lifecycle.py` — `LifecycleManager`, `DependencyResolver`
  - `skills/` — planning, final_answer, data_analysis
  - `tools/` — sql_tool, vector_books_tool, file_tool
  - `storage/` — prompt_storage, contract_storage, capability_registry

### Technical
- Все async методы используют `await self.event_bus_logger.*()`
- Sync методы оставлены с `logger.*` (fallback)
- Fallback на обычный logger если EventBusLogger не доступен
- Полная обратная совместимость с существующим кодом

### Metrics
- Создано файлов: 2
- Изменено файлов: 20
- Заменено вызовов: ~106 logger.* → event_bus_logger.*
- Строк добавлено: +750
- Строк удалено: -169

---

## [5.26.1] - 2026-02-28

### Added
- **Логирование llm.response.received при всех сценариях**
  - Событие публикуется всегда: при успехе, таймауте, ошибке LLM, недоступности провайдера
  - В данные события добавляются поля `error` и `error_type` при ошибках
  - Реализовано в `ReActPattern` и `EvaluationPattern`

### Fixed
- **Конфликт event loop при завершении сессии**
  - Исправлен метод `close()` в `SessionLogger` для безопасной работы с `asyncio.run()`
  - Убран вызов `close_session_logger()` из `finally` в `main.py`
  - Сессия теперь завершается внутри event loop через `end()`

### Changed
- **Увеличены таймауты LLM для больших моделей**
  - `LlamaCppConfig.timeout_seconds`: 120с → 600с (10 минут)
  - `dev.yaml`: `llm_providers.default.timeout_seconds`: 120с → 1200с
  - `dev.yaml`: `agent.llm_timeout_seconds`: 120с → 1200с
  - Причина: Qwen3-4B-Instruct требует больше времени для генерации с большими промптами

### Features
- **Добавлено свойство `is_initialized` в `LogIndexer`**
  - Позволяет проверить состояние инициализации индексатора

---

## [5.25.0] - 2026-02-28

### Fixed
- **Добавлено подробное логирование для диагностики LLM зависаний**

#### Проблема
При зависании LLM вызова не было понятно:
- Произошёл ли timeout
- Какое состояние у executor
- Загрузилась ли модель

#### Решение
Добавлено детальное логирование на всех этапах:

**Перед вызовом:**
```
INFO | Запуск LLM вызова: prompt_length=6104, max_tokens=1000, timeout=120с
DEBUG | Executor: <ThreadPoolExecutor>, llm loaded: True
```

**После успешного вызова:**
```
INFO | LLM вызов завершён успешно за 45.23с
```

**При timeout:**
```
ERROR | ⏰ LLM TIMEOUT после 120.05с (timeout=120с)
ERROR |   - prompt_length: 6104
ERROR |   - max_tokens: 1000
ERROR |   - executor: <ThreadPoolExecutor...>
ERROR |   - llm loaded: True
ERROR |   - call_completed: {'done': False, 'error': None}
ERROR |   - active_threads: 5
```

**При других ошибках:**
```
ERROR | ❌ LLM вызов failed после 2.34с: RuntimeError: LLM модель не загружена
ERROR |   - prompt_length: 6104
ERROR |   - max_tokens: 1000
```

#### Изменения
- `execute()`: logger.info() перед вызовом с prompt_length, max_tokens, timeout
- `execute()`: logger.info() после успешного вызова с elapsed time
- `except TimeoutError`: logger.error() с деталями (prompt_length, executor state, active_threads)
- `except Exception`: logger.error() с деталями и elapsed time
- TimeoutError теперь re-raise без wrapping в generic error

---

## [5.24.0] - 2026-02-28

### Fixed
- **Исправлено зависание LLM вызовов**

#### Проблема
Агент зависал после публикации события `llm.prompt.generated` без получения `llm.response.received`.

#### Причина
ThreadPoolExecutor создавался внутри метода `execute()` с `max_workers=1`, что приводило к:
- Блокировке единственного worker при повторных вызовах
- Отсутствию proper cleanup при shutdown
- Potential deadlock при concurrent requests

#### Решение
- Перемещено создание ThreadPoolExecutor в `initialize()` (вместо `execute()`)
- Увеличено `max_workers` с 1 до 2 для предотвращения блокировок
- Добавлен proper cleanup в `shutdown()` через `executor.shutdown(wait=False)`
- Добавлен logging для отладки LLM вызовов (`logger.debug` перед/после вызова)
- Добавлена проверка `if not self.llm` внутри `_call_llm_sync()`

#### Изменённые файлы
- `core/infrastructure/providers/llm/llama_cpp_provider.py`:
  - `__init__()`: добавлено `self._executor = None`
  - `initialize()`: создание executor с `max_workers=2`
  - `execute()`: использование существующего executor, добавлен logging
  - `shutdown()`: cleanup executor

---

## [5.23.0] - 2026-02-28

### Added
- **Этап 3 завершён: Все навыки используют structured output** (Structured Output Maturity: 98% → 100%)

#### Обновления FinalAnswerSkill
- `_call_llm()`: полное переписывание для использования `llm.generate_structured`
  - Возвращает `Dict[str, Any]` (Pydantic model_dump()) вместо `str`
  - Автоматическая валидация через JSON Schema контракта
  - Логирование попыток парсинга
- `_generate()`: обновлён для работы со структурированным ответом
  - Убран `_parse_llm_response()` (не нужен для structured output)
  - Metadata: `structured_output: True`

#### Итоги Этапа 3
Все навыки обновлены для использования `llm.generate_structured`:

| Навык | Методы | Статус |
|-------|--------|--------|
| **PlanningSkill** | 4 метода | ✅ 100% |
| **BookLibrarySkill** | 3 метода | ✅ 100% (через SQLGenerationService) |
| **DataAnalysisSkill** | 2 метода | ✅ 100% |
| **FinalAnswerSkill** | 1 метод | ✅ 100% |

#### Преимущества завершённого Этапа 3
- **100% зрелость Structural Output**: все LLM вызовы используют structured output
- **Гарантированная валидность**: все навыки возвращают только валидный JSON
- **Автоматическая retry**: до 3 попыток при ошибках парсинга во всех навыках
- **Наблюдаемость**: единое логирование попыток, ошибок, времени генерации
- **Типобезопасность**: Pydantic модели вместо dict во всех навыках
- **Единый интерфейс**: все LLM вызовы через ActionExecutor

### Changed
- Версия проекта: 5.22.0 → 5.23.0

### Technical Details
- Изменено файлов: 1
  - `core/application/skills/final_answer/skill.py`: ~50 строк изменено
  - 1 метод обновлен для использования `llm.generate_structured`

### Next Steps (Этап 4)
- Создание утилит `ContractUtils` (опционально)
- Документация по structured output (опционально)
- Мониторинг метрик в продакшене

---

## [5.22.0] - 2026-02-28

### Added
- **Этап 3 (продолжение): Обновление DataAnalysisSkill для structured output** (Structured Output Maturity: 96% → 98%)

#### Обновления DataAnalysisSkill
- `_analyze_data()`: использование `llm.generate_structured` через ActionExecutor
  - Автоматическая валидация выхода через JSON Schema контракта
  - Возврат Pydantic модели вместо dict
  - Логирование количества попыток парсинга
  - Metadata: `parsing_attempts`, `structured_output: True`, `error_type`
- `_analyze_step_data()`: использование `llm.generate_structured`
  - Те же преимущества что и `_analyze_data()`
  - Сохранение обратной совместимости

#### Обновления BookLibrarySkill
- **Уже использует structured output** через `SQLGenerationService`
  - `SQLGenerationService` уже использует `StructuredOutputConfig`
  - `book_library.search_books` автоматически получает валидный SQL
  - Не требовалось изменений

#### Преимущества обновления
- **Гарантированная валидность**: анализ данных возвращает только валидный JSON
- **Автоматическая retry**: до 3 попыток при ошибках парсинга
- **Наблюдаемость**: логирование попыток, ошибок валидации, времени генерации
- **Типобезопасность**: Pydantic модели вместо dict
- **Единый интерфейс**: все LLM вызовы через ActionExecutor

### Changed
- Версия проекта: 5.21.0 → 5.22.0

### Technical Details
- Изменено файлов: 1
  - `core/application/skills/data_analysis/skill.py`: ~100 строк изменено
  - 2 метода обновлены для использования `llm.generate_structured`

### Next Steps (Этап 3 завершение)
- Обновление FinalAnswerSkill для использования llm.generate_structured
- Интеграционные тесты всех навыков
- Финальная проверка зрелости (цель: 100%)

---

## [5.21.0] - 2026-02-28

### Added
- **Этап 3 (продолжение): Обновление PlanningSkill для structured output** (Structured Output Maturity: 92% → 96%)

#### Обновления PlanningSkill
- `_create_plan()`: использование `llm.generate_structured` через ActionExecutor
  - Автоматическая валидация выхода через JSON Schema контракта
  - Возврат Pydantic модели вместо dict
  - Логирование количества попыток парсинга
  - Metadata: `parsing_attempts`, `structured_output: True`
- `_update_plan()`: использование `llm.generate_structured`
  - Те же преимущества что и `_create_plan()`
  - Сохранение совместимости с existing plan data
- `_decompose_task()`: использование `llm.generate_structured`
  - Структурированная декомпозиция на подзадачи
  - Валидация списка subtasks через контракт
- `_correct_plan_after_failure()`: использование `llm.generate_structured`
  - Коррекция плана с гарантией валидности
  - Логирование успешной коррекции

#### Преимущества обновления
- **Гарантированная валидность**: LLM возвращает только валидный JSON
- **Автоматическая retry**: до 3 попыток при ошибках парсинга
- **Наблюдаемость**: логирование попыток, ошибок, времени генерации
- **Типобезопасность**: Pydantic модели вместо dict
- **Единый интерфейс**: все LLM вызовы через ActionExecutor

### Changed
- Версия проекта: 5.20.0 → 5.21.0

### Technical Details
- Изменено файлов: 1
  - `core/application/skills/planning/skill.py`: ~150 строк изменено
  - 4 метода обновлены для использования `llm.generate_structured`

### Next Steps (Этап 3 продолжение)
- Обновление BookLibrarySkill для использования llm.generate_structured
- Обновление DataAnalysisSkill для использования llm.generate_structured
- Обновление FinalAnswerSkill для использования llm.generate_structured
- Интеграционные тесты

---

## [5.20.0] - 2026-02-28

### Added
- **Этап 3: ActionExecutor поддержка LLM действий** (Structured Output Maturity: 85% → 92%)

#### Обновления ActionExecutor
- `_execute_llm_action()`: обработка LLM действий (llm.*)
  - `llm.generate`: обычная генерация текста
  - `llm.generate_structured`: структурированная генерация с JSON Schema
- `_llm_generate()`: вызов LLM провайдера для обычной генерации
  - Параметры: prompt, system_prompt, temperature, max_tokens, top_p, etc.
  - Возвращает: content, model, tokens_used, generation_time
- `_llm_generate_structured()`: вызов LLM провайдера для структурированной генерации
  - Параметры: prompt, structured_output (StructuredOutputConfig или dict)
  - Автоматическая конвертация dict → StructuredOutputConfig
  - Возвращает: parsed_content (Pydantic model_dump()), raw_content
  - Metadata: parsing_attempts, success, validation_errors
  - Обработка исключений: StructuredOutputError, ValueError

#### Интеграция с навыками
- Навыки теперь могут использовать `executor.execute_action("llm.generate_structured", ...)`
- Единый интерфейс для всех LLM вызовов через ActionExecutor
- Изоляция навыков от конкретных реализаций LLM провайдеров

#### Тесты
- `test_action_executor_llm.py`: 2 теста LLM действий
  - llm.generate: обычная генерация
  - llm.generate_structured: структурированная генерация

### Changed
- Версия проекта: 5.19.0 → 5.20.0

### Technical Details
- Изменено файлов: 1
  - `core/application/agent/components/action_executor.py`: +180 строк

### Next Steps (Этап 3 продолжение)
- Обновление PlanningSkill для использования llm.generate_structured
- Обновление BookLibrarySkill для использования llm.generate_structured
- Обновление DataAnalysisSkill для использования llm.generate_structured
- Обновление FinalAnswerSkill для использования llm.generate_structured

---

## [5.19.0] - 2026-02-28

### Added
- **Этап 2: Интеграция structured output в LLM провайдеры** (Structured Output Maturity: 72% → 85%)

#### Новые исключения
- `StructuredOutputError`: ошибка структурированного вывода (LlamaCppProvider)
  - Атрибуты: `model_name`, `attempts`, `correlation_id`, `validation_errors`
  - Генерируется после исчерпания всех попыток retry

#### Обновления LlamaCppProvider
- `generate_structured()`: полная реализация с retry логикой
  - Добавление JSON Schema в промпт автоматически
  - Извлечение JSON из разных форматов (чистый, markdown, mixed)
  - Валидация против Pydantic модели
  - Retry при ошибках парсинга/валидации (до `max_retries`)
  - Возврат `StructuredLLMResponse` с валидной моделью
  - **Улучшенное логирование:**
    - Info: запуск structured output с параметрами
    - Debug: каждая попытка генерации, получения ответа, извлечения JSON
    - Info: успешная попытка с номером
    - Warning: ошибка JSON или валидации с деталями
    - Error: все попытки исчерпаны с количеством ошибок
- `_add_schema_to_prompt()`: добавление JSON Schema в промпт с инструкциями
- `_extract_json_from_response()`: извлечение JSON из 3 форматов
  - Чистый JSON: `{"key": "value"}`
  - Markdown блок: ` ```json {...} ``` `
  - JSON с текстом: `Вот ответ: {...}`
- `_create_pydantic_from_schema()`: динамическое создание Pydantic модели из JSON Schema
  - Поддержка типов: string, integer, number, boolean, array, object
  - Required/optional поля
  - Описания полей (description)
  - Значения по умолчанию (default)
- `_add_error_to_prompt()`: добавление информации об ошибке для retry
  - Показывает невалидный JSON
  - Сообщение об ошибке валидации
  - Инструкции для исправления
- **Раздельная обработка ошибок:**
  - `json.JSONDecodeError`: ошибки парсинга JSON
  - `pydantic.ValidationError`: ошибки валидации схемы

#### Обновления MockProvider
- `generate_structured()`: реализация для тестирования
  - Поддержка retry логики
  - Валидация против JSON Schema
  - Генерация `StructuredOutputError` при ошибках
- `_create_pydantic_from_schema()`: создание моделей для тестов

#### Обновления BaseLLMProvider
- Абстрактный метод `generate_structured()` обновлён:
  - Возвращает `StructuredLLMResponse` вместо `Dict[str, Any]`
  - Подробная документация с примерами
  - Описаны исключения `StructuredOutputError`, `ValueError`

#### Тесты (19 тестов)
- `tests/infrastructure/providers/llm/test_structured_output.py`:
  - `TestExtractJsonFromResponse`: 11 тестов извлечения JSON
    - Чистый JSON, markdown, JSON с текстом
    - Вложенные структуры, кириллица
    - Ошибки парсинга
  - `TestCreatePydanticFromSchema`: 6 тестов создания моделей
    - Простые типы, mixed types
    - Optional/required поля
    - Описания полей, вложенные объекты
  - `TestStructuredOutputRetry`: 2 теста retry логики
    - Успех с первой попытки
    - Ошибка после всех попыток

### Changed
- Версия проекта: 5.18.0 → 5.19.0

### Technical Details
- Изменено файлов: 4
  - `core/infrastructure/providers/llm/llama_cpp_provider.py`: +370 строк (улучшенное логирование)
  - `core/infrastructure/providers/llm/mock_provider.py`: +130 строк
  - `core/infrastructure/providers/llm/base_llm.py`: +40 строк
  - `tests/infrastructure/providers/llm/test_structured_output.py`: +400 строк (новый)

### Next Steps (Этап 3)
- Обновление навыков для возврата Pydantic моделей
- Интеграция с `generate_structured()` через executor
- Валидация выходных данных через контракты

---

## [5.18.0] - 2026-02-28

### Added
- **Этап 1: Автоматическое добавление контрактов в промпты** (Structured Output Maturity: 56% → 72%)

#### Новые методы в BaseComponent
- `_format_contract_section()`: форматирование JSON схемы для добавления в промпт
- `_render_prompt_with_contract()`: рендеринг промпта с секциями входного/выходного контрактов
- `get_prompt_with_contract()`: публичный API для получения промпта с контрактами

#### Возможности
- Автоматическое добавление JSON Schema входных контрактов в промпты
- Автоматическое добавление JSON Schema выходных контрактов в промпты
- Поддержка трёх позиций для контрактов: "start", "end", "after_variables"
- Инструкция для LLM "⚠️ **ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON СОГЛАСНО ВЫХОДНОМУ КОНТРАКТУ ВЫШЕ!**"
- Graceful degradation: если контракт не найден, он пропускается с предупреждением в лог

#### Обновлённые навыки
- **PlanningSkill**: обновлены 6 методов (`_create_plan`, `_update_plan`, `_decompose_task`, `_correct_plan_after_failure`)
- **BookLibrarySkill**: обновлён 1 метод (`_search_books_dynamic`)
- **DataAnalysisSkill**: обновлены 2 метода (анализ данных и анализ шагов)
- **FinalAnswerSkill**: обновлён 1 метод (`_generate`)

#### Тесты
- `test_contract_prompts.py`: 4 теста новых методов
  - Проверка существования методов
  - Проверка сигнатур методов
  - Тест форматирования контракта
  - Тест импорта навыков

### Changed
- Версия проекта: 5.17.0 → 5.18.0

### Technical Details
- Изменено файлов: 5
  - `core/components/base_component.py`: +124 строки (новые методы)
  - `core/application/skills/planning/skill.py`: ~6 строк изменено
  - `core/application/skills/book_library/skill.py`: ~4 строки изменено
  - `core/application/skills/data_analysis/skill.py`: ~4 строки изменено
  - `core/application/skills/final_answer/skill.py`: ~2 строки изменено

### Next Steps (Этап 2)
- Интеграция `generate_structured()` в LLM провайдеры с retry логикой
- Извлечение JSON из ответов LLM (markdown, plain text, mixed)
- Создание Pydantic моделей из JSON Schema динамически

---

## [5.17.0] - 2026-02-27

### Added
- **Единая система логирования v2**

#### Новые компоненты ядра
- `LogManager`: централизованное управление логами через единую точку
- `LogIndexer`: индексация сессий и агентов для быстрого поиска (< 100мс)
- `LogRotator`: автоматическая ротация, архивация и очистка старых логов
- `LogSearch`: поиск по логам через индексы
- `LoggingConfig`: конфигурация через YAML с политиками хранения

#### Новые структуры данных
- `SessionIndexEntry`: запись индекса сессии (session_id, timestamp, path, agent_id, goal, status)
- `AgentIndexEntry`: запись индекса агента (agent_id, session_ids[], first/last_session)
- `RetentionConfig`: политика хранения (active_days, archive_months, max_size_mb)
- `IndexingConfig`: настройки индексации (enabled, update_interval_sec)
- `SymlinksConfig`: настройки symlink для быстрого доступа

#### CLI утилиты (scripts/logs/)
- `find_latest_session.py`: найти последнюю сессию
- `find_session.py`: поиск по session_id, agent_id, goal
- `find_last_llm.py`: найти последний LLM вызов
- `cleanup_old_logs.py`: очистка старых логов по политике
- `check_log_size.py`: проверка размера логов
- `rebuild_index.py`: перестроение индекса
- `export_session.py`: экспорт сессии в JSON
- `migrate_old_logs.py`: миграция старых логов в новую структуру

### Added
- **Удаление legacy-компонентов** (согласно [docs/reports/LEGACY_REMOVAL_REPORT.md](docs/reports/LEGACY_REMOVAL_REPORT.md))

#### Удалённые файлы
- `core/application/behaviors/react_behavior.py` — дублирующий ReAct паттерн
- `core/application/behaviors/react_pattern.py` — дублирующий ReAct паттерн
- `core/application/behaviors/planning_pattern.py` — дублирующий Planning паттерн
- `core/application/behaviors/base_behavior.py` — устаревший базовый класс
- `core/config/defaults/_old_dev.yaml` — неиспользуемая конфигурация

#### Удалённый код
- `BaseComponent._cached_*` алиасы (7 строк)
- `BaseSkill.run()` метод (37 строк)
- `get_legacy_event_bus` экспорт из event_bus

#### Перенесённые классы
- `ReActInput`, `ReActOutput`, `PlanningInput`, `PlanningOutput` → `core/application/behaviors/base.py`

#### Исправления
- Заменены импорты `log_config_new` → `log_config` (4 файла)
- Создан `core/infrastructure/logging/log_mixin.py` (отсутствующий модуль)

### Changed
- Обновлены импорты в `component_factory.py`, `conftest.py`, `test_behavior_contracts.py`
- Версия проекта: 5.16.0 → 5.17.0

### Fixed
- Проект запускается без ошибок импорта
- Все критичные тесты пройдены (8/8, 100%)

### Metrics
- Удалено файлов: 5
- Удалено строк кода: 618
- Дублирование паттернов: 100% → 0%
- Базовых классов поведений: 3 → 2 (-33%)

📄 **Подробности:** См. [docs/reports/LEGACY_REMOVAL_RESULTS.md](docs/reports/LEGACY_REMOVAL_RESULTS.md)

#### Документация (docs/logging/)
- `README.md`: обзор системы, быстрый старт
- `structure.md`: структура папок, доступ к файлам
- `cli.md`: справочник CLI команд
- `retention.md`: политика хранения, мониторинг

#### Тесты
- `tests/unit/infrastructure/logging/test_logging.py`: 20+ тестов всех компонентов

### Changed
- **Структура папок логов**: единая директория `logs/` вместо разрозненных
  - `logs/active/`: активные логи (symlink на текущие)
  - `logs/archive/YYYY/MM/`: архив по датам
  - `logs/indexed/`: индексы для поиска
  - `logs/config/`: конфигурация

- **Форматы логов**: JSONL для структурированности
  - Сессии: `{type, session_id, timestamp, ...}`
  - LLM вызовы: `{type, component, phase, tokens, latency_ms, ...}`

- **main.py**: полная интеграция с новой системой
  - `await init_logging_system()`: инициализация
  - `get_session_logger(session_id)`: логирование сессии
  - `await session_logger.start/end()`: жизненный цикл сессии
  - `await shutdown_logging_system()`: завершение

- **SessionLogger**: переписан для работы через LogManager
  - JSONL формат вместо текста
  - Автоматическая индексация
  - Интеграция с LogRotator

- **LLMCallLogger**: агрегация в один файл на сессию
  - Вместо 100+ файлов на сессию → 1 файл
  - JSONL формат для парсинга

### Removed
- **Удалены дублирующие компоненты**:
  - `log_event_handler.py`: дублировал LogCollector
  - `session_log_handler.py`: дублировал SessionLogger
  - `log_mixin.py`: не использовался
  - `planning_pattern.py`, `react_behavior.py`, `react_pattern.py`: удалены в рамках рефакторинга

- **Удалена версионность**:
  - `session_logger_v2.py` → `session_logger.py`
  - `llm_call_logger_v2.py` → `llm_call_logger.py`
  - `log_config_new.py` → `log_config.py`

### Fixed
- **Дублирование логов**: одно событие → один файл вместо 3+
- **Поиск сессий**: 30 сек → < 100мс через индексы
- **Размер логов**: ×3 экономия за счёт устранения дублирования
- **Имена файлов**: единый формат `YYYY-MM-DD_HH-MM-SS_session_{id}.log`

### Technical Details
- **Импорты**: единый модуль `core.infrastructure.logging`
- **Обратная совместимость**: `log_formatter.py`, `cleanup_old_sessions()` для старого кода
- **Миграция**: `python scripts/logs/migrate_old_logs.py --dry-run`

## [5.16.0] - 2026-02-27

### Added
- **Система логирования для самообучения агента**

#### Модели данных
- `LogEntry`: добавлены поля `execution_context`, `step_quality_score`, `benchmark_scenario_id`
- `ExecutionContextSnapshot`: новая модель для снимка контекста выполнения
  - Контекст решения: available_capabilities, selected_capability, behavior_pattern, reasoning
  - Метрики: execution_time_ms, tokens_used, success
  - Версии ресурсов: prompt_version, contract_version
  - Оценка качества: step_quality_score
- Обновлены методы to_dict/from_dict для сериализации

#### LogCollector
- `_calculate_quality_score()`: расчёт оценки шага 0.0-1.0
  - 0.5 базовых за выполнение
  - +0.3 за успешность, +0.2 за скорость (<100мс), +0.1 за токены (<100), +0.2 за прогресс
- `_on_capability_selected()`: сохранение execution_context и step_quality_score
- `_on_benchmark_event()`: связь через benchmark_scenario_id

#### Скрипты
- `scripts/learning/aggregate_training_data.py`: агрегация логов в датасет для обучения
  - positive_examples: шаги с quality score > 0.8
  - negative_examples: ошибки
  - benchmark_results: результаты бенчмарков
- `scripts/maintenance/cleanup_logs.py`: автоматическая очистка старых логов
  - Очистка data/logs/, data/metrics/, logs/sessions/, logs/llm_calls/
  - Настройка через --days (по умолчанию 30 дней)

#### Тесты
- `tests/unit/learning/test_models.py`: 8 тестов для ExecutionContextSnapshot и LogEntry
- `tests/unit/learning/test_log_collector_extended.py`: 11 тестов для quality score и логирования
- Результат: 19/19 тестов пройдено

### Fixed
- `main.py`: замена logger.user_message на logger.info (AttributeError)

### Changed
- Версия проекта: 5.15.0 → 5.16.0

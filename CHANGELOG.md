# CHANGELOG

## [5.7.0] - 2026-02-26

### Refactored
- **Система кэширования компонентов** — переименование атрибутов
  - `BaseComponent`: `_cached_prompts` → `prompts`
  - `BaseComponent`: `_cached_input_contracts` → `input_contracts`
  - `BaseComponent`: `_cached_output_contracts` → `output_contracts`
  - `PromptService`: `_cached_prompts` → `prompts`
  - `ContractService`: `_cached_contracts` → `contracts`
  - `DataRepository`: `_prompt_content_cache` → `prompt_cache`
  - `DataRepository`: `_contract_schema_cache` → `contract_schema_cache`
  - `ApplicationContext`: `_prompt_cache` → `prompt_cache`
  - `ApplicationContext`: `_input_contract_schema_cache` → `input_contract_cache`
  - `ApplicationContext`: `_output_contract_schema_cache` → `output_contract_cache`

- **Паттерны поведения** — исправление архитектурных нарушений
  - `ReActPattern`: удалён `_ensure_prompt_and_contract_loaded()`, добавлен `_load_reasoning_resources()`
  - `ReActPattern`: загрузка ресурсов только из кэша `BaseComponent`
  - `EvaluationPattern`: `session_context.get_llm_provider()` → `infrastructure_context.get_provider()`
  - `EvaluationPattern`: промпты/контракты из `self.prompts` / `self.output_contracts`
  - `FallbackPattern`: версии паттернов из `component_config.parameters` (не хардкод)

- **AgentRuntime** — удалён мёртвый код
  - Удалён метод `_decide_next_action()` — ответственность делегирована `Behavior Pattern`

### Fixed
- **test_log_collector.py** — обновлено количество subscriptions (9 → 11)
- **test_e2e_architecture.py** — обновлены имена атрибутов кэша

### Technical Details
- Сохранена обратная совместимость через алиасы в `BaseComponent`
- Все 696 тестов проходят успешно (10 skipped — интеграционные)
- Удалён unused файл `core/application/agent/strategies/react/prompts.py`

## [5.6.0] - 2026-02-26

### Added
- **Логирование LLM промптов и ответов в файлы**
  - Новые типы логов: `LogType.LLM_PROMPT` и `LogType.LLM_RESPONSE`
  - `LogCollector`: подписка на `LLM_PROMPT_GENERATED` и `LLM_RESPONSE_RECEIVED`
  - Сохранение в файлы: `data/logs/by_agent/`, `by_capability/`, `all/`
  - Полные промпты и ответы сохраняются в JSON формате

- **Контракты и промпты для book_library**
  - `book_library.search_books_input/output_v1.0.0.yaml` — динамический поиск книг
  - `book_library.execute_script_input/output_v1.0.0.yaml` — выполнение скриптов
  - `book_library.list_scripts_input/output_v1.0.0.yaml` — список скриптов
  - `book_library.search_books_v1.0.0.yaml` — промпт генерации SQL через LLM
  - `book_library.execute_script_v1.1.0.yaml` — промпт выполнения скриптов

### Fixed
- **main.py** — исправлено обращение к `event_bus`
  - Было: `application_context.event_bus`
  - Стало: `application_context.infrastructure_context.event_bus`
  - Исправлена ошибка `AttributeError: 'ApplicationContext' object has no attribute 'event_bus'`

### Changed
- **ReActPattern** — улучшено логирование схем capability
  - Предупреждение о пустой схеме заменено на debug сообщение
  - Нормальное поведение для capability без входных параметров

### Technical Details
- Включено полное логирование LLM в терминал (`log_full_content=True`)
- Структура логов: JSON с корреляцией по agent_id, session_id, capability

### Fixed
- **ReActPattern** — исправлено получение LLM провайдера и обработка ответов
  - Метод `_perform_structured_reasoning` теперь корректно получает `default_llm` через `ApplicationContext.get_provider()`
  - Создается `LLMRequest` с `StructuredOutputConfig` для структурированного вывода
  - Обработка ответа от `LlamaCppProvider` (dict с `raw_response`)
  - Добавлена передача `available_capabilities` в результат рассуждения

- **AgentFactory** — устранена архитектурная ошибка с созданием второго ApplicationContext
  - Удалено дублирующее создание `ApplicationContext` в `create_agent()`
  - Теперь используется существующий `application_context` из фабрики
  - Исправлен `__init__` для приёма `ApplicationContext` вместо `InfrastructureContext`

- **validate_reasoning_result** — улучшен парсинг JSON от LLM
  - Поддержка markdown-разметки (```json ... ```)
  - Поиск сбалансированных фигурных скобок для извлечения JSON
  - Нормализация формата (строки → dict для `recommended_action` и `analysis`)
  - Обработка упрощённого формата ответа от LLM

- **FallbackPattern** — добавлен параметр `application_context` в конструктор

- **data_dir доступ** — исправлена ошибка отсутствия атрибута в `AppConfig`
  - В `application_context.py` использован `getattr` с fallback
  - В `file_tool.py` использован `getattr` с fallback

### Changed
- Обновлена версия с 5.4.0 на 5.5.0

### Technical Details
- ReActPattern теперь корректно работает с новой архитектурой LLM провайдеров
- AgentFactory использует единый ApplicationContext (устранено дублирование)
- Улучшена совместимость с ответами LLM (разные форматы JSON)

---

## [5.4.0] - 2026-02-19

### Added
- **Vector Search** — система семантического поиска по документам
  - `VectorBooksTool` — универсальный инструмент (поиск + текст + анализ)
  - `DocumentIndexingService` — сервис индексации документов
  - `AnalysisCache` — кэш результатов LLM анализа
  - `TextChunkingStrategy` — разбиение текста на чанки
  - `FAISSProvider` — векторный поиск (FAISS)
  - `EmbeddingProvider` — генерация эмбеддингов (SentenceTransformers)
  
- **Модели данных:**
  - `VectorSearchResult`, `VectorQuery`, `VectorDocument`
  - `VectorChunk`, `VectorIndexInfo`, `VectorSearchStats`
  - `AnalysisResult`, `BookWithCharacter`
  
- **Конфигурация:**
  - `VectorSearchConfig` — общая конфигурация
  - `FAISSConfig`, `EmbeddingConfig`, `ChunkingConfig`
  - `VectorStorageConfig`, `AnalysisCacheConfig`
  
- **Тесты:**
  - Unit тесты (71 тест)
  - Integration тесты (3 теста)
  - E2E тесты (3 теста)
  - Performance бенчмарки (12 тестов)
  
- **Документация:**
  - `docs/api/vector_search_api.md` — API документация
  - `docs/guides/vector_search.md` — руководство пользователя
  - `docs/vector_search/README.md` — навигация
  - `examples/vector_search_examples.py` — примеры использования

### Changed
- Обновлена `SystemConfig` для поддержки `vector_search`
- Обновлен `registry.yaml` с конфигурацией vector search

### Technical Details
- Архитектура: раздельные индексы FAISS на каждый источник
- Chunking: 500 символов, перекрытие 50 символов
- Embedding: SentenceTransformers (all-MiniLM-L6-v2, 384 dim)
- Кэширование: TTL 7 дней, инвалидация по префиксу
- Производительность: поиск < 1 сек (p95)

---

## [5.3.0] - 2026-02-19

### Changed
- **Рефакторинг scripts/:** создана чистая структура
  - `cli/` — CLI утилиты (promptctl, run_benchmark, run_optimization)
  - `maintenance/` — скрипты обслуживания (generate_docs, validate_docs, manage_migrations)
  - `validation/` — скрипты валидации (validate_registry, validate_manifests)
- Добавлен scripts/README.md с документацией

### Removed
- Удалены 22 одноразовых скрипта миграции (organize_data_*, move_files_*, create_*, fix_registry_*, update_registry_*)
- Удалены 9 отладочных тестов (debug_*, test_*, verify_*)
- Удалены подпапки: tests/, data/, architecture_audit/, utils/, versioning/

---

## [5.2.0] - 2026-02-19

### Changed
- Обновлена документация: исправлены ссылки и устаревшая статистика
- Удалены временные файлы разработки
- BENCHMARK_LEARNING_PLAN.md перемещён в docs/plans/

### Added
- requirements.txt — зависимости проекта
- requirements-dev.txt — зависимости для разработки
- LICENSE — лицензия MIT
- .env.example — пример конфигурации окружения

### Removed
- dev.yaml.improved, config_test_result.txt, tests/system_context_test.txt
- capability_inventory.txt (устарел)
- minimal_registry.yaml, very_minimal_registry.yaml (тестовые)
- check_contracts.py (дублируется в scripts/)

---

## [5.1.0] - 2026-02-15

### Added
- Новый интерфейс `BehaviorPatternInterface` для версионируемых паттернов поведения
- Реализация паттернов: `ReActPattern`, `PlanningPattern`, `EvaluationPattern`, `FallbackPattern`
- `BehaviorManager` для управления паттернами поведения
- Система версионирования паттернов как у промптов
- Хранилище паттернов в `data/behaviors/`
- Контрактная валидация входных данных
- Механизм горячей перезагрузки паттернов
- Миграционный гайд с `AgentStrategyInterface` на `BehaviorPatternInterface`

### Changed
- `AgentRuntime` теперь использует `BehaviorManager` вместо `StrategyManager`
- Все стратегии рефакторены в паттерны поведения
- Устранены циклические зависимости между паттернами
- Убран прямой доступ к `runtime.system` в паттернах
- Повышена изоляция между экземплярами паттернов

### Removed
- Полностью удалена устаревшая система стратегий на основе `AgentStrategyInterface`
- Удалены все старые стратегии: ReAct, Planning, Evaluation, Fallback в `core.agent_runtime.strategies`
- Удален легаси-код и адаптеры обратной совместимости
- Удален устаревший `StrategyManager` и связанные компоненты
- Удален устаревший `StrategyService` и компоненты хранилища стратегий

### Fixed
- Циклические зависимости между стратегиями
- Проблемы с изоляцией состояния между агентами
- Проблемы с версионированием логики поведения

---

## [2.2.0] - 2026-02-15

### Новые возможности

- **Конфигурация**: Разделение ответственности между AppConfig (глобальная конфигурация) и ComponentConfig (локальная конфигурация компонента)
- **Изоляция**: Улучшена изоляция между агентами за счет использования ComponentConfig для каждого компонента
- **Документация**: Добавлены пояснения о различии между AppConfig и ComponentConfig

### Улучшения

- **Архитектура**: Исправлена путаница между AppConfig и ComponentConfig в компонентах
- **Конструкторы**: Обновлены конструкторы BaseSkill и BaseComponent для корректной обработки ComponentConfig
- **Инициализация**: Улучшена логика создания компонентов в ApplicationContext

Автор: @system

---

## [2.1.0] - 2026-02-12

### Новые возможности

- **Агент**: Добавлен файл run_agent.py для простого запуска агента с тестовым вопросом
- **Конфигурация**: Автоматическая регистрация провайдеров из конфигурации при инициализации
- **Тестирование**: Улучшена функциональность для тестирования работоспособности агента

### Улучшения

- **Инициализация**: Провайдеры теперь автоматически регистрируются из конфигурации
- **Документация**: Добавлены комментарии и улучшена читаемость кода
- **Стабильность**: Исправлены потенциальные ошибки при отсутствии провайдеров

Автор: @system

---

## [2.0.0] - 2026-02-11

### BREAKING CHANGES

- **Архитектура**: Полностью переработана архитектура системы по принципу "декларация ≠ данные ≠ реализация"
- **Компоненты**: Все компоненты (навыки, сервисы, инструменты) теперь используют ComponentConfig вместо AgentConfig
- **Инициализация**: Введена предзагрузка всех ресурсов (промптов, контрактов) при инициализации компонентов
- **Кэширование**: Реализованы изолированные кэши для каждого компонента с гарантией 0 обращений к хранилищу во время выполнения
- **BaseComponent**: Создан единый базовый класс для всех компонентов с поддержкой кэширования и предзагрузки

### Новые возможности

- **Компонентная архитектура**: Введена система ComponentConfig для управления версиями промптов и контрактов
- **Варианты компонентов**: Добавлена поддержка A/B тестирования и канареечных релизов через create_component_variant
- **Проверки архитектуры**: Внедрены гарантии, что все компоненты используют новую архитектуру
- **Изоляция ресурсов**: Каждый компонент имеет изолированные кэши промптов и контрактов

### Улучшения

- **Производительность**: Устранены обращения к хранилищу во время выполнения за счет предзагрузки
- **Масштабируемость**: Поддержка версионирования и вариантов компонентов
- **Тестируемость**: Изолированные кэши упрощают тестирование компонентов
- **Поддержка**: Четкое разделение ответственностей упрощает обслуживание

### Затронутые компоненты

- **Навыки**: PlanningSkill, BookLibrarySkill, FinalAnswerSkill обновлены для новой архитектуры
- **Сервисы**: PromptService, ContractService, SQLGenerationService, SQLQueryService, SQLValidatorService
- **Инструменты**: SQLTool и другие инструменты обновлены для соответствия новой архитектуре

Автор: @system

---

## [1.1.0] - 2026-02-11

### Изменения

- **Ядро**: Тестовое обновление системы версионирования

Автор: @test_agent

---

## [1.0.3] - 2026-02-11

### Изменения

- **Ядро**: Тестовое сообщение коммита

Автор: @test_user

---

## [1.0.2] - 2026-02-11

### Изменения

- **Ядро**: Тестовое сообщение коммита

Автор: @test_user

---

## [1.0.1] - 2026-02-11

### Изменения

- **Ядро**: Тестовое сообщение коммита

Автор: @test_user

---

## [1.0.0] - 2026-02-11

### Изменения

- **Ядро**: Установка начальной версии проекта
- **Промпты**: Установка начальных версий промптов
- **Контракты**: Установка начальных версий контрактов

Автор: @system

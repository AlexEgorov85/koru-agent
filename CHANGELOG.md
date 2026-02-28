# CHANGELOG

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
- **Удаление legacy-компонентов** (согласно LEGACY_REMOVAL_REPORT.md)

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

📄 **Подробности:** См. [LEGACY_REMOVAL_RESULTS.md](LEGACY_REMOVAL_RESULTS.md)

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

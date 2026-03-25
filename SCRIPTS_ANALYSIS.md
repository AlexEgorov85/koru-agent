# 📋 АНАЛИЗ ПАПКИ SCRIPTS

---

## 📊 ИТОГО

| Папка | Файлов | Активных | Устаревших |
|-------|--------|----------|------------|
| `scripts/` | 5 | 0 | 4 |
| `scripts/cli/` | 14 | 7 | 7 |
| `scripts/audit/` | 5 | 3 | 2 |
| `scripts/vector/` | 3 | 0 | 3 |
| `scripts/performance/` | 2 | 2 | 0 |
| `scripts/monitoring/` | 1 | 1 | 0 |
| `scripts/learning/` | 1 | 1 | 0 |
| `scripts/debug/` | 1 | 0 | 1 |
| `scripts/maintenance/` | 9 | 8 | 1 |
| `scripts/validation/` | 5 | 4 | 1 |
| **ВСЕГО** | **46** | **26** | **20** |

---

## ✅ АКТИВНЫЕ СКРИПТЫ (используются)

### scripts/cli/ (7)

| Скрипт | Назначение |
|--------|------------|
| `run_benchmark.py` | CLI для запуска бенчмарков |
| `run_real_agent_benchmark.py` | Запуск реального агента на бенчмарке |
| `generate_agent_benchmark.py` | Генерация бенчмарка из БД |
| `compare_benchmarks.py` | Сравнение результатов бенчмарков |
| `run_optimization.py` | CLI для оптимизации промптов |
| `benchmark_validator.py` | Валидация результатов бенчмарка |
| `promptctl.py` | Управление жизненным циклом промптов |

### scripts/audit/ (3)

| Скрипт | Назначение |
|--------|------------|
| `full_audit.py` | Основной скрипт аудита (запускает others) |
| `code_auditor.py` | Анализ классов/функций |
| `usage_tracker.py` | Трекинг использования кода |

### scripts/performance/ (2)

| Скрипт | Назначение |
|--------|------------|
| `event_bus_benchmark.py` | Бенчмарк EventBus |
| `profile_startup.py` | Профилирование времени запуска |

### scripts/monitoring/ (1)

| Скрипт | Назначение |
|--------|------------|
| `export_metrics.py` | Экспорт метрик в Prometheus |

### scripts/learning/ (1)

| Скрипт | Назначение |
|--------|------------|
| `aggregate_training_data.py` | Агрегация логов в данные для обучения |

### scripts/maintenance/ (8)

| Скрипт | Назначение |
|--------|------------|
| `generate_docs.py` | Генерация документации |
| `cleanup_logs.py` | Очистка старых логов |
| `remove_bom.py` | Удаление UTF-8 BOM |
| `check_links.py` | Проверка ссылок в документации |
| `validate_docs.py` | Валидация документации |
| `manage_migrations.py` | Управление миграциями |
| `fix_encoding.py` | Исправление编码问题 |
| `check_consistency.py` | Проверка консистентности registry |
| `analyze_commit.py` | Анализ коммитов для версионирования |

### scripts/validation/ (4)

| Скрипт | Назначение |
|--------|------------|
| `analyze_library_schema.py` | Анализ схемы БД |
| `check_skill_architecture.py` | Проверка архитектуры скиллов |
| `check_yaml_syntax.py` | Валидация YAML |
| `validate_registry.py` | Валидация registry.yaml |

---

## ❌ УСТАРЕВШИЕ СКРИПТЫ (можно удалить)

### scripts/ (4)

| Скрипт | Причина |
|--------|---------|
| `replace_logging.py` | Одноразовая миграция на EventBusLogger |
| `create_system_prompts.py` | Одноразовая миграция system prompts |
| `update_registry.py` | Одноразовая миграция registry |
| `rename_prompts.py` | Одноразовая миграция именования |

### scripts/cli/ (7)

| Скрипт | Причина |
|--------|---------|
| `run_agent_benchmark.py` | Использует mock, ограничен |
| `auto_optimize.py` | Использует mock, неполный |
| `analyze_and_optimize.py` | Dev-скрипт с mock |
| `run_optimization_real.py` | Тестовый скрипт |
| `test_optimization_real_data.py` | Тестовый скрипт |
| `generate_benchmark_from_db.py` | Похож на generate_agent_benchmark.py |

### scripts/audit/ (2)

| Скрипт | Причина |
|--------|---------|
| `comprehensive_audit.py` | Старая версия full_audit |
| `final_audit.py` | Старая версия |

### scripts/vector/ (3)

| Скрипт | Причина |
|--------|---------|
| `index_authors.py` | Одноразовая индексация |
| `index_books.py` | Одноразовая индексация |
| `initial_indexing.py` | Одноразовая индексация |

### scripts/debug/ (1)

| Скрипт | Причина |
|--------|---------|
| `reproduce_loops.py` | Дебаг-скрипт, вероятно уже не нужен |

### scripts/maintenance/ (1)

| Скрипт | Причина |
|--------|---------|
| `migrate_logs.py` | Одноразовая миграция |

### scripts/validation/ (1)

| Скрипт | Причина |
|--------|---------|
| `fix_behavior_prompts.py` | Одноразовый фикс |

---

## 🤔 НЕЯСНО

| Скрипт | Причина |
|--------|---------|
| `scripts/__init__.py` | Битые импорты - ссылается на несуществующие функции |

---

## 🗑️ РЕКОМЕНДАЦИЯ К УДАЛЕНИЮ

**20 скриптов** можно удалить как утратившие актуальность:

```
scripts/
├── replace_logging.py
├── create_system_prompts.py
├── update_registry.py
├── rename_prompts.py
└── __init__.py (переписать)

scripts/cli/
├── run_agent_benchmark.py
├── auto_optimize.py
├── analyze_and_optimize.py
├── run_optimization_real.py
├── test_optimization_real_data.py
└── generate_benchmark_from_db.py

scripts/audit/
├── comprehensive_audit.py
└── final_audit.py

scripts/vector/ (все 3)
├── index_authors.py
├── index_books.py
└── initial_indexing.py

scripts/debug/
└── reproduce_loops.py

scripts/maintenance/
└── migrate_logs.py

scripts/validation/
└── fix_behavior_prompts.py
```

**После удаления:** 26 активных скриптов

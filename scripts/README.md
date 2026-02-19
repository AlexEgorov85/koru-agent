# Скрипты koru-agent

## Структура

```
scripts/
├── cli/              # CLI утилиты для запуска
├── maintenance/      # Скрипты обслуживания системы
└── validation/       # Скрипты валидации и проверки
```

---

## CLI утилиты (`cli/`)

| Скрипт | Назначение | Пример использования |
|--------|------------|---------------------|
| `promptctl.py` | Управление промптами | `python scripts/cli/promptctl.py --help` |
| `run_benchmark.py` | Запуск бенчмарков | `python scripts/cli/run_benchmark.py -c planning.create_plan -v v1.0.0` |
| `run_optimization.py` | Оптимизация промптов | `python scripts/cli/run_optimization.py -c planning.create_plan -m accuracy` |

---

## Обслуживание (`maintenance/`)

| Скрипт | Назначение |
|--------|------------|
| `generate_docs.py` | Генерация документации проекта |
| `validate_docs.py` | Валидация документации |
| `manage_migrations.py` | Управление миграциями БД |
| `check_consistency.py` | Проверка консистентности данных |
| `analyze_commit.py` | Анализ коммитов для changelog |
| `apply_version.py` | Применение версии к компонентам |
| `validate_consistency.py` | Проверка консистентности версий |

---

## Валидация (`validation/`)

| Скрипт | Назначение |
|--------|------------|
| `validate_all_manifests.py` | Валидация всех манифестов компонентов |
| `validate_manifests.py` | Валидация отдельных манифестов |
| `validate_registry.py` | Валидация registry.yaml |
| `check_registry.py` | Проверка конфигурации registry |
| `check_yaml_syntax.py` | Проверка синтаксиса YAML файлов |
| `analyze_library_schema.py` | Анализ схемы библиотеки |
| `fix_behavior_prompts.py` | Исправление промптов поведения |

---

## Использование

### Запуск CLI утилит

```bash
# Бенчмарк
python scripts/cli/run_benchmark.py --capability planning.create_plan --version v1.0.0

# Оптимизация
python scripts/cli/run_optimization.py --capability planning.create_plan --metric accuracy --target 0.95

# Управление промптами
python scripts/cli/promptctl.py list
python scripts/cli/promptctl.py get planning.create_plan v1.0.0
```

### Запуск скриптов обслуживания

```bash
# Генерация документации
python scripts/maintenance/generate_docs.py

# Валидация документации
python scripts/maintenance/validate_docs.py

# Проверка консистентности
python scripts/maintenance/check_consistency.py
```

### Запуск скриптов валидации

```bash
# Валидация всех манифестов
python scripts/validation/validate_all_manifests.py

# Проверка registry
python scripts/validation/validate_registry.py

# Проверка YAML синтаксиса
python scripts/validation/check_yaml_syntax.py
```

---

## Добавление нового скрипта

1. Определите категорию скрипта (cli/maintenance/validation)
2. Создайте файл в соответствующей папке
3. Добавьте документацию в эту таблицу
4. Убедитесь, что скрипт имеет `--help` для CLI утилит

### Требования к скриптам

- **CLI утилиты**: использовать `argparse` с `--help`
- **Обслуживание**: логирование через `logging` модуль
- **Валидация**: вывод результатов в формате pass/fail

---

## Удалённые скрипты

Следующие одноразовые скрипты были удалены:
- Скрипты миграции данных (organize_data_*, move_files_*, create_*)
- Скрипты исправления registry (fix_registry_*, update_registry_*)
- Отладочные тесты (debug_*, test_*, verify_*)

Эти скрипты выполняли одноразовые задачи и больше не нужны.

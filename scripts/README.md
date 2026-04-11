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

Все CLI-команды доступны через единый интерфейс `koru`:

```bash
python -m scripts.cli.koru --help
```

| Команда | Назначение | Пример |
|---------|------------|--------|
| `koru bench run` | Запуск реального агента на бенчмарке | `koru bench run --level sql --limit 5` |
| `koru bench generate` | Генерация бенчмарка из БД | `koru bench generate` |
| `koru bench compare` | Сравнение результатов | `koru bench compare r1.json r2.json` |
| `koru bench history` | История запусков | `koru bench history` |
| `koru bench optimize` | Оптимизация через orchestrator | `koru bench optimize --size 2 --mode accuracy` |
| `koru prompt create` | Создать промпт-черновик | `koru prompt create --capability X --version v1.0.0` |
| `koru prompt promote` | Продвинуть в активные | `koru prompt promote --capability X --version v1.0.0` |
| `koru prompt archive` | Архивировать | `koru prompt archive --capability X --version v1.0.0` |
| `koru prompt status` | Статус всех промптов | `koru prompt status` |

Общие утилиты вынесены в `scripts/cli/_utils.py` для переиспользования.

---

## Векторная индексация (`vector/`)

Все операции индексации — через единый скрипт `indexer.py`:

```bash
# Создать пустые индексы для всех источников
python -m scripts.vector.indexer init

# Индексация авторов
python -m scripts.vector.indexer authors

# Индексация книг (по заголовкам)
python -m scripts.vector.indexer books

# Полная индексация книг (с чанками содержимого)
python -m scripts.vector.indexer books --full

# Произвольная таблица
python -m scripts.vector.indexer table --table "Lib.genres" --column "name" --source genres
```

**Удалённые скрипты** (функциональность перенесена в `indexer.py`):
- `index_authors.py` → `indexer authors`
- `index_books.py` → `indexer books`
- `rebuild_books_index.py` → `indexer books --full`
- `initial_indexing.py` → `indexer init`

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

---

## Использование

### Запуск CLI утилит

```bash
# Бенчмарк — запуск
python -m scripts.cli.koru bench run --level sql
python -m scripts.cli.koru bench run -g "Какие книги написал Пушкин?"
python -m scripts.cli.koru bench run --limit 5

# Бенчмарк — генерация
python -m scripts.cli.koru bench generate

# Бенчмарк — сравнение и история
python -m scripts.cli.koru bench compare results1.json results2.json
python -m scripts.cli.koru bench history

# Оптимизация
python -m scripts.cli.koru bench optimize --size 2 --mode accuracy

# Управление промптами
python -m scripts.cli.koru prompt create --capability X --version v1.0.0
python -m scripts.cli.koru prompt promote --capability X --version v1.0.0
python -m scripts.cli.koru prompt status
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

Следующие скрипты были объединены в единый CLI `koru.py`:
- `run_benchmark.py` → `koru bench run`
- `run_real_agent_benchmark.py` → `koru bench run`
- `run_orchestrator_benchmark.py` → `koru bench optimize`
- `run_optimization.py` → `koru bench optimize`
- `run_auto_optimization.py` → `koru bench optimize`
- `compare_benchmarks.py` → `koru bench compare`
- `generate_agent_benchmark.py` → `koru bench generate`
- `generate_benchmark_from_db.py` → `koru bench generate`
- `promptctl.py` → `koru prompt create/promote/archive/status`

Также удалены одноразовые скрипты:
- `fix_encoding.py` — исправление mojibake (задача выполнена)
- `remove_bom.py` — удаление BOM из файлов (задача выполнена)
- `migrate_logs.py` — миграция старой структуры логов (задача выполнена)
- `fix_behavior_prompts.py` — исправление YAML промптов (задача выполнена)

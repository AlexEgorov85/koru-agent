# 📚 BOOK_LIBRARY: НАВЫК РАБОТЫ С БИБЛИОТЕКОЙ КНИГ

**Версия:** v1.2.1  
**Дата:** 2026-02-17  
**Статус:** ✅ Готов к использованию

---

## 🎯 ОБЗОР

Навык `book_library` предоставляет доступ к библиотеке книг через **3 capability**:

| Capability | Тип | Время | Описание |
|------------|-----|-------|----------|
| `book_library.execute_script` | Static | ~50-100мс | Выполнение заготовленного SQL-скрипта |
| `book_library.search_books` | Dynamic | ~1000-2000мс | Динамический поиск через LLM |
| `book_library.list_scripts` | Informational | ~50мс | Список доступных скриптов |

---

## 🚀 БЫСТРЫЙ СТАРТ

### Пример запуска:

```bash
cd c:\Users\Алексей\Documents\WORK\Agent_v5
python run_book_library_example.py
```

### Пример кода:

```python
from core.application.context.application_context import ApplicationContext

# Получение навыка
skill = app_context.get_skill("book_library")

# 1. Получить список скриптов
result = await skill.execute(
    capability="book_library.list_scripts",
    parameters={},
    execution_context=None
)

# 2. Выполнить скрипт
result = await skill.execute(
    capability="book_library.execute_script",
    parameters={
        "script_name": "get_books_by_author",
        "parameters": {"author": "Лев Толстой"}
    },
    execution_context=None
)

# 3. Динамический поиск
result = await skill.execute(
    capability="book_library.search_books",
    parameters={
        "query": "Найти книги Пушкина",
        "max_results": 10
    },
    execution_context=None
)
```

---

## 📋 ДОСТУПНЫЕ СКРИПТЫ

| # | Скрипт | Параметры | Пример |
|---|--------|-----------|--------|
| 1 | `get_all_books` | `max_rows` | `{"max_rows": 50}` |
| 2 | `get_books_by_author` | `author`, `max_rows` | `{"author": "Пушкин"}` |
| 3 | `get_books_by_genre` | `genre`, `max_rows` | `{"genre": "Роман"}` |
| 4 | `get_books_by_year_range` | `year_from`, `year_to`, `max_rows` | `{"year_from": 1800, "year_to": 1899}` |
| 5 | `get_book_by_id` | `book_id` | `{"book_id": 1}` |
| 6 | `count_books_by_author` | `author` | `{"author": "Толстой"}` |
| 7 | `get_books_by_title_pattern` | `title_pattern`, `max_rows` | `{"title_pattern": "%Война%"}` |
| 8 | `get_distinct_authors` | `max_rows` | `{"max_rows": 50}` |
| 9 | `get_distinct_genres` | `max_rows` | `{"max_rows": 20}` |
| 10 | `get_genre_statistics` | `max_rows` | `{"max_rows": 10}` |

---

## 🏗️ АРХИТЕКТУРА (YAML-Only)

```
data/contracts/tool/book_library/*.yaml  ← Схемы валидации
         ↓
ComponentConfig (кэширует Pydantic модели)
         ↓
skill.py (get_cached_*_schema_safe())
         ↓
Валидация через model_validate()
```

### Структура файлов:

```
project/
├── core/application/skills/book_library/
│   ├── skill.py                    # Навык
│   └── scripts_registry.py         # Реестр скриптов
│
├── data/
│   ├── contracts/tool/book_library/    # Контракты (6 файлов)
│   ├── prompts/tool/book_library/      # Промпты (2 файла)
│   └── manifests/skills/book_library/  # Манифест
│
├── tests/integration/test_book_library_skill.py  # Тесты
├── run_book_library_example.py                   # Примеры
└── BOOK_LIBRARY_README.md                        # Этот файл
```

---

## 🔧 ТРЕБОВАНИЯ

### 1. Конфигурация БД (dev.yaml)

```yaml
db_providers:
  default_db:
    provider_type: postgres
    enabled: true
    parameters:
      host: "localhost"
      port: 5432
      database: "postgres"
      username: "postgres"
      password: "1"
      sslmode: "disable"
```

### 2. Таблица в БД

```sql
CREATE TABLE IF NOT EXISTS "Lib".books (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    year INTEGER,
    isbn TEXT,
    genre TEXT
);
```

### 3. LLM провайдер (для dynamic режима)

```yaml
llm_providers:
  default_llm:
    provider_type: llama_cpp
    enabled: true
    parameters:
      model_path: "path/to/model.gguf"
      n_ctx: 2048
```

---

## 📖 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### 1. Через ApplicationContext (production)

```python
from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig

# Инициализация
config = ConfigLoader().load()
infra = InfrastructureContext(config)
await infra.initialize()

app_context = ApplicationContext(
    infrastructure_context=infra,
    config=AppConfig.from_registry(profile="prod"),
    profile="prod"
)
await app_context.initialize()

# Получение навыка
skill = app_context.get_skill("book_library")
await skill.initialize()

# Использование
result = await skill.execute(
    capability="book_library.execute_script",
    parameters={"script_name": "get_all_books", "parameters": {"max_rows": 10}},
    execution_context=None
)

await infra.shutdown()
```

### 2. Через ActionExecutor (агент)

```python
from core.application.agent.components.action_executor import ActionExecutor
from core.session_context.session_context import SessionContext

executor = ActionExecutor(application_context=app_context)
session_context = SessionContext()
session_context.set_goal("Найти книги")

result = await executor.execute_capability(
    capability_name="book_library.execute_script",
    parameters={
        "script_name": "get_books_by_author",
        "parameters": {"author": "Лев Толстой"}
    },
    session_context=session_context
)
```

### 3. Запуск примеров

```bash
python run_book_library_example.py
```

Содержит 4 примера:
1. `run_with_app_context()` — прямой вызов
2. `run_with_executor()` — через ActionExecutor
3. `run_all_scripts_demo()` — все 10 скриптов
4. `run_performance_comparison()` — benchmark static vs dynamic

---

## 🧪 ТЕСТИРОВАНИЕ

```bash
# Запуск тестов
python -m pytest tests/integration/test_book_library_skill.py -v

# С покрытием
python -m pytest tests/integration/test_book_library_skill.py --cov=core/application/skills/book_library

# Анализ схемы БД
python analyze_library_schema.py
```

---

## ⚡ ПРОИЗВОДИТЕЛЬНОСТЬ

| Режим | Время | LLM | Когда использовать |
|-------|-------|-----|-------------------|
| Static (`execute_script`) | ~50-100мс | ❌ | 90% запросов |
| Dynamic (`search_books`) | ~1000-2000мс | ✅ | Сложные запросы |

**Рекомендация:** Используйте `execute_script` когда есть подходящий готовый скрипт.

---

## 📊 МОНИТОРИНГ

Метрики публикуются через EventBus:

- `book_library.total_executions` — количество выполнений
- `book_library.static_script_executions` — static скрипты
- `book_library.dynamic_search_executions` — dynamic поиск
- `book_library.avg_execution_time_ms` — среднее время
- `book_library.error_rate` — процент ошибок

Алерты: `data/alerts/book_library_alerts.yaml`

---

## 🐛 ОТЛАДКА

### Ошибка: "DB провайдер не найден"

**Решение:** Проверьте подключение к БД в dev.yaml

### Ошибка: "Контракт не загружен"

**Решение:** Проверьте YAML контракты в `data/contracts/tool/book_library/`

### Ошибка: "Capability не найдена"

**Решение:** Проверьте registry.yaml, секция `capability_types`

---

## 📁 ФАЙЛЫ

| Файл | Описание |
|------|----------|
| `core/application/skills/book_library/skill.py` | Навык (YAML-Only) |
| `core/application/skills/book_library/scripts_registry.py` | Реестр 10 скриптов |
| `data/contracts/tool/book_library/*.yaml` | 6 контрактов |
| `data/prompts/tool/book_library/*.yaml` | 2 промпта |
| `tests/integration/test_book_library_skill.py` | 16 тестов |
| `run_book_library_example.py` | Примеры запуска |

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Запустить анализ БД:** `python analyze_library_schema.py`
2. **Проверить тесты:** `python -m pytest tests/integration/test_book_library_skill.py -v`
3. **Использовать в агенте:** Агент автоматически получит описания capability

---

**Готово к использованию! ✅**

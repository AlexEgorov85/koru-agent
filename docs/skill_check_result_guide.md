# Гайд по развитию навыка check_result

## Обзор

Навык `check_result` — проверка результатов SQL-запросами. Поддерживает два режима:
1. `execute_script` — выполнение заготовленных скриптов
2. `generate_script` — генерация SQL через LLM

---

## Архитектура

```
core/components/skills/check_result/
├── skill.py                      # Координация, инициализация
├── handlers/
│   ├── execute_script_handler.py # Статические скрипты
│   └── generate_script_handler.py # Генерация SQL через LLM
└── handlers/__init__.py

data/skills/check_result/
└── tables.yaml                    # Конфигурация таблиц БД

data/contracts/skill/check_result/
├── check_result.execute_script_input_v1.0.0.yaml
├── check_result.execute_script_output_v1.0.0.yaml
├── check_result.generate_script_input_v1.0.0.yaml
└── check_result.generate_script_output_v1.0.0.yaml
```

---

## Что нужно доработать

### 1. Добавить новые скрипты

**Файл:** `core/components/skills/check_result/handlers/execute_script_handler.py`

**Структура скрипта:**
```python
SCRIPTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "script_name": {
        "description": "Описание скрипта",
        "name": "script_name",
        "sql": 'SELECT * FROM "Lib".books WHERE ...',
        "required_parameters": ["param1"],  # Обязательные
        "optional_parameters": ["param2"],   # Опциональные
        "validation": {                     # Валидация (опционально)
            "param1": {
                "table": "table_name",
                "search_fields": ["field1"],
                "vector_source": "vector_name",
            }
        }
    },
}
```

**Пример добавления:**
```python
"get_books_after_year": {
    "description": "Получить книги после указанного года",
    "name": "get_books_after_year",
    "sql': 'SELECT * FROM "Lib".books WHERE publication_year >= %s ORDER BY publication_year LIMIT %s',
    "required_parameters": ["year"],
    "optional_parameters": [],
}
```

**Важно:**
- SQL использует позиционные параметры `%s`
- При валидации: `vector_source` должен соответствовать таблице в БД
- Все скрипты должны иметь `LIMIT`

---

### 2. Расширить схему таблиц

**Файл:** `data/skills/check_result/tables.yaml`

```yaml
tables:
  - schema: Lib
    table: books
    description: Таблица книг
  - schema: Lib
    table: authors
    description: Таблица авторов
  - schema: Lib
    table: genres        # Добавить новые таблицы
    description: Таблица жанров
```

**Важно:** При изменении tables.yaml перезапустите приложение. Skill автоматически не перечитывает конфигурацию.

---

### 3. Изменить контракты

**Input контракт** — входящие параметры:
```
data/contracts/skill/check_result/check_result.<capability>_input_v<version>.yaml
```

**Output контракт** — результат выполнения:
```
data/contracts/skill/check_result/check_result.<capability>_output_v<version>.yaml
```

**Пример добавления поля в input:**
```yaml
schema_data:
  properties:
    new_field:
      type: string
      description: Описание нового поля
  required:
    - new_field
```

---

### 4. Добавить новую capability

1. **Зарегистрировать handler в skill.py:**
```python
self._handlers = {
    "check_result.execute_script": ExecuteScriptHandler(self),
    "check_result.generate_script": GenerateScriptHandler(self),
    "check_result.new_capability": NewHandler(self),  # Добавить
}
```

2. **Добавить Capability в get_capabilities():**
```python
Capability(
    name="check_result.new_capability",
    description="Описание",
    skill_name=self.name,
    supported_strategies=["react"],
    visiable=True
)
```

3. **Создать YAML контракты:**
- `check_result.new_capability_input_v1.0.0.yaml`
- `check_result.new_capability_output_v1.0.0.yaml`

---

### 5. Настроить валидацию параметров

Валидация в `execute_script_handler` работает в 3 этапа:

1. **SQL-валидация** — проверка по справочным таблицам
2. **Vector-валидация** — семантический поиск
3. **Fuzzy-валидация** — нечёткое сопоставление

**Пример конфигурации:**
```python
"validation": {
    "author": {
        "table": "authors",           # Таблица для проверки
        "search_fields": ["first_name", "last_name"],  # Поля поиска
        "vector_source": "authors",   # Источник для векторного поиска
    }
}
```

**Требования:**
- Таблица должна существовать в БД
- Поля должны быть в таблице
- `vector_source` должен быть настроен в системе

---

## Частые ошибки

### Ошибка: "Скрипт не найден"

**Причина:** Скрипт не добавлен в `SCRIPTS_REGISTRY`

**Решение:** Добавить скрипт в словарь

### Ошибка: "Параметры невалидны"

**Причина:** Валидация не прошла для параметра

**Решение:** Проверить что значение существует в таблице БД или отключить валидацию

### Ошибка: "Генерация SQL не удалась"

**Причина:** LLM не смог сгенерировать валидный SQL

**Решение:** Проверить что промпт sql_generation загружен, проверить схему таблиц

### Ошибка: "Результатов не найдено"

**Причина:** SQL вернул пустой результат

**Возможные причины:**
1. Данных по запросу нет в БД
2. Ошибка в сгенерированном SQL
3. База данных пуста

---

## Тестирование

**Добавление тестового скрипта:**
```python
# В execute_script_handler.py временно добавить:
"test_script": {
    "description": "Тестовый скрипт",
    "name": "test_script", 
    "sql": 'SELECT 1 as result',
    "required_parameters": [],
    "optional_parameters": [],
}
```

**Вызов через ReAct:**
```json
{
  "capability": "check_result.execute_script",
  "parameters": {
    "script_name": "test_script",
    "parameters": {}
  }
}
```

---

## Метрики

Навык публикует события в EventBus:

```python
await self._publish_with_context(
    event_type="check_result.metrics",
    data={
        "capability_name": "check_result.execute_script",
        "success": True,
        "execution_time_ms": 150.0,
        "execution_type": "static",
        "rows_returned": 10,
        "script_name": "get_all_books"
    },
    source="check_result"
)
```

---

## Зависимости

Навык требует:
- `sql_tool` — выполнение SQL
- `sql_generation` — генерация SQL через LLM
- `sql_query_service` — сервис запросов
- `table_description_service` — описание таблиц

**Проверка доступности:**
```python
DEPENDENCIES = ["sql_tool", "sql_generation", "sql_query_service", "table_description_service"]
```

---

## Версионирование

- **Версия skill:** определяется в `component_config`
- **Версия контрактов:** в YAML файлах (`v1.0.0`)
- **Статус:** `active` / `draft` / `deprecated`

Для изменения версии:
1. Изменить версию в YAML файлах
2. Обновить `registry.yaml`
3. Перезапустить приложение

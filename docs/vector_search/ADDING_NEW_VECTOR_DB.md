# Как добавить новую векторную БД и связать с валидацией параметров

**Версия:** 1.0.0  
**Дата:** 2026-04-12  
**Статус:** ✅ Утверждено

---

## 📋 Обзор

Документ описывает **полный пошаговый процесс** добавления нового FAISS-индекса (векторной БД) и его интеграции с 3-ступенчатой валидацией параметров в навыках.

### Когда это нужно

- Вы добавили новую таблицу в PostgreSQL и хотите, чтобы агент мог находить в ней значения через семантический поиск
- Вы хотите, чтобы параметры скриптов в `check_result` валидировались через vector search
- Вы создаёте новый навык, которому нужна валидация параметров по справочникам

### Архитектура за 1 минуту

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent_v5                                     │
│                                                                      │
│  1. PostgreSQL (реляционные данные)                                  │
│     └─ таблица: audits, violations, ...                              │
│                                                                      │
│  2. FAISS индекс (векторный поиск)                                   │
│     └─ файл: audits_index.faiss, violations_index.faiss              │
│                                                                      │
│  3. ParamValidator (3 ступени)                                       │
│     ├─ SQL ILIKE → поиск в таблице                                  │
│     ├─ Vector Search → FAISS индекс                                 │
│     └─ Fuzzy Matching → нечёткое сравнение                          │
│                                                                      │
│  4. SCRIPTS_REGISTRY (заготовленные скрипты)                         │
│     └─ validation config → связывает параметр с таблицой и FAISS     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Шаг 1: Регистрация индекса в конфигурации

### Файл: `core/config/vector_config.py`

В `VectorSearchConfig.indexes` добавьте новую запись:

```python
indexes: Dict[str, str] = {
    "books": "books_index.faiss",
    "authors": "authors_index.faiss",
    "audits": "audits_index.faiss",        # ← Ваше новое
    "violations": "violations_index.faiss", # ← Ваше новое
    "my_new_table": "my_new_table_index.faiss",  # ← Пример
}
```

**Правила именования:**

| Элемент | Правило | Пример |
|---------|---------|--------|
| Ключ в `indexes` | lowercase, без пробелов | `"audits"`, `"employees"` |
| Имя файла | `{source}_index.faiss` | `"audits_index.faiss"` |
| `vector_source` в скрипте | Должен совпадать с ключом | `"audits"` |

### Обновите валидатор (там же)

```python
@field_validator('indexes')
@classmethod
def validate_indexes(cls, v):
    """Валидация индексов."""
    required = {"books", "authors", "audits", "violations", "my_new_table"}  # ← Добавьте своё
    if set(v.keys()) != required:
        raise ValueError(f"Indexes must include: {required}")
    return v
```

---

## 🗄️ Шаг 2: Создание функции индексации

### Файл: `scripts/vector/indexer.py`

Добавьте функцию `index_<source>()` по шаблону:

```python
async def index_my_new_table(embedding, faiss_provider, vs_config) -> int:
    """Индексация <описание таблицы> — по <каким полям>."""
    print("=" * 60)
    print("ИНДЕКСАЦИЯ <НАЗВАНИЕ>")
    print("=" * 60)

    from core.config import get_config
    import psycopg2

    config = get_config(profile="dev")
    db_config = config.db_providers.get("default_db")
    if not db_config:
        print("❌ DB провайдер 'default_db' не найден")
        return 1

    params = db_config.parameters
    conn = psycopg2.connect(
        host=params.get("host", "localhost"),
        port=params.get("port", 5432),
        database=params.get("database", "postgres"),
        user=params.get("user", "postgres"),
        password=params.get("password", ""),
    )
    conn.autocommit = True
    cursor = conn.cursor()

    # === ЗАПРОС: Получите данные для индексации ===
    cursor.execute("""
        SELECT id, <поле_для_поиска>, <дополнительное_поле>
        FROM <ваша_таблица>
        WHERE <поле_для_поиска> IS NOT NULL
        ORDER BY id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Найдено записей: {len(rows)}\n")

    all_vectors = []
    all_metadata = []

    for row in rows:
        row_id, поле_для_поиска, доп_поле = row

        # === Формируем поисковый текст из значимых полей ===
        search_parts = [str(поле_для_поиска)]
        if доп_поле:
            search_parts.append(str(доп_поле))
        search_text = " ".join(p for p in search_parts if p)

        # === Генерируем вектор ===
        vector = await embedding.generate_single(search_text)
        metadata = {
            "id": row_id,
            "<ваше_поле>": поле_для_поиска or "",
            "search_text": search_text,
        }
        all_vectors.append(vector)
        all_metadata.append(metadata)
        print(f"   [{row_id}] {поле_для_поиска[:60]}...")

    print(f"\n📊 Добавление {len(all_vectors)} векторов в FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    # === Сохраняем индекс — КЛЮЧ должен совпадать с vector_config ===
    await save_index(faiss_provider, vs_config, "my_new_table")

    print("\n" + "=" * 60)
    print("✅ ИНДЕКСАЦИЯ <НАЗВАНИЕ> ЗАВЕРШЕНА!")
    print("=" * 60)
    return 0
```

### Ключевые решения при создании функции

| Решение | Вопрос | Рекомендация |
|---------|--------|-------------|
| Какие поля индексировать | Что будет искать пользователь? | Берите текстовые поля, по которым имеет смысл искать |
| `search_text` | Что отправлять в embedding? | Объедините все значимые текстовые поля через пробел |
| Метаданные | Что хранить в индексе? | Все поля, которые могут понадобиться для отображения результатов и фильтрации |

### Добавьте CLI команду

В `build_parser()`:

```python
# my_new_table
subparsers.add_parser("my_new_table", help="Индексация <название>")
```

В `async_main()`:

```python
elif args.command == "my_new_table":
    return await index_my_new_table(embedding, faiss_provider, vs_config)
```

---

## 🔄 Шаг 3: Обновление `rebuild_all_indexes.py`

Добавьте новый раздел в `rebuild_all_indexes.py`:

```python
# =========================================================================
# N. ИНДЕКСАЦИЯ <НАЗВАНИЕ>
# =========================================================================
print("\n" + "=" * 60)
print("N. ИНДЕКСАЦИЯ <НАЗВАНИЕ>")
print("=" * 60)

cursor.execute("""
    SELECT id, <поля>
    FROM <ваша_таблица>
    WHERE <поле> IS NOT NULL
    ORDER BY id
""")
items = cursor.fetchall()
print(f"Найдено записей: {len(items)}")

items_provider = FAISSProvider(dimension=vs_config.embedding.dimension, config=vs_config.faiss)
await items_provider.initialize()

items_vectors = []
items_metadata = []
for row in items:
    # ... логика как в indexer.py ...
    vector = await embedding.generate_single(search_text)
    items_vectors.append(vector)
    items_metadata.append(metadata)

await items_provider.add(items_vectors, items_metadata)
items_index_path = storage_path / vs_config.indexes["my_new_table"]
await items_provider.save(str(items_index_path))
count = await items_provider.count()
print(f"✅ Сохранено my_new_table_index: {count} векторов")
await items_provider.shutdown()
```

---

## 🚀 Шаг 4: Запуск индексации

```bash
# Индексация только новой таблицы
python -m scripts.vector.indexer my_new_table

# Полная переиндексация всех таблиц
python -m scripts.vector.rebuild_all_indexes

# Создание пустых индексов (если БД ещё пуста)
python -m scripts.vector.indexer init
```

### Проверка статуса

После запуска проверьте:

```bash
ls data/vector/
# Должны появиться: my_new_table_index.faiss, my_new_table_index_metadata.json
```

В логах при старте приложения:

```
✅ Загружен индекс my_new_table: data\vector\my_new_table_index.faiss (N векторов)
```

---

## 🔗 Шаг 5: Связывание с валидацией параметров скриптов

### Файл: `core/components/skills/check_result/handlers/execute_script_handler.py`

В `SCRIPTS_REGISTRY` добавьте `validation` конфигурацию:

```python
SCRIPTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_items_by_field": {
        "description": "Получить элементы по полю",
        "name": "get_items_by_field",
        "sql": '''
            SELECT id, name, description
            FROM my_new_table
            WHERE name ILIKE %s
            ORDER BY id
            LIMIT %s
        ''',
        "required_parameters": ["name"],      # Параметр, требующий валидации
        "optional_parameters": [],
        "validation": {                        # ← Связь с FAISS и SQL
            "name": {
                "table": "my_new_table",                    # Таблица для SQL ILIKE (ступень 1)
                "search_fields": ["name"],                  # Поля для SQL поиска
                "vector_source": "my_new_table",            # Ключ FAISS индекса (ступень 2)
                # "vector_min_score": 0.7,                  # (опционально) мин. score
                # "vector_top_k": 3,                        # (опционально) топ-K результатов
            }
        }
    },
}
```

### Как работает валидация (3 ступени)

```
Параметр: "Иванов"
                │
                ▼
        ┌───────────────┐
        │ Ступень 1:    │  SELECT DISTINCT "name"
        │ SQL ILIKE     │  FROM "my_new_table"
        │               │  WHERE "name" ILIKE '%иванов%'
        │ Нашли? → ✅   │  → {"valid": True, "corrected_value": "Иванов И.И."}
        │ Не нашли? ↓   │
        └───────────────┘
                │
                ▼
        ┌───────────────┐
        │ Ступень 2:    │  vector_books.search(
        │ Vector Search │      query="Иванов",
        │ (FAISS)       │      source="my_new_table"
        │               │  )
        │ Score > 0.7?  │  → {"valid": True, "corrected_value": "Иванов И.И."}
        │ Да → ✅       │
        │ Нет? ↓        │
        └───────────────┘
                │
                ▼
        ┌───────────────┐
        │ Ступень 3:    │  SELECT DISTINCT "name"
        │ Fuzzy Match   │  FROM "my_new_table"
        │               │  → Levenshtein distance ≤ 2
        │ Нашли? → ✅   │  → {"valid": True, "corrected_value": "Иванов И.И."}
        │ Не нашли? ❌  │  → {"valid": False, "error": "..."}
        └───────────────┘
```

### Таблица решений для validation config

| Ситуация | Что указать | Результат |
|----------|-------------|-----------|
| Простое поле (имя, статус) | `table` + `search_fields` | SQL ILIKE найдёт точные совпадения |
| Текстовое поле (описание) | + `vector_source` | FAISS найдёт семантически похожие |
| Опечатки в именах | Всё выше + fuzzy fallback | Levenshtein исправит «Ивнанов» → «Иванов» |
| Без валидации | Не указывать `validation` | Параметр пройдёт как есть |

---

## ⚙️ Шаг 6: Настройка ParamValidator

### Файл: `core/components/skills/check_result/handlers/execute_script_handler.py`

Убедитесь что `ParamValidator` инициализирован **без схемы** (для таблиц в `public`):

```python
def __init__(self, skill):
    super().__init__(skill)
    self._param_validator = ParamValidator(
        executor=self.executor,
        schema=None,  # None = public схема (без указания "Lib"."table")
        log_callback=self._log_debug
    )
```

**Если таблица в именованной схеме** (например `audit.violations`):

```python
self._param_validator = ParamValidator(
    executor=self.executor,
    schema="audit",  # Указываем схему
    log_callback=self._log_debug
)
```

И SQL в скриптах тоже должен использовать схему:

```python
"sql": 'SELECT ... FROM "audit"."violations" WHERE ...',
```

---

## ✅ Чек-лист добавления новой векторной БД

### Конфигурация

- [ ] Добавлен ключ в `VectorSearchConfig.indexes` (`core/config/vector_config.py`)
- [ ] Обновлён `validate_indexes()` с новым `required` set
- [ ] FAISS провайдер будет создан автоматически при `_init_vector_search()`

### Индексация

- [ ] Создана функция `index_<source>()` в `scripts/vector/indexer.py`
- [ ] Добавлена CLI команда в `build_parser()`
- [ ] Добавлен обработчик в `async_main()`
- [ ] Добавлен раздел в `scripts/vector/rebuild_all_indexes.py`
- [ ] Индекс создан: `data/vector/<source>_index.faiss`
- [ ] Метаданные созданы: `data/vector/<source>_metadata.json`

### Валидация

- [ ] В `SCRIPTS_REGISTRY` добавлен `validation` блок для параметров
- [ ] `vector_source` совпадает с ключом в `VectorSearchConfig.indexes`
- [ ] `table` совпадает с именем таблицы в PostgreSQL
- [ ] `search_fields` содержат поля, по которым имеет смысл искать
- [ ] `ParamValidator` инициализирован с правильной схемой

### Проверка

- [ ] `python -m scripts.vector.indexer <source>` — отработал без ошибок
- [ ] В логе: `✅ Загружен индекс <source>: ... (N векторов)`
- [ ] Валидация параметра работает (agent может исправить опечатки)
- [ ] Скрипт выполняется с валидированными параметрами

---

## 📖 Примеры

### Пример 1: Добавление индекса «employees»

**Конфигурация:**

```python
# core/config/vector_config.py
indexes: Dict[str, str] = {
    "books": "books_index.faiss",
    "authors": "authors_index.faiss",
    "audits": "audits_index.faiss",
    "violations": "violations_index.faiss",
    "employees": "employees_index.faiss",  # ← Новое
}
```

**Функция индексации:**

```python
# scripts/vector/indexer.py
async def index_employees(embedding, faiss_provider, vs_config) -> int:
    """Индексация сотрудников — по ФИО и должности."""
    # ... SELECT id, full_name, position FROM employees ...
    # ... vector = embedding.generate_single(f"{full_name} {position}") ...
    # ... metadata = {"employee_id": id, "full_name": ..., "position": ...} ...
    await save_index(faiss_provider, vs_config, "employees")
```

**Скрипт с валидацией:**

```python
# execute_script_handler.py
"get_employee_tasks": {
    "description": "Получить задачи сотрудника",
    "sql": 'SELECT ... FROM tasks WHERE assigned_to ILIKE %s LIMIT %s',
    "required_parameters": ["employee"],
    "validation": {
        "employee": {
            "table": "employees",
            "search_fields": ["full_name"],
            "vector_source": "employees",
        }
    }
},
```

**Запуск:**

```bash
python -m scripts.vector.indexer employees
```

### Пример 2: Скрипт без валидации

Если параметр — числовой ID или дата, валидация не нужна:

```python
"get_audit_by_id": {
    "description": "Получить проверку по ID",
    "sql": 'SELECT * FROM audits WHERE id = %s',
    "required_parameters": ["audit_id"],
    # Нет "validation" — ID не нуждается в семантической проверке
},
```

### Пример 3: Валидация по нескольким полям

```python
"search_violations": {
    "sql": 'SELECT ... FROM violations WHERE description ILIKE %s OR violation_code ILIKE %s LIMIT %s',
    "required_parameters": ["query"],
    "validation": {
        "query": {
            "table": "violations",
            "search_fields": ["description", "violation_code"],  # Поиск по двум полям
            "vector_source": "violations",
            "vector_min_score": 0.6,   # Более мягкий порог
            "vector_top_k": 5,         # Больше кандидатов
        }
    }
},
```

---

## 🐛 Решение проблем

### Индекс не загружается при старте

**Симптом:** `⚠️ Индекс my_table не найден: ...`

**Причина:** Файл индекса не существует или путь неверный.

**Решение:**
```bash
# Проверить наличие файлов
ls data/vector/my_table_index*

# Пересоздать индекс
python -m scripts.vector.indexer my_table
```

### Vector validation всегда падает

**Симптом:** `Vector validation failed: ...`, fallback на fuzzy

**Причины:**
1. FAISS индекс пустой — `count() == 0`
2. `vector_source` не совпадает с ключом в `indexes`
3. `min_score` слишком высокий

**Решение:**
```python
# Проверить count
infra = infrastructure_context
faiss = infra.get_faiss_provider("my_source")
print(await faiss.count())  # Должно быть > 0

# Проверить имя
print(vs_config.indexes.keys())  # Должно содержать "my_source"

# Снизить порог
"vector_min_score": 0.5,  # Было 0.7
```

### SQL validation не находит значения

**Симптом:** `SQL validation failed`, но значение есть в таблице

**Причины:**
1. Неверное имя таблицы (регистр в PostgreSQL)
2. Неверное имя поля
3. Схема не указана или неверная

**Решение:**
```python
# Проверить SQL вручную
cursor.execute('SELECT DISTINCT "name" FROM "my_table" WHERE "name" ILIKE %s', ['%тест%'])
print(cursor.fetchall())

# Если таблица в схеме:
"table": "my_table",  # Без схемы
# И в ParamValidator:
schema="my_schema"
```

### Ошибка: "Indexes must include: ..."

**Симптом:** ValidationError при старте

**Причина:** В `indexes` не все обязательные ключи.

**Решение:** Добавьте недостающий ключ в `indexes` и обновите `validate_indexes()`.

---

## 🔑 Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `core/config/vector_config.py` | Регистрация имён индексов и валидация |
| `core/infrastructure_context/infrastructure_context.py` | Загрузка FAISS индексов при старте |
| `core/components/skills/utils/param_validator.py` | 3-ступенчатая валидация |
| `core/components/skills/check_result/handlers/execute_script_handler.py` | Скрипты с validation config |
| `scripts/vector/indexer.py` | Универсальный индексатор |
| `scripts/vector/rebuild_all_indexes.py` | Полная переиндексация |
| `data/vector/` | Хранилище FAISS индексов |

---

## 🔗 Связанные документы

| Документ | Описание |
|----------|----------|
| `docs/vector_search/VECTOR_LIFECYCLE.md` | Жизненный цикл векторной БД |
| `docs/vector_search/README.md` | Навигация по документации vector search |
| `docs/vector_search/UNIVERSAL_SPEC.md` | Универсальная спецификация |
| `docs/skill_check_result_guide.md` | Гайд по навыку check_result |

---

## 🔍 Capability: check_result.vector_search

### Обзор

Помимо валидации параметров, FAISS индексы используются для **семантического поиска** по текстам актов через отдельную capability `check_result.vector_search`.

Это позволяет агенту находить релевантные фрагменты по смыслу, а не по точному совпадению слов.

### Когда использовать

| Ситуация | Инструмент |
|----------|-----------|
| «Покажи все проверки в финансовом отделе» | `execute_script` + `get_audit_by_status` |
| «Нашлись ли нарушения с формулировкой "не проведена инвентаризация"?» | **`vector_search`** |
| «Кто ответственен за просроченные нарушения?» | `execute_script` + `get_overdue_violations` |
| «Все случаи, похожие на коррупцию в закупках» | **`vector_search`** |
| «Статистика по проверкам» | `execute_script` + `get_audit_statistics` |

### Архитектура

```
check_result.vector_search
        │
        ▼
┌───────────────────────┐
│  VectorSearchHandler   │
│  (handler)             │
└─────────┬─────────────┘
          │
          ▼
┌───────────────────────┐
│  vector_books.search   │  ← ActionExecutor
│  (VectorBooksTool)     │
└─────────┬─────────────┘
          │
          ▼
┌───────────────────────┐
│  FAISS Provider        │  ← audits_index.faiss
│  source="audits"       │  ← violations_index.faiss
│  source="violations"   │
└───────────────────────┘
```

### Файлы capability

| Файл | Назначение |
|------|-----------|
| `core/components/skills/check_result/handlers/vector_search_handler.py` | Обработчик |
| `data/contracts/skill/check_result/check_result.vector_search_input_v1.0.0.yaml` | Входной контракт |
| `data/contracts/skill/check_result/check_result.vector_search_output_v1.0.0.yaml` | Выходной контракт |
| `data/prompts/skill/check_result/check_result.vector_search.system_v1.0.0.yaml` | Системный промпт |

### Параметры (input)

```yaml
query: "нарушения связанные с контрактами"    # обязательный
source: violations                             # audits | violations
top_k: 10                                      # 1-100
min_score: 0.5                                 # 0.0-1.0
```

### Результаты (output)

```json
{
  "results": [
    {
      "type": "violation",
      "score": 0.82,
      "audit_id": 3,
      "audit_title": "Аудит закупочной деятельности",
      "violation_id": 142,
      "violation_code": "VIOL-03-015",
      "description": "Отсутствует утвержденный регламент закупки...",
      "severity": "Высокая",
      "status": "Открыто",
      "responsible": "Козлов Д.Е.",
      "matched_text": "...договор не содержит существенных условий..."
    }
  ],
  "total_found": 1,
  "query": "нарушения связанные с контрактами",
  "source": "violations",
  "execution_time": 0.15
}
```

### Как добавить свою capability векторного поиска

Если вам нужен ещё один тип семантического поиска (например, по полным текстам актов):

**1. Создать handler:**
```python
# core/components/skills/check_result/handlers/my_vector_search_handler.py
class MyVectorSearchHandler(SkillHandler):
    capability_name = "check_result.my_vector_search"

    async def execute(self, params, execution_context=None):
        # Вызов vector_books.search с кастомной логикой
        results = await self._vector_search(query, source="my_source")
        return self._format_results(results)
```

**2. Зарегистрировать в `skill.py`:**
```python
from .handlers.vector_search_handler import VectorSearchHandler
from .handlers.my_vector_search_handler import MyVectorSearchHandler

self._handlers = {
    "check_result.execute_script": ExecuteScriptHandler(self),
    "check_result.generate_script": GenerateScriptHandler(self),
    "check_result.vector_search": VectorSearchHandler(self),
    "check_result.my_vector_search": MyVectorSearchHandler(self),  # ← Новое
}
```

**3. Добавить в `get_capabilities()`:**
```python
Capability(
    name="check_result.my_vector_search",
    description="Описание capability",
    skill_name=self.name,
    supported_strategies=["react"],
    visiable=True
)
```

**4. Обновить `__init__.py` handlers:**
```python
from .my_vector_search_handler import MyVectorSearchHandler

__all__ = [
    "ExecuteScriptHandler",
    "GenerateScriptHandler",
    "VectorSearchHandler",
    "MyVectorSearchHandler",
]
```

**5. Создать YAML контракты:**
- `data/contracts/skill/check_result/check_result.my_vector_search_input_v1.0.0.yaml`
- `data/contracts/skill/check_result/check_result.my_vector_search_output_v1.0.0.yaml`

**6. Создать системный промпт:**
- `data/prompts/skill/check_result/check_result.my_vector_search.system_v1.0.0.yaml`

---

*Документ создан: 2026-04-12*
*Версия: 1.0.0*
*Статус: ✅ Утверждено*

# Документация: SOURCE_CONFIG — настройка источников векторного поиска

> **Назначение:** Описание структуры `SOURCE_CONFIG` в `core/config/vector_config.py` и того, как параметры влияют на индексацию, embedding и поиск.

---

## 1. Общая структура

`SOURCE_CONFIG` — это словарь `Dict[str, Dict[str, Any]]`, где:
- **Ключ** — имя источника (например, `"violations"`, `"books"`)
- **Значение** — конфигурация источника с параметрами для SQL-запроса, индексации и инструкций

```python
SOURCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "имя_источника": {
        # Параметры подключения к БД
        "schema": "...",
        "table": "...",
        "select_cols": "...",
        "text_fields": [...],
        "metadata_fields": [...],
        "pk_column": "...",
        "where_clause": "...",
        "order_by": "...",
        "join_clause": "...",  # опционально

        # Инструкция для embedding (новое)
        "instruction": "...",
    },
}
```

---

## 2. Поля конфигурации

### 2.1. Параметры SQL-запроса

| Поле | Тип | Обязательное | Описание | Пример |
|------|-----|-------------|----------|---------|
| `schema` | `str` | Да | Схема БД | `"oarb"` |
| `table` | `str` | Да | Таблица (можно с алиасом для JOIN) | `"violations v"` |
| `select_cols` | `str` | Да | Список полей для SELECT (через запятую) | `"v.id, v.description, a.title as audit_title"` |
| `pk_column` | `str` | Да | Поле primary key (используется для `document_id`) | `"id"` |
| `text_fields` | `List[str]` | Да | Поля, из которых собирается `search_text` для векторизации | `["description", "violation_code"]` |
| `metadata_fields` | `List[str]` | Да | Поля, сохраняемые в `RowMetadata.row` (полная строка) | `["id", "description", "severity"]` |
| `where_clause` | `str` | Нет | Условие WHERE (включая ключевое слово WHERE) | `"WHERE v.description IS NOT NULL"` |
| `order_by` | `str` | Нет | Сортировка (включая ключевое слово ORDER BY) | `"ORDER BY v.id"` |
| `join_clause` | `str` | Нет | JOIN с другими таблицами (включая ключевое слово JOIN) | `"JOIN oarb.audits a ON v.audit_id = a.id"` |

---

### 2.2. Параметр `instruction` (NEW)

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `instruction` | `str` | Нет | Инструкция для embedding-провайдера (добавляется перед текстом при векторизации) |

**Как это работает:**
```python
"instruction": "Дан вопрос о нарушении. Необходимо найти абзац текста с описанием нарушения."
```

При индексации для каждого чанка инструкция передаётся в `embedding.generate_single()`:
```python
vector = await embedding.generate_single(chunk_text, instruction=source_instruction)
```

**Для каких провайдеров работает:**
- ✅ `Qwen3EmbeddingProvider` — добавляет `Instruct: {instruction}\nQuery: {text}`
- ✅ `GigaEmbeddingsProvider` — добавляет `Instruct: {instruction}\nQuery: {text}`
- ❌ `SentenceTransformersProvider` — игнорирует (не поддерживает инструкции)

**Приоритет инструкций:**
1. Явная инструкция из `SOURCE_CONFIG[source]["instruction"]` (передаётся при индексации)
2. Инструкция из `EmbeddingConfig.instruction` (глобальная, в `vector_config.py`)
3. Если обе пустые — инструкция не добавляется

---

## 3. Как данные влияют на процесс

### 3.1. Индексация (`scripts/vector/indexer.py`)

```
┌─────────────────────────────────────────────────────────────┐
│                    SQL QUERY (из конфига)                    │
│  SELECT {select_cols} FROM {schema}.{table} {join} {where} │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              ДЛЯ КАЖДОЙ СТРОКИ (row_dict)                  │
│                                                             │
│  1. search_text = " ".join(row_dict[f] for f in text_fields)│
│     ↑ Собирается ТОЛЬКО из text_fields                      │
│                                                             │
│  2. Chunking:                                              │
│     chunks = await chunking.split(search_text, document_id)  │
│     ↑ Если search_text > chunk_size (500) → разбивается     │
│                                                             │
│  3. ДЛЯ КАЖДОГО ЧАНКА:                                    │
│     - vector = embedding.generate_single(chunk_text,         │
│                                      instruction=instr)    │
│     - metadata = RowMetadata(                               │
│         row=row_dict,        ← ВСЯ СТРОКА ЦЕЛИКОМ           │
│         content=chunk_text,  ← ТОЛЬКО ТЕКСТ ЧАНКА           │
│         search_text=chunk_text,                              │
│         chunk_index=N,                                      │
│         total_chunks=M,                                     │
│       )                                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2. Влияние `text_fields`

**Что попадает в вектор:**
```python
# Пример: text_fields = ["description", "violation_code", "audit_title"]
search_text = " ".join([
    row_dict["description"],    # Основное поле для поиска
    row_dict["violation_code"], # Код нарушения (для точности)
    row_dict["audit_title"],    # Название аудита (контекст)
])
```

**Важно:**
- Только поля из `text_fields` участвуют в создании вектора
- Если поле пустое (`None` или `""`) — оно пропускается
- Порядок полей в `text_fields` важен: первые поля имеют больший вес в `search_text`

### 3.3. Влияние `metadata_fields`

**Что попадает в `RowMetadata.row` (полная строка):**
```python
row_dict = dict(zip(col_names, row))
# row_dict содержит ВСЕ поля из select_cols, но в метаданных сохраняется
# только то, что указано в metadata_fields (и pk_column)

meta = RowMetadata(
    row=row_dict,  # ← Всё из select_cols, но логично указывать metadata_fields
)
```

**Рекомендация:** `metadata_fields` должно включать все поля, которые могут понадобиться при отображении результатов поиска.

### 3.4. Влияние `instruction`

Инструкция помогает embedding-модели понять **контекст задачи**:

| Источник | Инструкция | Зачем |
|----------|-----------|-------|
| `violations` | "Дан вопрос о нарушении..." | Модель ищет семантическое сходство с описанием нарушений |
| `books` | "Дан вопрос о книге..." | Модель фокусируется на названиях и описаниях книг |
| `authors` | "Дан вопрос о людях..." | Модель ищет по именам авторов |

**Без инструкции:** Модель использует "общий" контекст, что может снизить качество поиска для специфичных доменов.

---

## 4. Примеры конфигурации

### 4.1. Простой источник (одна таблица)

```python
"books": {
    "schema": "Lib",
    "table": "books",
    "select_cols": "id, title, isbn, publication_date, author_id",
    "text_fields": ["title"],              # Векторизуем только название
    "metadata_fields": ["id", "title", "isbn", "publication_date", "author_id"],
    "pk_column": "id",
    "where_clause": "WHERE title IS NOT NULL",
    "order_by": "ORDER BY title",
    "instruction": "Дан вопрос о книге. Необходимо найти абзац текста с названием или описанием книги.",
}
```

**Поведение:**
- `search_text` = `row_dict["title"]`
- Если `title` короче 500 символов → один чанк (`total_chunks=1`)
- Если `title` длинный (маловероятно) → разбивается

---

### 4.2. Сложный источник (JOIN с другой таблицей)

```python
"violations": {
    "schema": "oarb",
    "table": "violations v",
    "select_cols": """v.id, v.violation_code, v.description, v.recommendation,
                      v.severity, v.status, v.responsible, v.deadline, v.audit_id,
                      a.title as audit_title, a.status as audit_status""",
    "text_fields": ["description", "violation_code", "audit_title"],
    "metadata_fields": ["id", "violation_code", "description", "severity", "status",
                       "responsible", "deadline", "audit_id", "audit_title", "audit_status"],
    "pk_column": "id",
    "where_clause": "WHERE v.description IS NOT NULL",
    "order_by": "ORDER BY v.id",
    "join_clause": "JOIN oarb.audits a ON v.audit_id = a.id",
    "instruction": "Дан вопрос о нарушении. Необходимо найти абзац текста с описанием нарушения.",
}
```

**Поведение:**
- `search_text` = `description + " " + violation_code + " " + audit_title`
- `description` может быть длинным → разбивается на чанки по 500 символов
- Для каждого чанка создаётся отдельный вектор
- В `row` каждого чанка лежит **полная строка** (все поля из `select_cols`)

---

### 4.3. Источник с короткими текстами (без chunking)

```python
"authors": {
    "schema": "Lib",
    "table": "authors",
    "select_cols": "id, first_name, last_name, birth_date",
    "text_fields": ["first_name", "last_name"],
    "metadata_fields": ["id", "first_name", "last_name", "birth_date"],
    "pk_column": "id",
    "where_clause": "WHERE last_name IS NOT NULL",
    "order_by": "ORDER BY last_name, first_name",
    "instruction": "Дан вопрос о людях (авторах). Необходимо найти абзац текста с ответом о человеке.",
}
```

**Поведение:**
- `search_text` = `"Имя Фамилия"` (обычно < 100 символов)
- Chunking не применяется (текст < `chunk_size`)
- `total_chunks` всегда = 1

---

## 5. Как проверить работу

### 5.1. Запуск индексации

```bash
# Индексировать конкретный источник
python -m scripts.vector.indexer --sources violations

# Индексировать всё
python -m scripts.vector.indexer

# Индексировать по скиллу (группа источников)
python -m scripts.vector.indexer --skill check_result
```

### 5.2. Логи при индексации

При индексации выводятся:
```
📐 Chunking: size=500, overlap=50, min_size=100
💡 Пример метаданных (первая запись):
   Ключи: ['source', 'table', 'primary_key', 'pk_value', 'row', ...]
   chunk_index=0, total_chunks=3  ← Если текст был разбит на 3 чанка
```

### 5.3. Проверка метаданных в FAISS

В метаданных каждого вектора:
```python
{
    "source": "violations",
    "table": "oarb.violations",
    "primary_key": "id",
    "pk_value": 123,
    "row": {                           # ← ВСЯ строка целиком
        "id": 123,
        "description": "Длинный текст...",
        "violation_code": "V-001",
        ...
    },
    "chunk_index": 0,                   # ← Индекс чанка (0, 1, 2, ...)
    "total_chunks": 3,                   # ← Всего чанков для этой строки
    "search_text": "текст чанка...",    # ← Только этот чанк
    "content": "текст чанка...",         # ← Только этот чанк
}
```

---

## 6. Частые ошибки

### 6.1. `text_fields` не совпадает с `select_cols`

❌ **Неправильно:**
```python
"select_cols": "id, title",
"text_fields": ["description"],  # ← Нет в select_cols!
```

✅ **Правильно:**
```python
"select_cols": "id, title, description",
"text_fields": ["description"],
```

---

### 6.2. `pk_column` не в `select_cols`

❌ **Неправильно:**
```python
"select_cols": "title, description",  # ← Нет id!
"pk_column": "id",
```

✅ **Правильно:**
```python
"select_cols": "id, title, description",
"pk_column": "id",
```

---

### 6.3. Забыли про `JOIN` в сложных запросах

❌ **Неправильно:**
```python
"select_cols": "v.id, v.description, a.title",  # ← a.title из другой таблицы
# Нет join_clause!
```

✅ **Правильно:**
```python
"select_cols": "v.id, v.description, a.title",
"join_clause": "JOIN oarb.audits a ON v.audit_id = a.id",
```

---

## 7. Настройка chunking (глобальная)

Chunking настраивается в `VectorSearchConfig` (в `vector_config.py`):

```python
class ChunkingConfig(BaseModel):
    enabled: bool = True           # Включён ли chunking
    strategy: str = "text"         # Стратегия: text/semantic/hybrid
    chunk_size: int = 500          # Макс. размер чанка (символы)
    chunk_overlap: int = 50        # Перекрытие между чанками
    min_chunk_size: int = 100      # Минимальный размер чанка
    separators: List[str] = [...]  # Разделители (заголовки → абзацы → предложения)
```

**Как это влияет:**
- `chunk_size=500` — если `search_text` > 500 символов, он разбивается
- `chunk_overlap=50` — конец предыдущего чанка дублируется в начало следующего (для контекста)
- `min_chunk_size=100` — чанки короче 100 символов отбрасываются

---

## 8. Как данные влияют на результат — подробный разбор

### 8.1. Влияние `text_fields` на качество поиска

`text_fields` определяет, **какие поля попадают в вектор**. От этого зависит, что сможет "найти" семантический поиск.

**Пример 1: Только название (плохо)**
```python
"text_fields": ["title"],  # Только название книги
```
- ✅ Найдёт запросы типа "книги про войну"
- ❌ Не найдёт запросы про сюжет, если его нет в title

**Пример 2: Название + описание (хорошо)**
```python
"text_fields": ["title", "description"],
```
- ✅ Найдёт и по названию, и по смыслу описания
- ⚠️ description может быть длинным → больше чанков → больше векторов

**Пример 3: Добавление контекста (лучше)**
```python
"text_fields": ["description", "violation_code", "audit_title"],
```
- `violation_code` — помогает находить по коду (V-001)
- `audit_title` — добавляет контекст аудита
- ✅ Более точные результаты для специфичных запросов

---

### 8.2. Влияние `instruction` на векторы

Инструкция **меняет само значение вектора**. Разные инструкции → разные векторы для одного текста.

**Без инструкции:**
```python
"instruction": None,  # или не указано
# Вектор отражает "общий смысл" текста
```

**С инструкцией для нарушений:**
```python
"instruction": "Дан вопрос о нарушении. Необходимо найти абзац текста с описанием нарушения."
# Вектор смещается в сторону "нарушение-центричного" смысла
# Запрос "какие нарушения по безопасности?" найдёт лучше
```

**С инструкцией для книг:**
```python
"instruction": "Дан вопрос о книге. Необходимо найти абзац текста с названием или описанием книги."
# Вектор смещается в сторону "книжного" контекста
```

**Важно:** Инструкция добавляется только при индексации (к чанкам) и при поиске (к запросу). Они должны быть **согласованы** — если меняете инструкцию в `SOURCE_CONFIG`, нужно переиндексировать!

---

### 8.3. Влияние `chunk_size` на количество векторов

| Длина `search_text` | `chunk_size=500` | Результат |
|----------------------|------------------|-----------|
| 300 символов | < 500 | 1 чанк, 1 вектор |
| 1200 символов | > 500 | 3 чанка, 3 вектора |
| 5000 символов | > 500 | ~10 чанков, 10 векторов |

**Формула:** `total_chunks ≈ len(search_text) / (chunk_size - chunk_overlap)`
- Для `chunk_size=500, overlap=50`: ~1 чанк на 450 символов текста

**Как это влияет на поиск:**
- ✅ Больше чанков = точнее поиск по длинным текстам
- ❌ Больше чанков = медленнее поиск (больше векторов сравнивать)
- ❌ Больше чанков = больше места на диске

---

### 8.4. Влияние `metadata_fields` на отображение результатов

`metadata_fields` определяет, **какие поля попадут в `row`** метаданных вектора. Это влияет на то, что увидит пользователь при выводе результатов.

**Пример:** При поиске нарушений
```python
"metadata_fields": ["id", "violation_code", "description", "severity", "status", "responsible"]
```

В результатах поиска:
```python
{
    "source": "violations",
    "score": 0.85,
    "content": "текст чанка...",
    "metadata": {
        "row": {
            "id": 123,
            "violation_code": "V-001",
            "description": "полный текст...",  # ← ВСЯ строка, не только чанк!
            "severity": "Высокая",
            "status": "Открыто",
            "responsible": "Иванов И.И.",
            # ... все поля из metadata_fields
        }
    }
}
```

**Если не включить поле в `metadata_fields`:**
- Оно не попадёт в `row`
- При отображении результатов это поле будет недоступно
- Придётся делать доп. запрос к БД (медленно)

---

### 8.5. Влияние `join_clause` на обогащение данных

JOIN позволяет подтянуть данные из связанных таблиц в `search_text` и `row`.

**Без JOIN:**
```python
"table": "violations v",
"select_cols": "v.id, v.description",
"text_fields": ["description"],
# search_text = только description нарушения
```

**С JOIN:**
```python
"table": "violations v",
"select_cols": "v.id, v.description, a.title as audit_title",
"join_clause": "JOIN oarb.audits a ON v.audit_id = a.id",
"text_fields": ["description", "audit_title"],
# search_text = description + " " + audit_title
```

**Преимущества:**
- ✅ Более контекстный поиск (нарушение + название аудита)
- ✅ Можно искать по названию аудита
- ⚠️ Нужно убедиться, что JOIN не дублирует строки (уникальность по pk_column)

---

### 8.6. Влияние `where_clause` на полноту индекса

`where_clause` определяет, **какие строки попадут в индекс**.

**Примеры:**
```python
# Только строки с заполненным описанием (обязательно!)
"where_clause": "WHERE v.description IS NOT NULL",

# Исключить закрытые аудиты
"where_clause": "WHERE v.description IS NOT NULL AND a.status != 'Закрыт'",

# Только нарушения высокой важности
"where_clause": "WHERE v.severity = 'Высокая'",
```

**Риски:**
- ❌ Слишком строгий WHERE → пустой индекс → поиск не работает
- ❌ Слишком мягкий WHERE → индекс раздувается → медленный поиск

---

## 9. Резюме

| Параметр | Влияет на | Как |
|----------|-----------|----|
| `text_fields` | Что векторизуется | Собирает `search_text` для embedding |
| `instruction` | Качество поиска | Меняет само значение вектора (добавляется перед текстом) |
| `metadata_fields` | Что в `row` | Поля, доступные при отображении результатов |
| `select_cols` | Какие данные доступны | Должны включать всё из `text_fields` + `metadata_fields` + `pk_column` |
| `chunk_size` | Количество векторов | Если `search_text` > 500 → разбивается на чанки |
| `join_clause` | Обогащение данных | Позволяет добавить контекст из связанных таблиц |
| `where_clause` | Полнота индекса | Фильтрует строки, попадающие в индекс |
| `chunk_overlap` | Связность чанков | Конец предыдущего чанка дублируется в начало следующего |

# Отчёт о доработке навыка Book Library

## Дата
8 марта 2026 г.

## Проблема
Навык `book_library` использовал упрощённую схему БД с одной таблицей `books` и текстовым полем `author`. В реальной БД используется **нормализованная схема** с двумя таблицами:
- `"Lib".books` (id, title, author_id, isbn, publication_date, genre)
- `"Lib".authors` (id, first_name, last_name, birth_date)

Связь между таблицами осуществляется через `author_id` (FOREIGN KEY).

## Внесённые изменения

### 1. scripts_registry.py
**Файл:** `core/application/skills/book_library/scripts_registry.py`

#### Обновлена схема в документации модуля:
```python
СХЕМА БАЗЫ ДАННЫХ (нормализованная):
    "Lib".books (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        author_id INTEGER REFERENCES "Lib".authors(id),
        year INTEGER,
        isbn TEXT,
        genre TEXT
    )
    
    "Lib".authors (
        id SERIAL PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        birth_date DATE
    )
```

#### Обновлены все SQL-скрипты (10 шт.):

| Скрипт | Было | Стало |
|--------|------|-------|
| `get_all_books` | `SELECT ... FROM books` | `SELECT ... FROM "Lib".books b JOIN "Lib".authors a ON b.author_id = a.id` |
| `get_books_by_author` | `WHERE author = $1` | `WHERE a.last_name ILIKE $1` |
| `get_books_by_genre` | `FROM books WHERE genre = $1` | `FROM "Lib".books b JOIN "Lib".authors a ON b.author_id = a.id WHERE b.genre = $1` |
| `get_books_by_year_range` | `WHERE year BETWEEN` | `WHERE EXTRACT(YEAR FROM b.publication_date) BETWEEN` |
| `get_book_by_id` | `FROM books WHERE id = $1` | `FROM "Lib".books b JOIN "Lib".authors a ON b.author_id = a.id WHERE b.id = $1` |
| `count_books_by_author` | `SELECT COUNT(*), author FROM books WHERE author = $1` | `SELECT COUNT(*), a.last_name, a.first_name FROM "Lib".books b JOIN "Lib".authors a ON b.author_id = a.id WHERE a.last_name ILIKE $1 GROUP BY a.id` |
| `get_books_by_title_pattern` | `FROM books WHERE title ILIKE $1` | `FROM "Lib".books b JOIN "Lib".authors a ON b.author_id = a.id WHERE b.title ILIKE $1` |
| `get_distinct_authors` | `SELECT DISTINCT author FROM books` | `SELECT DISTINCT a.id, a.first_name, a.last_name FROM "Lib".authors a JOIN "Lib".books b ON a.id = b.author_id` |
| `get_distinct_genres` | `FROM books` | `FROM "Lib".books` |
| `get_genre_statistics` | `AVG(year)` | `AVG(EXTRACT(YEAR FROM publication_date))` |

#### Возвращаемые поля (для всех скриптов):
```python
book_id, book_title, isbn, publication_date,
author_id, first_name, last_name, birth_date
```

### 2. skill.py
**Файл:** `core/application/skills/book_library/skill.py`

#### Обновлена схема для LLM-генерации SQL:
```python
"table_schema": """
    "Lib".books (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        author_id INTEGER REFERENCES "Lib".authors(id),
        isbn TEXT,
        publication_date DATE,
        genre TEXT
    ),
    "Lib".authors (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        birth_date DATE
    )
"""
```

#### Обновлен fallback SQL в `_search_books_dynamic`:
```python
sql_query = f"""
    SELECT 
        b.id as book_id,
        b.title as book_title,
        b.isbn,
        b.publication_date,
        a.id as author_id,
        a.first_name,
        a.last_name,
        a.birth_date
    FROM "Lib".books b
    JOIN "Lib".authors a ON b.author_id = a.id
    WHERE b.title ILIKE '%{query_val}%' 
       OR a.last_name ILIKE '%{query_val}%' 
       OR a.first_name ILIKE '%{query_val}%'
    LIMIT {max_results_val}
"""
```

#### Обновлено описание capability:
```python
description="Выполнение заготовленного SQL-скрипта по имени. 10 скриптов: ... Нормализованная схема: Lib.books JOIN Lib.authors. Быстро ~100мс."
```

### 3. Контракты (YAML)

#### book_library.search_books_output_v1.0.0.yaml
Обновлена схема выходных данных:
```yaml
rows:
  items:
    type: object
    properties:
      book_id: {type: integer}
      book_title: {type: string}
      isbn: {type: string}
      publication_date: {type: string, format: date}
      author_id: {type: integer}
      first_name: {type: string}
      last_name: {type: string}
      birth_date: {type: string, format: date}
```

#### book_library.execute_script_output_v1.0.0.yaml
Добавлены свойства для полей нормализованной схемы:
```yaml
rows:
  items:
    properties:
      book_id, book_title, isbn, publication_date,
      author_id, first_name, last_name, birth_date,
      genre, count, avg_year
```

## Пример использования

### Поиск книг Пушкина (статический скрипт):
```python
result = await skill.execute(
    capability="book_library.execute_script",
    parameters={
        "script_name": "get_books_by_author",
        "author": "%Пушкин%",
        "max_rows": 50
    }
)
```

**SQL:**
```sql
SELECT 
    b.id as book_id,
    b.title as book_title,
    b.isbn,
    b.publication_date,
    a.id as author_id,
    a.first_name,
    a.last_name,
    a.birth_date
FROM "Lib".books b
JOIN "Lib".authors a ON b.author_id = a.id
WHERE a.last_name ILIKE '%Пушкин%'
ORDER BY b.title
LIMIT 50;
```

### Динамический поиск:
```python
result = await skill.execute(
    capability="book_library.search_books",
    parameters={
        "query": "Найти все книги Пушкина",
        "max_results": 10
    }
)
```

## Преимущества новой схемы

1. **Нормализация данных** — информация об авторах хранится один раз
2. **Точный поиск по фамилии** — `ILIKE` по полю `last_name` вместо текстового `author`
3. **Расширенные данные** — возвращаются `first_name`, `birth_date` автора
4. **Целостность данных** — FOREIGN KEY гарантирует существование автора
5. **Гибкость** — легко добавить новые поля автора без изменения таблицы книг

## Проверка синтаксиса
```bash
python -m py_compile core/application/skills/book_library/scripts_registry.py
python -m py_compile core/application/skills/book_library/skill.py
```
✅ Оба файла прошли проверку без ошибок.

## Результаты тестов

```bash
pytest tests/integration/test_book_library_simple.py -v
```

| Тест | Статус | Причина |
|------|--------|---------|
| `test_get_all_books` | ✅ PASS | Скрипт работает корректно |
| `test_get_books_by_author` | ❌ FAIL | Проблема с передачей параметров в executor.execute_action() |
| `test_context_recording` | ❌ FAIL | Отдельная проблема с записью шагов в контекст |
| `test_invalid_script_name` | ✅ PASS | Ошибка обрабатывается корректно |
| `test_search_books_by_author` | ✅ PASS | Динамический поиск работает (fallback SQL) |

### Известная проблема

**Проблема:** Статические скрипты (`execute_script`) не возвращают результаты, хотя SQL-запрос правильный и параметры передаются верно.

**Диагностика:**
- Прямой SQL через `db.execute()` работает: возвращает 5 книг Пушкина
- Параметры формируются правильно: `{'p1': '%Пушкин%', 'p2': 50}`
- `executor.execute_action(action_name="sql_query.execute", ...)` не выполняет запрос

**Причина:** `ActionExecutor` не находит action `sql_query.execute` или не передаёт параметры в `db_provider`.

**Временное решение:** Используйте динамический поиск (`search_books`) — он работает через fallback SQL.

**Требуется:** Исправить регистрацию action для `sql_query.execute` или использовать прямой вызов сервиса.

## Обратная совместимость
**НЕТ** — изменения ломают обратную совместимость:
- Старые запросы с полем `author` не будут работать
- Старые контракты с полями `id`, `title`, `author`, `year`, `genre` не соответствуют новым
- Требуется обновить код, использующий навык

## Миграция
Для обновления существующего кода:
1. Заменить `author` → `last_name` + `first_name`
2. Заменить `year` → `EXTRACT(YEAR FROM publication_date)`
3. Заменить `id` → `book_id`
4. Заменить `title` → `book_title`

# 📚 Vector Search API Documentation

**Версия:** 1.0.0  
**Дата:** 2026-02-19

---

## 📋 Обзор

API векторного поиска предоставляет возможности для:
- Семантического поиска по документам
- Индексации новых документов
- LLM анализа контента
- Работы с книгами (поиск + текст + анализ)

---

## 🔧 Компоненты

### 1. VectorBooksTool

**Расположение:** `core/application/tools/vector_books_tool.py`

**Назначение:** Универсальный инструмент для работы с книгами.

#### Capabilities

##### search

Семантический поиск по текстам книг.

**Входные параметры:**
```python
{
    "query": str,           # Текстовый запрос
    "top_k": int = 10,      # Количество результатов
    "min_score": float = 0.5,  # Минимальный порог
    "filters": dict = None  # Фильтры по метаданным
}
```

**Выходные данные:**
```python
{
    "results": [
        {
            "chunk_id": str,
            "document_id": str,
            "book_id": int,
            "chapter": int,
            "score": float,
            "content": str,
            "metadata": dict
        }
    ],
    "total_found": int
}
```

**Пример:**
```python
result = await agent.use_tool(
    "vector_books_tool",
    capability="search",
    query="Евгений Онегин",
    top_k=10
)
```

---

##### get_document

Получение полного текста книги из SQL.

**Входные параметры:**
```python
{
    "document_id": str  # ID документа (например, "book_1")
}
```

**Выходные данные:**
```python
{
    "book_id": int,
    "chapters": [
        {"chapter": int, "content": str}
    ]
}
```

**Пример:**
```python
result = await agent.use_tool(
    "vector_books_tool",
    capability="get_document",
    document_id="book_1"
)
```

---

##### analyze

LLM анализ контента (герои, темы, классификация).

**Входные параметры:**
```python
{
    "entity_id": str,        # ID сущности
    "analysis_type": str,    # Тип анализа (character/theme/category)
    "prompt": str,           # Промпт для LLM
    "force_refresh": bool = False  # Игнорировать кэш
}
```

**Выходные данные:**
```python
{
    "entity_id": str,
    "analysis_type": str,
    "result": dict,          # Результаты анализа
    "confidence": float,     # Уверенность (0-1)
    "reasoning": str,        # Обоснование
    "analyzed_at": str       # ISO datetime
}
```

**Пример:**
```python
result = await agent.use_tool(
    "vector_books_tool",
    capability="analyze",
    entity_id="book_1",
    analysis_type="character",
    prompt="Кто главный герой?"
)
```

---

##### query

SQL запрос к базе книг.

**Входные параметры:**
```python
{
    "sql": str,              # SQL запрос
    "parameters": tuple = None  # Параметры запроса
}
```

**Выходные данные:**
```python
{
    "data": list  # Результаты запроса
}
```

**Пример:**
```python
result = await agent.use_tool(
    "vector_books_tool",
    capability="query",
    sql="SELECT * FROM books WHERE author_id = ?",
    parameters=(1,)
)
```

---

### 2. DocumentIndexingService

**Расположение:** `core/application/services/document_indexing_service.py`

**Назначение:** Сервис индексации документов.

#### Методы

##### index_book

Индексация книги.

**Входные параметры:**
```python
{
    "book_id": int  # ID книги
}
```

**Выходные данные:**
```python
{
    "book_id": int,
    "chunks_indexed": int,
    "vectors_added": int
}
```

**Пример:**
```python
from core.application.services.document_indexing_service import DocumentIndexingService

service = DocumentIndexingService(sql, faiss, embedding, chunking)
result = await service.index_book(book_id=1)
```

---

##### reindex_book

Переиндексация книги (удаление + добавление).

**Входные параметры:**
```python
{
    "book_id": int
}
```

**Выходные данные:**
```python
{
    "book_id": int,
    "deleted": int,
    "indexed": int
}
```

---

##### delete_book

Удаление книги из индекса.

**Входные параметры:**
```python
{
    "book_id": int
}
```

**Выходные данные:**
```python
{
    "book_id": int,
    "deleted": int
}
```

---

##### index_all_books

Индексация всех книг.

**Выходные данные:**
```python
[
    {"book_id": int, "chunks_indexed": int, "vectors_added": int},
    ...
]
```

---

### 3. AnalysisCache

**Расположение:** `core/infrastructure/cache/analysis_cache.py`

**Назначение:** Кэш результатов LLM анализа.

#### Методы

##### get

Получение из кэша.

**Входные параметры:**
```python
{
    "cache_key": str  # Ключ кэша
}
```

**Выходные данные:**
```python
dict | None  # Данные или None
```

---

##### set

Сохранение в кэш.

**Входные параметры:**
```python
{
    "cache_key": str,
    "value": dict,
    "ttl_hours": int = 168  # 7 дней
}
```

---

##### delete

Удаление из кэша.

**Входные параметры:**
```python
{
    "cache_key": str
}
```

**Выходные данные:**
```python
bool  # True если удалено
```

---

##### invalidate_by_prefix

Инвалидация по префиксу.

**Входные параметры:**
```python
{
    "prefix": str  # Префикс ключей
}
```

**Выходные данные:**
```python
int  # Количество удалённых
```

---

## 📊 Модели данных

### VectorSearchResult

```python
{
    "id": str,
    "document_id": str,
    "chunk_id": str | None,
    "score": float,  # 0-1
    "content": str,
    "metadata": dict,
    "source": str
}
```

### VectorQuery

```python
{
    "query": str | None,
    "vector": list[float] | None,
    "top_k": int,  # 1-100
    "min_score": float,  # 0-1
    "filters": dict | None,
    "offset": int
}
```

### AnalysisResult

```python
{
    "entity_id": str,
    "analysis_type": str,
    "result": dict,
    "confidence": float,  # 0-1
    "reasoning": str | None,
    "analyzed_at": str  # ISO datetime
}
```

---

## 🔗 Интеграция

### С другими инструментами

```python
# Пример использования с другими инструментами
from core.application.tools.vector_books_tool import VectorBooksTool
from core.application.services.document_indexing_service import DocumentIndexingService

# Индексация
await indexing_service.index_book(book_id=1)

# Поиск
results = await vector_books_tool.execute(
    capability="search",
    query="текст запроса"
)

# Анализ
analysis = await vector_books_tool.execute(
    capability="analyze",
    entity_id="book_1",
    analysis_type="character",
    prompt="Кто главный герой?"
)
```

---

*Документ создан: 2026-02-19*  
*Версия: 1.0.0*

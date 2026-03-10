# 📚 Интеграция с базой книг (SQL + Vector)

**Версия:** 1.0.0
**Дата:** 2026-02-19
**Статус:** ✅ Утверждено

---

## 📋 Обзор

Этот документ описывает интеграцию существующей SQL базы данных с авторами, книгами и текстами с системой векторного поиска.

---

## 🎯 Архитектурное решение

### ADR-011: Гибридный поиск (Vector + SQL)

| Параметр | Решение |
|----------|---------|
| **Семантический поиск** | Vector DB (FAISS) |
| **Полный текст книги** | SQL DB (PostgreSQL) |
| **Связь между БД** | book_id, author_id в метаданных |
| **Синхронизация** | Event-driven (при добавлении книги) |

**Обоснование:**
1. ✅ Векторный поиск для семантического поиска по текстам
2. ✅ SQL для получения полного текста книги
3. ✅ Ссылки через book_id/author_id
4. ✅ Не дублируем полный текст в векторной БД

---

## 📊 Структура данных

### SQL База (существующая)

```sql
-- Авторы
CREATE TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    birth_date DATE,
    nationality TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Книги
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author_id INTEGER REFERENCES authors(id),
    year INTEGER,
    genre TEXT,
    language TEXT DEFAULT 'ru',
    publisher TEXT,
    isbn TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP  -- Когда добавлена в векторный индекс
);

-- Тексты книг (по главам)
CREATE TABLE book_texts (
    id INTEGER PRIMARY KEY,
    book_id INTEGER REFERENCES books(id),
    chapter INTEGER NOT NULL,
    title TEXT,  -- Название главы
    content TEXT NOT NULL,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter)
);

-- Индексы для производительности
CREATE INDEX idx_books_author ON books(author_id);
CREATE INDEX idx_book_texts_book ON book_texts(book_id);
CREATE INDEX idx_books_year ON books(year);
CREATE INDEX idx_books_genre ON books(genre);
```

---

### Vector База (новая)

```
data/vector/
├── books_index.faiss          ← Индекс чанков текстов книг
├── books_metadata.json        ← Метаданные чанков (ссылки на SQL)
└── config.json
```

---

## 🔗 Структура метаданных чанка

### Полная схема

```json
{
  "chunk_id": "book_chunk_0001_0000",
  "document_id": "book_0001",
  "source": "books",
  "content": "текст чанка (500 символов)...",
  "vector_id": 0,

  "book_metadata": {
    "book_id": 1,
    "book_title": "Война и мир",
    "author_id": 1,
    "author_name": "Лев Толстой",
    "year": 1869,
    "genre": "roman",
    "language": "ru",
    "publisher": "Азбука",
    "isbn": "978-5-389-12345-6"
  },

  "chunk_metadata": {
    "chapter": 1,
    "chapter_title": "Глава 1",
    "chunk_index": 0,
    "total_chunks": 150,
    "chunk_size": 500,
    "chunk_overlap": 50,
    "word_count": 85
  },

  "sql_reference": {
    "enabled": true,
    "database": "books_db",
    "table": "book_texts",
    "text_column": "content",
    "join_columns": {
      "book_id": 1,
      "chapter": 1
    },
    "full_text_query": "SELECT content FROM book_texts WHERE book_id = ? ORDER BY chapter"
  },

  "indexed_at": "2026-02-19T10:00:00Z",
  "content_hash": "sha256:abc123..."
}
```

### Минимальная схема (для экономии места)

```json
{
  "chunk_id": "book_chunk_0001_0000",
  "document_id": "book_0001",
  "source": "books",
  "content": "текст чанка...",
  "vector_id": 0,
  "book_id": 1,
  "author_id": 1,
  "chapter": 1,
  "chunk_index": 0
}
```

**Примечание:** Полные метаданные книг хранятся в SQL, в векторной БД только ссылки.

---

## 🔍 Сценарии использования

### Сценарий 1: Семантический поиск по текстам книг

**Запрос пользователя:**
```
"найди книги о любви и войне"
```

**Выполнение:**
```python
# 1. Векторный поиск
results = await agent.use_tool(
    "vector_books_tool",
    query="любовь война роман",
    top_k=10
)

# 2. Результаты
[
  {
    "chunk_id": "book_chunk_0001_0025",
    "score": 0.92,
    "content": "текст чанка с описанием сцены...",
    "book_id": 1,
    "book_title": "Война и мир",
    "author_name": "Лев Толстой",
    "chapter": 5,
    "chunk_index": 25
  },
  {
    "chunk_id": "book_chunk_0002_0010",
    "score": 0.87,
    "content": "текст чанка...",
    "book_id": 2,
    "book_title": "Анна Каренина",
    "author_name": "Лев Толстой",
    "chapter": 3,
    "chunk_index": 10
  }
]
```

---

### Сценарий 2: Получение полного текста книги

**Запрос пользователя:**
```
"дай полный текст книги Война и мир"
```

**Выполнение:**
```python
# 1. SQL запрос (через sql_tool)
result = await agent.use_tool(
    "sql_tool",
    query="""
        SELECT bt.content, bt.chapter, bt.title as chapter_title
        FROM book_texts bt
        JOIN books b ON bt.book_id = b.id
        WHERE b.id = 1
        ORDER BY bt.chapter
    """
)

# 2. Результаты
{
  "book_id": 1,
  "book_title": "Война и мир",
  "author_name": "Лев Толстой",
  "chapters": [
    {
      "chapter": 1,
      "chapter_title": "Глава 1",
      "content": "полный текст главы 1..."
    },
    {
      "chapter": 2,
      "chapter_title": "Глава 2",
      "content": "полный текст главы 2..."
    }
  ]
}
```

---

### Сценарий 3: Гибридный поиск (вектор + SQL фильтр)

**Запрос пользователя:**
```
"найди у Толстого про любовь"
```

**Выполнение:**
```python
# Вариант 1: Векторный поиск с фильтром по author_id
results = await agent.use_tool(
    "vector_books_tool",
    query="любовь",
    top_k=10,
    filters={"author_id": [1]}  # ← Фильтр по автору
)

# Вариант 2: SQL → Векторный пост-фильтр
# 1. SQL: получаем book_id для автора
books = await sql_db.fetch(
    "SELECT id FROM books WHERE author_id = ?",
    (1,)
)
book_ids = [b["id"] for b in books]

# 2. Vector: поиск по книгам автора
results = await agent.use_tool(
    "vector_books_tool",
    query="любовь",
    top_k=10,
    filters={"book_id": book_ids}
)
```

---

### Сценарий 4: Поиск с переходом к полному тексту

**Запрос пользователя:**
```
"найди сцену бала в Войне и мир и покажи полный текст"
```

**Выполнение:**
```python
# 1. Векторный поиск сцены
chunk_results = await agent.use_tool(
    "vector_books_tool",
    query="бал Наташа Ростова",
    top_k=3
)

# 2. Получаем book_id из результатов
book_id = chunk_results[0]["book_id"]  # 1

# 3. SQL: получаем полный текст книги
full_text = await agent.use_tool(
    "sql_tool",
    query="""
        SELECT content, chapter
        FROM book_texts
        WHERE book_id = ?
        ORDER BY chapter
    """,
    parameters=(book_id,)
)

# 4. Возвращаем чанк + полный текст
{
  "chunk_results": chunk_results,
  "full_book_text": full_text
}
```

---

## 🛠️ VectorBooksTool

### Манифест

```yaml
# data/manifests/tools/vector_books_tool/manifest.yaml

name: "vector_books_tool"
version: "1.0.0"
description: "Семантический поиск по текстам книг с интеграцией SQL"

capabilities:
  - name: "search"
    description: "Поиск по текстам книг (векторный)"
    input_contract: "vector_books.search_input_v1.0.0"
    output_contract: "vector_books.search_output_v1.0.0"

  - name: "get_book_text"
    description: "Получение полного текста книги (SQL)"
    input_contract: "vector_books.get_book_text_input_v1.0.0"
    output_contract: "vector_books.get_book_text_output_v1.0.0"

  - name: "get_chapter_text"
    description: "Получение текста главы (SQL)"
    input_contract: "vector_books.get_chapter_text_input_v1.0.0"
    output_contract: "vector_books.get_chapter_text_output_v1.0.0"

dependencies:
  infrastructure:
    - "faiss_provider_books"
    - "sql_provider"
  services:
    - "book_indexing_service"

config:
  default_top_k: 10
  max_top_k: 50
  chunk_size: 500
  chunk_overlap: 50
```

---

### Промпт для навыка

```
Ты — инструмент семантического поиска по текстам книг.

Используй этот навык для:
- Поиска сцен, цитат, описаний в текстах книг
- Поиска по смыслу (не точное совпадение слов)
- Поиска с фильтрами по автору, жанру, году

Параметры:
- query: текст запроса (обязательно)
- top_k: количество результатов (по умолчанию 10)
- filters: опциональные фильтры
  - author_id: фильтр по автору
  - book_id: фильтр по книге
  - genre: фильтр по жанру
  - year_from, year_to: фильтр по году

Для получения полного текста книги используй capability "get_book_text".
Для получения текста главы используй capability "get_chapter_text".

Примеры:
- search(query="любовь война", top_k=10)
- search(query="бал", filters={"author_id": [1]})
- get_book_text(book_id=1)
- get_chapter_text(book_id=1, chapter=5)
```

---

## 🔄 Синхронизация SQL ↔ Vector

### Добавление книги в векторный индекс

```python
# core/application/services/book_indexing_service.py

class BookIndexingService:
    """Сервис индексации книг в векторном индексе."""

    def __init__(
        self,
        sql_provider: SQLProvider,
        faiss_provider: FAISSProvider,
        embedding_provider: EmbeddingProvider,
        chunking_service: ChunkingService
    ):
        self.sql = sql_provider
        self.faiss = faiss_provider
        self.embedding = embedding_provider
        self.chunking = chunking_service

    async def index_book(self, book_id: int) -> IndexResult:
        """Добавление книги в векторный индекс."""

        # 1. Получаем данные книги из SQL
        book_data = await self.sql.fetch("""
            SELECT
                b.id as book_id,
                b.title,
                b.author_id,
                b.year,
                b.genre,
                b.language,
                a.name as author_name,
                a.nationality
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE b.id = ?
        """, (book_id,))

        if not book_data:
            raise ValueError(f"Book {book_id} not found")

        book = book_data[0]

        # 2. Получаем тексты глав
        chapter_texts = await self.sql.fetch("""
            SELECT chapter, title as chapter_title, content
            FROM book_texts
            WHERE book_id = ?
            ORDER BY chapter
        """, (book_id,))

        # 3. Разбиваем на чанки
        all_chunks = []
        for chapter in chapter_texts:
            chapter_chunks = await self.chunking.split(
                content=chapter["content"],
                chapter=chapter["chapter"],
                chapter_title=chapter["chapter_title"]
            )
            all_chunks.extend(chapter_chunks)

        # 4. Генерируем эмбеддинги
        vectors = await self.embedding.generate(
            [chunk.content for chunk in all_chunks]
        )

        # 5. Формируем метаданные
        metadata = []
        for i, (chunk, vector) in enumerate(zip(all_chunks, vectors)):
            metadata.append({
                "chunk_id": f"book_chunk_{book_id:04d}_{i:04d}",
                "document_id": f"book_{book_id:04d}",
                "source": "books",
                "content": chunk.content,
                "book_id": book["book_id"],
                "book_title": book["title"],
                "author_id": book["author_id"],
                "author_name": book["author_name"],
                "year": book["year"],
                "genre": book["genre"],
                "language": book["language"],
                "chapter": chunk.chapter,
                "chapter_title": chunk.chapter_title,
                "chunk_index": i,
                "total_chunks": len(all_chunks),
                "sql_reference": {
                    "enabled": True,
                    "table": "book_texts",
                    "text_column": "content",
                    "join_columns": {
                        "book_id": book_id,
                        "chapter": chunk.chapter
                    }
                }
            })

        # 6. Добавляем в FAISS
        await self.faiss.add(vectors, metadata)

        # 7. Обновляем метку индексации в SQL
        await self.sql.execute("""
            UPDATE books SET indexed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (book_id,))

        return IndexResult(
            book_id=book_id,
            chunks_indexed=len(all_chunks),
            vectors_added=len(vectors)
        )

    async def reindex_book(self, book_id: int) -> IndexResult:
        """Переиндексация книги (удаление + добавление)."""

        # 1. Удаляем старые чанки
        await self.faiss.delete_by_filter({"book_id": book_id})

        # 2. Добавляем заново
        return await self.index_book(book_id)

    async def index_all_books(self) -> List[IndexResult]:
        """Индексация всех книг."""

        # Получаем все книги
        books = await self.sql.fetch("SELECT id FROM books")

        results = []
        for book in books:
            try:
                result = await self.index_book(book["id"])
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to index book {book['id']}: {e}")

        return results
```

---

### Event-driven синхронизация

```python
# core/infrastructure/event_bus/vector_event_handler.py

class VectorBookEventHandler:
    """Обработчик событий для синхронизации книг."""

    def __init__(self, indexing_service: BookIndexingService):
        self.indexing_service = indexing_service

    @subscribe_to_event("BookCreated")
    async def on_book_created(self, event: BookCreatedEvent):
        """Новая книга создана → добавить в векторный индекс."""
        await self.indexing_service.index_book(event.book_id)

    @subscribe_to_event("BookUpdated")
    async def on_book_updated(self, event: BookUpdatedEvent):
        """Книга обновлена → переиндексировать."""
        if event.text_changed:
            await self.indexing_service.reindex_book(event.book_id)

    @subscribe_to_event("BookDeleted")
    async def on_book_deleted(self, event: BookDeletedEvent):
        """Книга удалена → удалить из векторного индекса."""
        await self.faiss_provider_books.delete_by_filter(
            {"book_id": event.book_id}
        )
```

---

## 📊 Метрики

### Метрики индексации

```python
{
    "books_indexing": {
        "total_books": 150,
        "indexed_books": 145,
        "pending_books": 5,
        "total_chunks": 7500,
        "total_vectors": 7500,
        "index_size_mb": 75,
        "last_indexing": "2026-02-19T10:00:00Z"
    }
}
```

### Метрики поиска

```python
{
    "vector_books_tool": {
        "search_count_24h": 200,
        "avg_search_latency_ms": 55,
        "p95_latency_ms": 90,
        "avg_results_count": 8.5,
        "get_book_text_count_24h": 50
    }
}
```

---

## 📁 Обновлённая структура файлов

```
data/vector/
├── knowledge_index.faiss
├── knowledge_metadata.json
├── history_index.faiss
├── history_metadata.json
├── docs_index.faiss
├── docs_metadata.json
├── books_index.faiss          ← Новый
├── books_metadata.json        ← Новый
└── config.json

data/manifests/tools/
├── vector_knowledge_tool/
├── vector_history_tool/
├── vector_docs_tool/
└── vector_books_tool/         ← Новый
    └── manifest.yaml

core/application/services/
├── vector_search_service.py
├── book_indexing_service.py   ← Новый
└── ...

core/application/tools/
├── vector_knowledge_tool.py
├── vector_history_tool.py
├── vector_docs_tool.py
└── vector_books_tool.py       ← Новый
```

---

## 🎯 Критерии приёмки

### Функциональные:
```
✅ Семантический поиск по текстам книг работает
✅ Получение полного текста книги через SQL работает
✅ Гибридный поиск (вектор + SQL фильтр) работает
✅ Синхронизация SQL ↔ Vector работает
✅ Event-driven обновления работают
```

### Нефункциональные:
```
✅ Время поиска p95 < 1000ms
✅ Индексация книги (100 глав) < 60 сек
✅ Метаданные чанка < 1KB
```

---

*Документ создан: 2026-02-19*
*Версия: 1.0.1*
*Статус: ✅ Утверждено*

---

## 📝 История изменений

| Дата | Версия | Изменение |
|------|--------|-----------|
| 2026-02-19 | 1.0.0 | Initial document |
| 2026-02-19 | 1.0.1 | Упрощено: VectorBooksTool содержит всю логику (без BookAnalysisTool) |

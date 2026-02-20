# 🔄 Жизненный цикл векторной БД

**Версия:** 1.0.0  
**Дата:** 2026-02-19  
**Статус:** ✅ Утверждено

---

## 📋 Обзор

Этот документ описывает полный процесс создания, обновления и поддержания векторной БД в актуальном состоянии.

---

## 🏗️ Архитектура хранения

### Где что хранится

| Данные | Хранение | Формат | Обновление |
|--------|----------|--------|------------|
| Исходный текст | SQL (`book_texts.content`) | TEXT | При изменении книги |
| Векторы | FAISS (`books_index.faiss`) | binary (384 dim) | При индексации |
| Метаданные | JSON (`books_metadata.json`) | JSON | При индексации |
| Статус индексации | SQL (`books.indexed_at`) | TIMESTAMP | При индексации |

---

## 🔄 Жизненный цикл

### 1. Создание (первичная индексация)

**Когда:** Первый запуск системы

**Процесс:**
```
┌─────────────────────────────────────────────────────────────┐
│  1. Получаем все книги из SQL                               │
│     SELECT id FROM books                                    │
│                                                             │
│  2. Для каждой книги:                                       │
│     ┌────────────────────────────────────────────────────┐ │
│     │ 2.1. Получаем текст                                │ │
│     │      SELECT chapter, content FROM book_texts       │ │
│     │      WHERE book_id = ?                             │ │
│     │                                                    │ │
│     │ 2.2. Разбиваем на чанки                            │ │
│     │      chunks = chunking.split(content)              │ │
│     │                                                    │ │
│     │ 2.3. Генерируем векторы                            │ │
│     │      vectors = embedding.generate(chunks)          │ │
│     │                                                    │ │
│     │ 2.4. Добавляем в FAISS                             │ │
│     │      faiss.add(vectors, metadata)                  │ │
│     └────────────────────────────────────────────────────┘ │
│                                                             │
│  3. Сохраняем индекс на диск                                │
│     faiss.save("data/vector/books_index.faiss")             │
│                                                             │
│  4. Помечаем книгу как проиндексированную                   │
│     UPDATE books SET indexed_at = NOW() WHERE id = ?        │
└─────────────────────────────────────────────────────────────┘
```

**Код:**
```python
# core/application/services/document_indexing_service.py

class DocumentIndexingService:
    """Сервис индексации документов."""
    
    async def initial_indexing(self):
        """Первичная индексация всех книг."""
        
        # 1. Получаем все книги
        books = await self.sql.fetch("SELECT id FROM books")
        
        logger.info(f"Starting initial indexing for {len(books)} books")
        
        # 2. Индексируем каждую
        for book in books:
            try:
                await self.index_book(book["id"])
                logger.info(f"Indexed book {book['id']}")
            except Exception as e:
                logger.error(f"Failed to index book {book['id']}: {e}")
        
        # 3. Сохраняем индекс
        await self.faiss.save()
        
        logger.info("Initial indexing completed")
    
    async def index_book(self, book_id: int):
        """Индексация одной книги."""
        
        # 1. Получаем текст из SQL
        chapters = await self.sql.fetch("""
            SELECT chapter, content
            FROM book_texts
            WHERE book_id = ?
            ORDER BY chapter
        """, (book_id,))
        
        # 2. Разбиваем на чанки
        all_chunks = []
        for chapter in chapters:
            chunks = await self.chunking.split(
                content=chapter["content"],
                chapter=chapter["chapter"]
            )
            all_chunks.extend(chunks)
        
        # 3. Генерируем векторы
        vectors = await self.embedding.generate(
            [chunk.content for chunk in all_chunks]
        )
        
        # 4. Формируем метаданные
        metadata = []
        for i, chunk in enumerate(all_chunks):
            metadata.append({
                "chunk_id": f"book_{book_id}_chunk_{i}",
                "document_id": f"book_{book_id}",
                "book_id": book_id,
                "chapter": chunk.chapter,
                "chunk_index": i
            })
        
        # 5. Добавляем в FAISS
        await self.faiss.add(vectors, metadata)
        
        # 6. Помечаем как проиндексированную
        await self.sql.execute("""
            UPDATE books SET indexed_at = NOW()
            WHERE id = ?
        """, (book_id,))
```

---

### 2. Обновление (триггеры)

#### Триггер 1: Добавлена новая книга

**Событие:** `BookCreated`

**Процесс:**
```python
# core/infrastructure/event_bus/vector_event_handler.py

class VectorEventHandler:
    """Обработчик событий для векторной БД."""
    
    @subscribe_to_event("BookCreated")
    async def on_book_created(self, event: BookCreatedEvent):
        """Новая книга → индексировать."""
        
        logger.info(f"New book created: {event.book_id}")
        
        # Индексируем новую книгу
        await self.indexing_service.index_book(event.book_id)
        
        # Сохраняем индекс
        await self.faiss_provider.save()
```

---

#### Триггер 2: Обновлён текст книги

**Событие:** `BookUpdated`

**Процесс:**
```python
class VectorEventHandler:
    
    @subscribe_to_event("BookUpdated")
    async def on_book_updated(self, event: BookUpdatedEvent):
        """Книга обновлена → переиндексировать."""
        
        if not event.text_changed:
            return  # Текст не менялся, не нужно переиндексировать
        
        logger.info(f"Book updated: {event.book_id}")
        
        # Переиндексируем книгу
        await self.indexing_service.reindex_book(event.book_id)
        
        # Сохраняем индекс
        await self.faiss_provider.save()
```

---

#### Триггер 3: Удалена книга

**Событие:** `BookDeleted`

**Процесс:**
```python
class VectorEventHandler:
    
    @subscribe_to_event("BookDeleted")
    async def on_book_deleted(self, event: BookDeletedEvent):
        """Книга удалена → удалить из индекса."""
        
        logger.info(f"Book deleted: {event.book_id}")
        
        # Удаляем из FAISS
        await self.faiss_provider.delete_by_filter({
            "book_id": event.book_id
        })
        
        # Сохраняем индекс
        await self.faiss_provider.save()
```

---

### 3. Плановая проверка (cron)

**Когда:** Каждые 24 часа (настраиваемое)

**Процесс:**
```
┌─────────────────────────────────────────────────────────────┐
│  1. Находим устаревшие книги                                │
│     SELECT id FROM books                                    │
│     WHERE updated_at > indexed_at                           │
│        OR indexed_at IS NULL                                │
│                                                             │
│  2. Для каждой устаревшей:                                  │
│     - Переиндексировать                                     │
│                                                             │
│  3. Оптимизируем индекс                                     │
│     faiss.optimize()                                        │
│                                                             │
│  4. Логируем результат                                      │
│     - Количество переиндексированных                        │
│     - Размер индекса                                        │
│     - Время выполнения                                      │
└─────────────────────────────────────────────────────────────┘
```

**Код:**
```python
# core/infrastructure/scheduler/vector_indexing_scheduler.py

class VectorIndexingScheduler:
    """Плановая переиндексация."""
    
    def __init__(self, interval_hours: int = 24):
        self.interval_hours = interval_hours
    
    async def start(self):
        """Запуск планировщика."""
        logger.info(f"Starting vector indexing scheduler (interval={self.interval_hours}h)")
        
        while True:
            try:
                await self.check_and_reindex()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            await asyncio.sleep(self.interval_hours * 3600)
    
    async def check_and_reindex(self):
        """Проверка и переиндексация."""
        
        start_time = time.time()
        
        # 1. Находим устаревшие книги
        stale_books = await self.sql.fetch("""
            SELECT id, title, indexed_at, updated_at
            FROM books
            WHERE updated_at > indexed_at
               OR indexed_at IS NULL
        """)
        
        if not stale_books:
            logger.info("No stale books found")
            return
        
        logger.info(f"Found {len(stale_books)} stale books")
        
        # 2. Переиндексируем
        reindexed = 0
        for book in stale_books:
            try:
                await self.indexing_service.reindex_book(book["id"])
                reindexed += 1
                logger.info(f"Reindexed book {book['id']}: {book['title']}")
            except Exception as e:
                logger.error(f"Failed to reindex book {book['id']}: {e}")
        
        # 3. Сохраняем индекс
        await self.faiss_provider.save()
        
        # 4. Оптимизируем
        await self.faiss_provider.optimize()
        
        # 5. Логируем
        elapsed = time.time() - start_time
        logger.info(
            f"Reindexing completed: {reindexed}/{len(stale_books)} books, "
            f"elapsed={elapsed:.2f}s"
        )
```

---

### 4. Стратегии переиндексации

#### Стратегия А: Полная переиндексация

```python
async def reindex_book(self, book_id: int):
    """Полная переиндексация книги."""
    
    logger.info(f"Full reindex of book {book_id}")
    
    # 1. Удаляем старые векторы
    await self.faiss.delete_by_filter({"book_id": book_id})
    
    # 2. Индексируем заново
    await self.index_book(book_id)
```

**Когда использовать:**
- ✅ Книга полностью переписана
- ✅ Изменено > 50% текста
- ✅ Простая реализация

---

#### Стратегия Б: Инкрементальное обновление

```python
async def update_chapters(self, book_id: int, chapter_numbers: List[int]):
    """Инкрементальное обновление (только указанные главы)."""
    
    logger.info(f"Incremental update of book {book_id}, chapters {chapter_numbers}")
    
    for chapter in chapter_numbers:
        # 1. Удаляем старые векторы для главы
        await self.faiss.delete_by_filter({
            "book_id": book_id,
            "chapter": chapter
        })
        
        # 2. Получаем новый текст
        chapter_data = await self.sql.fetch_one("""
            SELECT content FROM book_texts
            WHERE book_id = ? AND chapter = ?
        """, (book_id, chapter))
        
        # 3. Разбиваем на чанки
        chunks = await self.chunking.split(chapter_data["content"], chapter=chapter)
        
        # 4. Генерируем векторы
        vectors = await self.embedding.generate([c.content for c in chunks])
        
        # 5. Добавляем в FAISS
        metadata = [{
            "chunk_id": f"book_{book_id}_chapter_{chapter}_chunk_{i}",
            "document_id": f"book_{book_id}",
            "book_id": book_id,
            "chapter": chapter,
            "chunk_index": i
        } for i in range(len(chunks))]
        
        await self.faiss.add(vectors, metadata)
```

**Когда использовать:**
- ✅ Изменено < 50% текста
- ✅ Известны изменённые главы
- ✅ Критична скорость обновления

---

## 📊 Мониторинг

### Метрики

```python
# core/infrastructure/metrics/vector_metrics.py

class VectorMetrics:
    """Метрики векторной БД."""
    
    async def get_index_stats(self) -> dict:
        """Статистика индекса."""
        return {
            "total_vectors": await self.faiss.count(),
            "total_books": await self.get_indexed_books_count(),
            "index_size_mb": await self.get_index_size_mb(),
            "last_indexing": await self.get_last_indexing_time(),
            "stale_books": await self.get_stale_books_count()
        }
    
    async def get_stale_books_count(self) -> int:
        """Количество книг, требующих переиндексации."""
        result = await self.sql.fetch_one("""
            SELECT COUNT(*) as count
            FROM books
            WHERE updated_at > indexed_at
               OR indexed_at IS NULL
        """)
        return result["count"]
    
    async def check_sync(self) -> dict:
        """Проверка синхронизации SQL ↔ FAISS."""
        
        # Книги в SQL
        sql_books = await self.sql.fetch("SELECT id FROM books")
        sql_ids = {b["id"] for b in sql_books}
        
        # Книги в FAISS
        faiss_books = await self.faiss.get_unique_book_ids()
        faiss_ids = set(faiss_books)
        
        return {
            "in_sql_only": sql_ids - faiss_ids,  # Есть в SQL, нет в FAISS
            "in_faiss_only": faiss_ids - sql_ids,  # Есть в FAISS, нет в SQL
            "synchronized": len(sql_ids & faiss_ids)  # Везде
        }
```

---

### Проверка рассинхронизации

```python
async def detect_desync() -> list:
    """Обнаружение рассинхронизации SQL ↔ FAISS."""
    
    issues = []
    
    # 1. Книги в SQL но не в FAISS
    missing_in_faiss = await sql.fetch("""
        SELECT b.id, b.title
        FROM books b
        LEFT JOIN book_texts bt ON bt.book_id = b.id
        WHERE b.indexed_at IS NULL
    """)
    
    if missing_in_faiss:
        issues.append({
            "type": "missing_in_faiss",
            "books": missing_in_faiss
        })
    
    # 2. Книги в FAISS но не в SQL
    faiss_book_ids = await faiss.get_unique_book_ids()
    sql_book_ids = {b["id"] for b in await sql.fetch("SELECT id FROM books")}
    
    orphaned = faiss_book_ids - sql_book_ids
    if orphaned:
        issues.append({
            "type": "orphaned_in_faiss",
            "book_ids": list(orphaned)
        })
    
    # 3. Устаревшие индексы
    stale = await sql.fetch("""
        SELECT id, title, indexed_at, updated_at
        FROM books
        WHERE updated_at > indexed_at
    """)
    
    if stale:
        issues.append({
            "type": "stale_index",
            "books": stale
        })
    
    return issues
```

---

## 📋 Чек-лист

### Первичная настройка

```
□ SQL таблица books имеет поле indexed_at
□ SQL таблица books имеет поле updated_at
□ Создан DocumentIndexingService
□ Создан VectorEventHandler
□ Создан VectorIndexingScheduler
□ Настроены триггеры событий
□ Настроен планировщик (cron)
□ Настроен мониторинг
```

### Процессы

```
□ Первичная индексация работает
□ Индексация новой книги работает
□ Переиндексация обновлённой книги работает
□ Удаление из индекса работает
□ Плановая проверка работает
□ Мониторинг рассинхронизации работает
```

---

*Документ создан: 2026-02-19*  
*Версия: 1.0.0*  
*Статус: ✅ Утверждено*

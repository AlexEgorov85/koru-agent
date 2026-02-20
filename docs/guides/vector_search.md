# 📖 Vector Search Руководство

**Версия:** 1.0.0  
**Дата:** 2026-02-19

---

## 📋 Содержание

1. [Введение](#введение)
2. [Быстрый старт](#быстрый-старт)
3. [Настройка](#настройка)
4. [Использование](#использование)
5. [Лучшие практики](#лучшие-практики)
6. [Troubleshooting](#troubleshooting)

---

## Введение

Vector Search — система семантического поиска по документам с использованием векторных эмбеддингов.

**Возможности:**
- 🔍 Семантический поиск по тексту
- 📚 Интеграция с базой книг (SQL + Vector)
- 🧠 LLM анализ контента
- 💾 Кэширование результатов
- ⚡ Быстрый поиск (< 1 сек)

---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install faiss-cpu
pip install sentence-transformers
```

### 2. Базовая настройка

Добавьте в `registry.yaml`:

```yaml
vector_search:
  enabled: true
  indexes:
    knowledge: "knowledge_index.faiss"
    history: "history_index.faiss"
    docs: "docs_index.faiss"
    books: "books_index.faiss"
  embedding:
    model_name: "all-MiniLM-L6-v2"
    device: "cpu"
  chunking:
    chunk_size: 500
    chunk_overlap: 50
```

### 3. Индексация книг

```python
from core.application.services.document_indexing_service import DocumentIndexingService

service = DocumentIndexingService(sql, faiss, embedding, chunking)
await service.index_book(book_id=1)
```

### 4. Поиск

```python
from core.application.tools.vector_books_tool import VectorBooksTool

tool = VectorBooksTool(faiss, sql, embedding, llm, cache, chunking)

result = await tool.execute(
    capability="search",
    query="Евгений Онегин",
    top_k=10
)
```

---

## Настройка

### Конфигурация FAISS

```yaml
vector_search:
  faiss:
    index_type: "Flat"  # Flat, IVF, HNSW
    nlist: 100          # Для IVF
    nprobe: 10          # Для IVF
    metric: "IP"        # IP (косинусное), L2
```

**Рекомендации:**
- **Flat:** Для < 10K векторов
- **IVF:** Для 10K-1M векторов
- **HNSW:** Для максимальной скорости

---

### Конфигурация Embedding

```yaml
vector_search:
  embedding:
    model_name: "all-MiniLM-L6-v2"
    dimension: 384
    device: "cpu"  # cpu, cuda
    batch_size: 32
```

**Популярные модели:**
- `all-MiniLM-L6-v2` — быстро, 384 dim
- `all-mpnet-base-v2` — качественно, 768 dim
- `paraph-multilingual` — мультиязычная

---

### Конфигурация Chunking

```yaml
vector_search:
  chunking:
    strategy: "text"  # text, semantic, hybrid
    chunk_size: 500
    chunk_overlap: 50
    min_chunk_size: 100
```

**Рекомендации:**
- **chunk_size:** 500 для книг, 200 для статей
- **chunk_overlap:** 10% от chunk_size
- **min_chunk_size:** 100 символов

---

## Использование

### Сценарий 1: Поиск по книгам

```python
# Поиск
result = await tool.execute(
    capability="search",
    query="найди сцену бала",
    top_k=10,
    filters={"book_id": [1, 2]}
)

# Получение полного текста
text = await tool.execute(
    capability="get_document",
    document_id="book_1"
)
```

---

### Сценарий 2: Анализ героя

```python
# Анализ
analysis = await tool.execute(
    capability="analyze",
    entity_id="book_1",
    analysis_type="character",
    prompt="Кто главный герой? Какой у него пол?"
)

print(analysis["result"]["main_character"])
print(analysis["result"]["gender"])
print(f"Уверенность: {analysis['confidence']}")
```

---

### Сценарий 3: Массовая индексация

```python
from core.application.services.document_indexing_service import DocumentIndexingService

service = DocumentIndexingService(sql, faiss, embedding, chunking)

# Индексация всех книг
results = await service.index_all_books()

for result in results:
    if "error" in result:
        print(f"Ошибка: {result['error']}")
    else:
        print(f"Книга {result['book_id']}: {result['chunks_indexed']} чанков")
```

---

### Сценарий 4: SQL запрос

```python
# Получение книг автора
books = await tool.execute(
    capability="query",
    sql="SELECT * FROM books WHERE author_id = ?",
    parameters=(1,)
)

for book in books["data"]:
    print(f"{book['title']} ({book['year']})")
```

---

## Лучшие практики

### 1. Индексация

✅ **Делайте:**
- Индексируйте книги при добавлении
- Переиндексируйте при обновлении текста
- Используйте event-driven синхронизацию

❌ **Не делайте:**
- Не индексируйте дубликаты
- Не забывайте обновлять `indexed_at`

---

### 2. Поиск

✅ **Делайте:**
- Используйте фильтры для уточнения
- Настраивайте `min_score` для качества
- Кэшируйте частые запросы

❌ **Не делайте:**
- Не используйте top_k > 100
- Не игнорируйте `min_score`

---

### 3. LLM Анализ

✅ **Делайте:**
- Кэшируйте результаты (7 дней)
- Проверяйте `confidence`
- Используйте конкретные промпты

❌ **Не делайте:**
- Не анализируйте без кэша
- Не доверяйте низкой уверенности (< 0.8)

---

### 4. Производительность

✅ **Делайте:**
- Используйте IVF для больших индексов
- Батчите эмбеддинги (32-64)
- Мониторьте размер индекса

❌ **Не делайте:**
- Не храните > 1M векторов в одном индексе
- Не забывайте про оптимизацию

---

## Troubleshooting

### Проблема: Медленный поиск

**Причины:**
- Большой индекс (> 100K векторов)
- Flat индекс вместо IVF

**Решения:**
```yaml
faiss:
  index_type: "IVF"
  nlist: 1000  # Увеличить
  nprobe: 50   # Увеличить
```

---

### Проблема: Низкая точность

**Причины:**
- Неподходящая модель эмбеддингов
- Слишком большой chunk_size

**Решения:**
```yaml
embedding:
  model_name: "all-mpnet-base-v2"  # Более качественная

chunking:
  chunk_size: 300  # Уменьшить
```

---

### Проблема: Рассинхронизация SQL ↔ FAISS

**Причины:**
- Книга обновлена в SQL, но не в FAISS

**Решения:**
```python
# Переиндексация
await service.reindex_book(book_id=1)

# Проверка
stale = await sql.fetch("""
    SELECT id FROM books
    WHERE updated_at > indexed_at
""")
```

---

### Проблема: Кэш не работает

**Причины:**
- Неправильный путь к кэшу
- Проблемы с правами доступа

**Решения:**
```python
cache = AnalysisCache("data/cache/book_analysis")
# Проверить что директория существует
cache.storage_path.mkdir(parents=True, exist_ok=True)
```

---

## 📚 Дополнительные ресурсы

- [API Documentation](../api/vector_search_api.md)
- [Architecture Decisions](../vector_search/ARCHITECTURE_DECISIONS.md)
- [Examples](../../examples/vector_search_examples.py)

---

*Документ создан: 2026-02-19*  
*Версия: 1.0.0*

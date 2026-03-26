"""
Примеры использования Vector Search.

Запуск:
    python examples/vector_search_examples.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Пример 1: Базовый поиск
# ============================================================================

async def example_1_basic_search():
    """Базовый поиск по книгам."""
    
    print("\n" + "="*60)
    print("Пример 1: Базовый поиск")
    print("="*60)
    
    from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider
    from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
    from core.services.tools.vector_books_tool import VectorBooksTool
    
    # Mock провайдеры
    faiss = MockFAISSProvider(dimension=384)
    embedding = MockEmbeddingProvider(dimension=384)
    
    # Mock SQL
    class MockSQL:
        async def fetch(self, sql, params=None):
            return [{"id": 1, "title": "Евгений Онегин"}]
        async def execute(self, sql, params=None):
            return True
    
    # Mock LLM
    class MockLLM:
        async def generate_json(self, prompt):
            return {"result": {}, "confidence": 0.9, "reasoning": "test"}
    
    # Mock Cache
    class MockCache:
        async def get(self, key): return None
        async def set(self, key, value, ttl_hours=168): pass
    
    # Mock Chunking
    from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
    chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
    
    tool = VectorBooksTool(
        faiss_provider=faiss,
        sql_provider=MockSQL(),
        embedding_provider=embedding,
        llm_provider=MockLLM(),
        cache_service=MockCache(),
        chunking_strategy=chunking
    )
    
    # Индексация
    text = "Евгений Онегин — роман в стихах Пушкина."
    chunks = await chunking.split(text, document_id="book_1", metadata={"book_id": 1})
    vectors = await embedding.generate([c.content for c in chunks])
    metadata = [{"chunk_id": c.id, "book_id": 1, "content": c.content} for c in chunks]
    await faiss.add(vectors, metadata)
    
    # Поиск
    result = await tool.execute(
        capability="search",
        query="Пушкин роман",
        top_k=10
    )
    
    print(f"Найдено результатов: {result['total_found']}")
    for r in result.get("results", []):
        print(f"  - Score: {r['score']:.2f}, Book: {r['book_id']}")


# ============================================================================
# Пример 2: LLM Анализ героя
# ============================================================================

async def example_2_character_analysis():
    """Анализ главного героя книги."""
    
    print("\n" + "="*60)
    print("Пример 2: LLM Анализ героя")
    print("="*60)
    
    from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider
    from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
    from core.services.tools.vector_books_tool import VectorBooksTool
    
    # Mock провайдеры
    faiss = MockFAISSProvider(dimension=384)
    embedding = MockEmbeddingProvider(dimension=384)
    
    # Mock SQL
    class MockSQL:
        async def fetch(self, sql, params=None):
            return [{"chapter": 1, "content": "Евгений Онегин глава 1"}]
        async def execute(self, sql, params=None):
            return True
    
    # Mock LLM
    class MockLLM:
        async def generate_json(self, prompt):
            if "главный герой" in prompt.lower():
                return {
                    "result": {"main_character": "Евгений Онегин", "gender": "male"},
                    "confidence": 0.95,
                    "reasoning": "Имя в названии книги"
                }
            return {"result": {}, "confidence": 0.5, "reasoning": ""}
    
    # Mock Cache
    class MockCache:
        def __init__(self):
            self.cache = {}
        async def get(self, key):
            return self.cache.get(key)
        async def set(self, key, value, ttl_hours=168):
            self.cache[key] = value
    
    chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
    
    tool = VectorBooksTool(
        faiss_provider=faiss,
        sql_provider=MockSQL(),
        embedding_provider=embedding,
        llm_provider=MockLLM(),
        cache_service=MockCache(),
        chunking_strategy=chunking
    )
    
    # Анализ
    result = await tool.execute(
        capability="analyze",
        entity_id="book_1",
        analysis_type="character",
        prompt="Кто главный герой? Какой у него пол?"
    )
    
    print(f"Герой: {result['result'].get('main_character', 'N/A')}")
    print(f"Пол: {result['result'].get('gender', 'N/A')}")
    print(f"Уверенность: {result['confidence']:.2f}")
    print(f"Обоснование: {result.get('reasoning', 'N/A')}")


# ============================================================================
# Пример 3: Индексация книги
# ============================================================================

async def example_3_book_indexing():
    """Индексация книги."""
    
    print("\n" + "="*60)
    print("Пример 3: Индексация книги")
    print("="*60)
    
    from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
    from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
    from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider
    from core.services.document_indexing_service import DocumentIndexingService
    
    # Mock SQL
    class MockSQL:
        async def fetch(self, sql, params=None):
            if "book_texts" in sql:
                return [
                    {"chapter": 1, "content": "Глава 1 текст " * 10},
                    {"chapter": 2, "content": "Глава 2 текст " * 10}
                ]
            elif "books" in sql:
                return [{"id": 1}]
            return []
        async def execute(self, sql, params=None):
            return True
    
    chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
    embedding = MockEmbeddingProvider(dimension=384)
    faiss = MockFAISSProvider(dimension=384)
    
    service = DocumentIndexingService(
        sql_provider=MockSQL(),
        faiss_provider=faiss,
        embedding_provider=embedding,
        chunking_strategy=chunking
    )
    
    # Индексация
    result = await service.index_book(book_id=1)
    
    print(f"Книга: {result['book_id']}")
    print(f"Чанков: {result['chunks_indexed']}")
    print(f"Векторов: {result['vectors_added']}")
    
    # Проверка
    count = await faiss.count()
    print(f"Всего векторов в индексе: {count}")


# ============================================================================
# Пример 4: Поиск с фильтрами
# ============================================================================

async def example_4_filtered_search():
    """Поиск с фильтрами по метаданным."""
    
    print("\n" + "="*60)
    print("Пример 4: Поиск с фильтрами")
    print("="*60)
    
    from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
    from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
    from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider
    
    chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
    embedding = MockEmbeddingProvider(dimension=384)
    faiss = MockFAISSProvider(dimension=384)
    
    # Индексируем несколько книг
    for book_id in [1, 2, 3]:
        text = f"Текст книги {book_id} о любви и войне."
        chunks = await chunking.split(text, document_id=f"book_{book_id}", metadata={"book_id": book_id})
        vectors = await embedding.generate([c.content for c in chunks])
        metadata = [{"chunk_id": c.id, "book_id": book_id} for c in chunks]
        await faiss.add(vectors, metadata)
    
    # Поиск без фильтра
    query = await embedding.generate_single("любовь")
    results_all = await faiss.search(query, top_k=10)
    print(f"Без фильтра: {len(results_all)} результатов")
    
    # Поиск с фильтром
    results_filtered = await faiss.search(
        query,
        top_k=10,
        filters={"book_id": [1, 2]}
    )
    print(f"С фильтром (book_id in [1,2]): {len(results_filtered)} результатов")
    
    for r in results_filtered:
        print(f"  - Book: {r['metadata']['book_id']}, Score: {r['score']:.2f}")


# ============================================================================
# Пример 5: Кэширование анализа
# ============================================================================

async def example_5_caching():
    """Кэширование результатов анализа."""
    
    print("\n" + "="*60)
    print("Пример 5: Кэширование анализа")
    print("="*60)
    
    from core.infrastructure.cache.analysis_cache import AnalysisCache
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = AnalysisCache(tmpdir)
        
        # Сохранение
        data = {
            "entity_id": "book_1",
            "analysis_type": "character",
            "result": {"main_character": "Евгений Онегин"},
            "confidence": 0.95
        }
        
        await cache.set("character:book_1", data, ttl_hours=168)
        print("✓ Сохранено в кэш")
        
        # Получение
        cached = await cache.get("character:book_1")
        print(f"✓ Получено из кэша: {cached['result']['main_character']}")
        
        # Статистика
        stats = await cache.get_stats()
        print(f"✓ Размер кэша: {stats['total_keys']} ключей, {stats['total_size_mb']:.3f} MB")


# ============================================================================
# Главная функция
# ============================================================================

async def main():
    """Запуск всех примеров."""
    
    print("\n" + "="*60)
    print("VECTOR SEARCH EXAMPLES")
    print("="*60)
    
    try:
        await example_1_basic_search()
        await example_2_character_analysis()
        await example_3_book_indexing()
        await example_4_filtered_search()
        await example_5_caching()
        
        print("\n" + "="*60)
        print("Все примеры выполнены успешно!")
        print("="*60 + "\n")
    
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

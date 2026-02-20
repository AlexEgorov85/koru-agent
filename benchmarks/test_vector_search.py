"""
Performance бенчмарки для векторного поиска.

Запуск:
    pytest benchmarks/test_vector_search.py -v --benchmark-only

Сравнение:
    pytest benchmarks/test_vector_search.py -v --benchmark-compare
"""

import pytest
import asyncio
from pathlib import Path


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def chunking_strategy():
    """Chunking стратегия для бенчмарков."""
    from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
    return TextChunkingStrategy(chunk_size=500, chunk_overlap=50, min_chunk_size=10)


@pytest.fixture
def embedding_provider():
    """Mock Embedding провайдер."""
    from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
    return MockEmbeddingProvider(dimension=384)


@pytest.fixture
def faiss_provider():
    """Mock FAISS провайдер."""
    from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider
    return MockFAISSProvider(dimension=384)


@pytest.fixture
def analysis_cache(tmp_path):
    """Кэш для бенчмарков."""
    from core.infrastructure.cache.analysis_cache import AnalysisCache
    return AnalysisCache(str(tmp_path / "cache"))


# ============================================================================
# BENCHMARKS: Chunking
# ============================================================================

class TestChunkingBenchmarks:
    """Бенчмарки chunking."""
    
    def test_chunking_small_text(self, benchmark, chunking_strategy):
        """Chunking маленького текста (100 символов)."""
        text = "A" * 100
        
        async def run():
            return await chunking_strategy.split(text, document_id="doc_1")
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 1
    
    def test_chunking_medium_text(self, benchmark, chunking_strategy):
        """Chunking среднего текста (1000 символов)."""
        text = "A" * 1000
        
        async def run():
            return await chunking_strategy.split(text, document_id="doc_1")
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 1
        
        # Цель: < 10 мс
        # assert result.stats['mean'] < 0.01
    
    def test_chunking_large_text(self, benchmark, chunking_strategy):
        """Chunking большого текста (10000 символов)."""
        text = "A" * 10000
        
        async def run():
            return await chunking_strategy.split(text, document_id="doc_1")
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 1
        
        # Цель: < 50 мс
        # assert result.stats['mean'] < 0.05


# ============================================================================
# BENCHMARKS: Embedding
# ============================================================================

class TestEmbeddingBenchmarks:
    """Бенчмарки embedding."""
    
    def test_embedding_single(self, benchmark, embedding_provider):
        """Embedding одного текста."""
        text = "Текст для эмбеддинга"
        
        async def run():
            return await embedding_provider.generate_single(text)
        
        result = benchmark(asyncio.run, run())
        assert len(result) == 384
        
        # Цель: < 100 мс (Mock быстро)
        # assert result.stats['mean'] < 0.1
    
    def test_embedding_batch(self, benchmark, embedding_provider):
        """Embedding батча текстов."""
        texts = ["Текст " + str(i) for i in range(10)]
        
        async def run():
            return await embedding_provider.generate(texts)
        
        result = benchmark(asyncio.run, run())
        assert len(result) == 10
        
        # Цель: < 500 мс (Mock быстро)
        # assert result.stats['mean'] < 0.5


# ============================================================================
# BENCHMARKS: FAISS Search
# ============================================================================

class TestFAISSBenchmarks:
    """Бенчмарки FAISS поиска."""
    
    @pytest.mark.asyncio
    async def test_faiss_search_small_index(self, benchmark, faiss_provider, embedding_provider):
        """Поиск в маленьком индексе (100 векторов)."""
        
        # Индексация
        vectors = await embedding_provider.generate(["Текст " + str(i) for i in range(100)])
        metadata = [{"id": i} for i in range(100)]
        await faiss_provider.add(vectors, metadata)
        
        # Поиск
        query = await embedding_provider.generate_single("запрос")
        
        async def run():
            return await faiss_provider.search(query, top_k=10)
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 1
        
        # Цель: < 10 мс
        # assert result.stats['mean'] < 0.01
    
    @pytest.mark.asyncio
    async def test_faiss_search_medium_index(self, benchmark, faiss_provider, embedding_provider):
        """Поиск в среднем индексе (1000 векторов)."""
        
        # Индексация
        vectors = await embedding_provider.generate(["Текст " + str(i) for i in range(1000)])
        metadata = [{"id": i} for i in range(1000)]
        await faiss_provider.add(vectors, metadata)
        
        # Поиск
        query = await embedding_provider.generate_single("запрос")
        
        async def run():
            return await faiss_provider.search(query, top_k=10)
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 1
        
        # Цель: < 50 мс
        # assert result.stats['mean'] < 0.05
    
    @pytest.mark.asyncio
    async def test_faiss_search_with_filters(self, benchmark, faiss_provider, embedding_provider):
        """Поиск с фильтрами."""
        
        # Индексация с метаданными
        vectors = await embedding_provider.generate(["Текст " + str(i) for i in range(500)])
        metadata = [{"category": "cat" + str(i % 5)} for i in range(500)]
        await faiss_provider.add(vectors, metadata)
        
        # Поиск с фильтром
        query = await embedding_provider.generate_single("запрос")
        
        async def run():
            return await faiss_provider.search(query, top_k=10, filters={"category": ["cat1"]})
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 0


# ============================================================================
# BENCHMARKS: Cache
# ============================================================================

class TestCacheBenchmarks:
    """Бенчмарки кэша."""
    
    def test_cache_set(self, benchmark, analysis_cache):
        """Сохранение в кэш."""
        data = {"result": {"main_character": "Test"}, "confidence": 0.9}
        
        async def run():
            await analysis_cache.set("test_key", data)
        
        benchmark(asyncio.run, run())
    
    def test_cache_get(self, benchmark, analysis_cache):
        """Получение из кэша."""
        data = {"result": {"main_character": "Test"}, "confidence": 0.9}
        
        async def setup():
            await analysis_cache.set("test_key", data)
        
        asyncio.run(setup())
        
        async def run():
            return await analysis_cache.get("test_key")
        
        result = benchmark(asyncio.run, run())
        assert result == data
        
        # Цель: < 5 мс
        # assert result.stats['mean'] < 0.005


# ============================================================================
# BENCHMARKS: End-to-End
# ============================================================================

class TestE2EBenchmarks:
    """E2E бенчмарки полного пайплайна."""
    
    @pytest.mark.asyncio
    async def test_e2e_indexing_pipeline(self, benchmark, chunking_strategy, embedding_provider, faiss_provider):
        """Полный пайплайн индексации."""
        
        text = "Текст книги для индексации. " * 100  # ~3000 символов
        
        async def run():
            # 1. Chunking
            chunks = await chunking_strategy.split(text, document_id="book_1", metadata={"book_id": 1})
            
            # 2. Embedding
            vectors = await embedding_provider.generate([chunk.content for chunk in chunks])
            
            # 3. FAISS add
            metadata = [{"chunk_id": chunk.id, "book_id": 1} for chunk in chunks]
            await faiss_provider.add(vectors, metadata)
            
            return len(chunks)
        
        result = benchmark(asyncio.run, run())
        assert result >= 1
        
        # Цель: < 500 мс для полного пайплайна
        # assert result.stats['mean'] < 0.5
    
    @pytest.mark.asyncio
    async def test_e2e_search_pipeline(self, benchmark, chunking_strategy, embedding_provider, faiss_provider):
        """Полный пайплайн поиска."""
        
        # Индексация
        text = "Текст книги для поиска. " * 100
        chunks = await chunking_strategy.split(text, document_id="book_1", metadata={"book_id": 1})
        vectors = await embedding_provider.generate([chunk.content for chunk in chunks])
        metadata = [{"chunk_id": chunk.id, "book_id": 1} for chunk in chunks]
        await faiss_provider.add(vectors, metadata)
        
        # Поиск
        query = await embedding_provider.generate_single("поиск")
        
        async def run():
            return await faiss_provider.search(query, top_k=10)
        
        result = benchmark(asyncio.run, run())
        assert len(result) >= 1
        
        # Цель: < 100 мс для поиска
        # assert result.stats['mean'] < 0.1

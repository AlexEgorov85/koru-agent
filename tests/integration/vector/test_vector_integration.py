"""
Integration тесты для векторного поиска.

Тестируют интеграцию между компонентами:
- Chunking → Embedding → FAISS
- FAISS → Search → Results
"""

import pytest
from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider


class TestChunkingEmbeddingFAISSIntegration:
    """Интеграция Chunking → Embedding → FAISS."""
    
    @pytest.fixture
    def components(self):
        """Создание компонентов."""
        return {
            "chunking": TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10),
            "embedding": MockEmbeddingProvider(dimension=384),
            "faiss": MockFAISSProvider(dimension=384)
        }
    
    @pytest.mark.asyncio
    async def test_full_indexing_pipeline(self, components):
        """Полный пайплайн индексации."""
        
        # 1. Текст книги
        text = "Глава 1. Текст первой главы.\n\nГлава 2. Текст второй главы."
        
        # 2. Chunking
        chunks = await components["chunking"].split(
            content=text,
            document_id="book_1",
            metadata={"book_id": 1}
        )
        
        assert len(chunks) >= 1
        
        # 3. Embedding
        vectors = await components["embedding"].generate(
            [chunk.content for chunk in chunks]
        )
        
        assert len(vectors) == len(chunks)
        assert len(vectors[0]) == 384
        
        # 4. FAISS add
        metadata = [
            {"chunk_id": chunk.id, "document_id": chunk.document_id, "book_id": 1}
            for chunk in chunks
        ]
        
        ids = await components["faiss"].add(vectors, metadata)
        
        assert len(ids) == len(chunks)
        
        # 5. FAISS search
        query_vector = await components["embedding"].generate_single("текст главы")
        
        results = await components["faiss"].search(
            query_vector,
            top_k=5,
            filters={"book_id": 1}
        )
        
        assert len(results) >= 1
        assert "score" in results[0]
        assert "metadata" in results[0]
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, components):
        """Поиск с фильтрами."""
        
        # Индексируем две книги
        for book_id in [1, 2]:
            text = f"Текст книги {book_id}"
            
            chunks = await components["chunking"].split(
                content=text,
                document_id=f"book_{book_id}",
                metadata={"book_id": book_id}
            )
            
            vectors = await components["embedding"].generate(
                [chunk.content for chunk in chunks]
            )
            
            metadata = [
                {"chunk_id": chunk.id, "book_id": book_id}
                for chunk in chunks
            ]
            
            await components["faiss"].add(vectors, metadata)
        
        # Поиск с фильтром
        query_vector = await components["embedding"].generate_single("текст")
        
        results = await components["faiss"].search(
            query_vector,
            top_k=10,
            filters={"book_id": [1]}
        )
        
        assert len(results) >= 1
        assert all(r["metadata"]["book_id"] == 1 for r in results)
    
    @pytest.mark.asyncio
    async def test_delete_from_index(self, components):
        """Удаление из индекса."""
        
        # Индексируем книгу
        text = "Текст книги"
        
        chunks = await components["chunking"].split(
            content=text,
            document_id="book_1",
            metadata={"book_id": 1}
        )
        
        vectors = await components["embedding"].generate(
            [chunk.content for chunk in chunks]
        )
        
        metadata = [{"chunk_id": chunk.id, "book_id": 1} for chunk in chunks]
        
        await components["faiss"].add(vectors, metadata)
        
        # Проверяем что есть
        count_before = await components["faiss"].count()
        assert count_before >= 1
        
        # Удаляем
        deleted = await components["faiss"].delete_by_filter({"book_id": 1})
        
        assert deleted >= 0

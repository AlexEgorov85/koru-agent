"""
E2E тесты для векторного поиска.

Тестируют полные сценарии использования:
- Поиск по книгам
- Анализ героев
- Индексация книг
"""

import pytest
from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider
from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider
from core.application.services.document_indexing_service import DocumentIndexingService


class TestDocumentIndexingE2E:
    """E2E тесты индексации документов."""
    
    @pytest.fixture
    def mock_sql(self):
        """Mock SQL."""
        class MockSQL:
            async def fetch(self, sql, params=None):
                if "book_texts" in sql:
                    return [
                        {"chapter": 1, "content": "Глава 1 текст"},
                        {"chapter": 2, "content": "Глава 2 текст"}
                    ]
                elif "books" in sql:
                    return [{"id": 1}]
                return []
            
            async def execute(self, sql, params=None):
                return True
        return MockSQL()
    
    @pytest.mark.asyncio
    async def test_full_indexing_pipeline(self, mock_sql):
        """Полный пайплайн индексации."""
        
        chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
        embedding = MockEmbeddingProvider(dimension=384)
        faiss = MockFAISSProvider(dimension=384)
        
        service = DocumentIndexingService(
            sql_provider=mock_sql,
            faiss_provider=faiss,
            embedding_provider=embedding,
            chunking_strategy=chunking
        )
        
        # Индексация
        result = await service.index_book(book_id=1)
        
        assert result["book_id"] == 1
        assert result["chunks_indexed"] >= 1
        assert result["vectors_added"] >= 1
        
        # Проверка что векторы добавлены
        count = await faiss.count()
        assert count >= 1
    
    @pytest.mark.asyncio
    async def test_reindexing(self, mock_sql):
        """Переиндексация."""
        
        chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
        embedding = MockEmbeddingProvider(dimension=384)
        faiss = MockFAISSProvider(dimension=384)
        
        service = DocumentIndexingService(
            sql_provider=mock_sql,
            faiss_provider=faiss,
            embedding_provider=embedding,
            chunking_strategy=chunking
        )
        
        # Первая индексация
        await service.index_book(book_id=1)
        
        # Переиндексация
        result = await service.reindex_book(book_id=1)
        
        assert result["book_id"] == 1
        assert result["indexed"] >= 1
    
    @pytest.mark.asyncio
    async def test_delete_book(self, mock_sql):
        """Удаление книги."""
        
        chunking = TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
        embedding = MockEmbeddingProvider(dimension=384)
        faiss = MockFAISSProvider(dimension=384)
        
        service = DocumentIndexingService(
            sql_provider=mock_sql,
            faiss_provider=faiss,
            embedding_provider=embedding,
            chunking_strategy=chunking
        )
        
        # Индексация
        await service.index_book(book_id=1)
        
        # Удаление
        result = await service.delete_book(book_id=1)
        
        assert result["book_id"] == 1
        assert "deleted" in result

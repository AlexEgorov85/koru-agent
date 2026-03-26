"""
Тесты DocumentIndexingService.
"""

import pytest
from core.services.document_indexing_service import DocumentIndexingService


class TestDocumentIndexingService:
    """Тесты DocumentIndexingService."""
    
    @pytest.fixture
    def mock_providers(self):
        """Mock провайдеры."""
        
        class MockSQL:
            async def fetch(self, sql, params=None):
                if "book_texts" in sql:
                    return [
                        {"chapter": 1, "content": "Глава 1 текст"},
                        {"chapter": 2, "content": "Глава 2 текст"}
                    ]
                elif "books" in sql:
                    return [{"id": 1}, {"id": 2}]
                return []
            
            async def execute(self, sql, params=None):
                return True
        
        class MockFAISS:
            def __init__(self):
                self.vectors = []
                self.metadata = []
            
            async def add(self, vectors, metadata):
                self.vectors.extend(vectors)
                self.metadata.extend(metadata)
                return list(range(len(vectors)))
            
            async def delete_by_filter(self, filters):
                return 0
        
        class MockEmbedding:
            async def generate(self, texts):
                return [[0.1] * 384 for _ in texts]
        
        class MockChunking:
            async def split(self, content, document_id, metadata=None):
                from core.models.types.vector_types import VectorChunk
                return [
                    VectorChunk(
                        id=f"{document_id}_chunk_0",
                        document_id=document_id,
                        content=content[:100],
                        metadata=metadata or {},
                        index=0
                    )
                ]
        
        return {
            "sql": MockSQL(),
            "faiss": MockFAISS(),
            "embedding": MockEmbedding(),
            "chunking": MockChunking()
        }
    
    @pytest.fixture
    def service(self, mock_providers):
        return DocumentIndexingService(
            sql_provider=mock_providers["sql"],
            faiss_provider=mock_providers["faiss"],
            embedding_provider=mock_providers["embedding"],
            chunking_strategy=mock_providers["chunking"]
        )
    
    @pytest.mark.asyncio
    async def test_index_book(self, service, mock_providers):
        """Индексация книги."""
        
        result = await service.index_book(book_id=1)
        
        assert result["book_id"] == 1
        assert result["chunks_indexed"] >= 1
        assert result["vectors_added"] >= 1
    
    @pytest.mark.asyncio
    async def test_reindex_book(self, service, mock_providers):
        """Переиндексация книги."""
        
        result = await service.reindex_book(book_id=1)
        
        assert result["book_id"] == 1
        assert result["indexed"] >= 1
    
    @pytest.mark.asyncio
    async def test_delete_book(self, service, mock_providers):
        """Удаление книги."""
        
        result = await service.delete_book(book_id=1)
        
        assert result["book_id"] == 1
        assert "deleted" in result
    
    @pytest.mark.asyncio
    async def test_index_all_books(self, service, mock_providers):
        """Индексация всех книг."""
        
        results = await service.index_all_books()
        
        assert len(results) >= 1
        assert all("book_id" in r for r in results)

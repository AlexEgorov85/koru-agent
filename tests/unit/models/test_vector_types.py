"""
Тесты моделей векторного поиска.
"""

import pytest
from datetime import datetime
from core.models.types.vector_types import (
    VectorSearchResult,
    VectorQuery,
    VectorDocument,
    VectorChunk,
    VectorIndexInfo,
    VectorSearchStats
)


class TestVectorSearchResult:
    """Тесты VectorSearchResult."""
    
    def test_create_valid(self):
        """Создание валидного результата."""
        result = VectorSearchResult(
            id="result_001",
            document_id="doc_123",
            chunk_id="chunk_456",
            score=0.92,
            content="текст чанка",
            metadata={"category": "technical"},
            source="books"
        )
        assert result.id == "result_001"
        assert result.score == 0.92
        assert result.source == "books"
    
    def test_score_validation(self):
        """Валидация score (0-1)."""
        with pytest.raises(ValueError):
            VectorSearchResult(
                id="r1", document_id="d1", score=1.5,
                content="text", metadata={}, source="books"
            )
        
        with pytest.raises(ValueError):
            VectorSearchResult(
                id="r1", document_id="d1", score=-0.1,
                content="text", metadata={}, source="books"
            )
    
    def test_source_any_string(self):
        """Тест: любой источник работает (string, не enum)."""
        result = VectorSearchResult(
            id="r1", document_id="d1", score=0.9,
            content="text", metadata={},
            source="any_custom_source"  # Любой string!
        )
        assert result.source == "any_custom_source"
    
    def test_chunk_id_optional(self):
        """chunk_id опционален."""
        result = VectorSearchResult(
            id="r1", document_id="d1", score=0.9,
            content="text", metadata={}, source="books"
        )
        assert result.chunk_id is None


class TestVectorQuery:
    """Тесты VectorQuery."""
    
    def test_create_with_query(self):
        """Создание с текстовым запросом."""
        query = VectorQuery(
            query="векторный поиск",
            top_k=10
        )
        assert query.query == "векторный поиск"
        assert query.top_k == 10
    
    def test_create_with_vector(self):
        """Создание с вектором."""
        query = VectorQuery(
            vector=[0.1] * 384,
            top_k=10
        )
        assert len(query.vector) == 384
    
    def test_top_k_validation(self):
        """Валидация top_k."""
        with pytest.raises(ValueError):
            VectorQuery(query="test", top_k=0)
        
        with pytest.raises(ValueError):
            VectorQuery(query="test", top_k=101)
    
    def test_filters_validation(self):
        """Валидация фильтров."""
        # Валидные фильтры
        query = VectorQuery(
            query="test",
            filters={"source": ["books"], "category": ["technical"]}
        )
        assert query.filters is not None
        
        # Невалидные фильтры
        with pytest.raises(ValueError):
            VectorQuery(
                query="test",
                filters={"invalid_filter": "value"}
            )
    
    def test_default_values(self):
        """Значения по умолчанию."""
        query = VectorQuery(query="test")
        assert query.top_k == 10
        assert query.min_score == 0.5
        assert query.offset == 0
        assert query.filters is None


class TestVectorDocument:
    """Тесты VectorDocument."""
    
    def test_create_valid(self):
        """Создание валидного документа."""
        doc = VectorDocument(
            content="текст документа",
            metadata={"category": "technical"},
            source="books"
        )
        assert doc.content == "текст документа"
        assert doc.source == "books"
    
    def test_chunk_size_validation(self):
        """Валидация chunk_size."""
        with pytest.raises(ValueError):
            VectorDocument(
                content="text", metadata={}, source="books",
                chunk_size=50  # < 100
            )
        
        with pytest.raises(ValueError):
            VectorDocument(
                content="text", metadata={}, source="books",
                chunk_size=3000  # > 2000
            )
    
    def test_id_optional(self):
        """id опционален."""
        doc = VectorDocument(
            content="text", metadata={}, source="books"
        )
        assert doc.id is None


class TestVectorChunk:
    """Тесты VectorChunk."""
    
    def test_create_valid(self):
        """Создание валидного чанка."""
        chunk = VectorChunk(
            id="chunk_001",
            document_id="doc_123",
            content="текст чанка",
            index=0
        )
        assert chunk.id == "chunk_001"
        assert chunk.index == 0
    
    def test_chapter_optional(self):
        """chapter опционален."""
        chunk = VectorChunk(
            id="chunk_001",
            document_id="doc_123",
            content="текст чанка",
            index=0
        )
        assert chunk.chapter is None
    
    def test_vector_optional(self):
        """vector опционален."""
        chunk = VectorChunk(
            id="chunk_001",
            document_id="doc_123",
            content="текст чанка",
            index=0
        )
        assert chunk.vector is None


class TestVectorIndexInfo:
    """Тесты VectorIndexInfo."""
    
    def test_create_valid(self):
        """Создание валидной информации."""
        info = VectorIndexInfo(
            source="books",
            total_documents=150,
            total_chunks=7500,
            index_size_mb=75.2,
            dimension=384,
            index_type="Flat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert info.total_documents == 150
        assert info.dimension == 384
    
    def test_source_any_string(self):
        """source - любой string."""
        info = VectorIndexInfo(
            source="custom_source",
            total_documents=10,
            total_chunks=100,
            index_size_mb=1.0,
            dimension=384,
            index_type="Flat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert info.source == "custom_source"


class TestVectorSearchStats:
    """Тесты VectorSearchStats."""
    
    def test_create_valid(self):
        """Создание валидной статистики."""
        stats = VectorSearchStats(
            query_time_ms=45.2,
            total_found=150,
            returned_count=10,
            filters_applied=["source"]
        )
        assert stats.query_time_ms == 45.2
        assert stats.total_found == 150
        assert stats.returned_count == 10

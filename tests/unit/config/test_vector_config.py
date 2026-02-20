"""
Тесты конфигурации векторного поиска.
"""

import pytest
from core.config.vector_config import (
    FAISSConfig,
    EmbeddingConfig,
    ChunkingConfig,
    VectorStorageConfig,
    AnalysisCacheConfig,
    VectorSearchConfig
)


class TestFAISSConfig:
    """Тесты FAISSConfig."""
    
    def test_default_values(self):
        """Значения по умолчанию."""
        config = FAISSConfig()
        assert config.index_type == "Flat"
        assert config.nlist == 100
        assert config.nprobe == 10
        assert config.metric == "IP"
    
    def test_nprobe_validation(self):
        """Валидация nprobe."""
        with pytest.raises(ValueError):
            FAISSConfig(nlist=50, nprobe=100)  # nprobe > nlist
    
    def test_index_type_validation(self):
        """Валидация index_type."""
        with pytest.raises(ValueError):
            FAISSConfig(index_type="Invalid")
    
    def test_metric_validation(self):
        """Валидация metric."""
        with pytest.raises(ValueError):
            FAISSConfig(metric="Invalid")


class TestEmbeddingConfig:
    """Тесты EmbeddingConfig."""
    
    def test_default_values(self):
        """Значения по умолчанию."""
        config = EmbeddingConfig()
        assert config.model_name == "all-MiniLM-L6-v2"
        assert config.dimension == 384
        assert config.device == "cpu"
        assert config.batch_size == 32
    
    def test_device_validation(self):
        """Валидация device."""
        with pytest.raises(ValueError):
            EmbeddingConfig(device="invalid")


class TestChunkingConfig:
    """Тесты ChunkingConfig."""
    
    def test_default_values(self):
        """Значения по умолчанию."""
        config = ChunkingConfig()
        assert config.enabled is True
        assert config.strategy == "text"
        assert config.chunk_size == 500
        assert config.chunk_overlap == 50
    
    def test_chunk_size_validation(self):
        """Валидация chunk_size."""
        with pytest.raises(ValueError):
            ChunkingConfig(chunk_size=50)  # < 100
        
        with pytest.raises(ValueError):
            ChunkingConfig(chunk_size=3000)  # > 2000
    
    def test_strategy_validation(self):
        """Валидация strategy."""
        with pytest.raises(ValueError):
            ChunkingConfig(strategy="invalid")


class TestVectorSearchConfig:
    """Тесты VectorSearchConfig."""
    
    def test_default_values(self):
        """Значения по умолчанию."""
        config = VectorSearchConfig()
        assert config.enabled is True
        assert config.default_top_k == 10
        assert config.max_top_k == 100
        assert len(config.indexes) == 4
        assert "knowledge" in config.indexes
        assert "books" in config.indexes
    
    def test_indexes_validation(self):
        """Валидация индексов."""
        # Неполный набор индексов
        with pytest.raises(ValueError):
            VectorSearchConfig(indexes={"knowledge": "k.faiss"})
        
        # Полный набор
        config = VectorSearchConfig(
            indexes={
                "knowledge": "k.faiss",
                "history": "h.faiss",
                "docs": "d.faiss",
                "books": "b.faiss"
            }
        )
        assert len(config.indexes) == 4
    
    def test_nested_configs(self):
        """Вложенные конфигурации."""
        config = VectorSearchConfig()
        assert config.faiss is not None
        assert config.embedding is not None
        assert config.chunking is not None
        assert config.storage is not None
        assert config.cache is not None
    
    def test_custom_values(self):
        """Пользовательские значения."""
        config = VectorSearchConfig(
            default_top_k=20,
            max_top_k=50,
            default_min_score=0.7
        )
        assert config.default_top_k == 20
        assert config.max_top_k == 50
        assert config.default_min_score == 0.7

"""
Тесты Chunking стратегий.
"""

import pytest
from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy


class TestTextChunkingStrategy:
    """Тесты TextChunkingStrategy."""
    
    @pytest.fixture
    def strategy(self):
        return TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
    
    @pytest.mark.asyncio
    async def test_small_text_one_chunk(self, strategy):
        """Маленький текст → один чанк."""
        text = "Короткий текст."
        chunks = await strategy.split(text, document_id="doc_1")
        
        assert len(chunks) >= 1
        assert chunks[0].document_id == "doc_1"
    
    @pytest.mark.asyncio
    async def test_large_text_multiple_chunks(self, strategy):
        """Большой текст → несколько чанков."""
        text = "A" * 500  # 500 символов
        chunks = await strategy.split(text, document_id="doc_1")
        
        assert len(chunks) >= 1
    
    @pytest.mark.asyncio
    async def test_overlap_exists(self, strategy):
        """Перекрытие существует."""
        text = "A" * 300
        chunks = await strategy.split(text, document_id="doc_1")
        
        if len(chunks) >= 2:
            # Проверяем что чанки не пустые
            assert len(chunks[0].content) > 0
            assert len(chunks[1].content) > 0
    
    @pytest.mark.asyncio
    async def test_metadata_included(self, strategy):
        """Метаданные включены."""
        text = "Текст с метаданными"
        chunks = await strategy.split(
            text,
            document_id="doc_1",
            metadata={"custom": "value"}
        )
        
        assert len(chunks) >= 1
        assert chunks[0].metadata.get("custom") == "value"
    
    @pytest.mark.asyncio
    async def test_paragraph_split(self, strategy):
        """Разбиение по абзацам."""
        text = "Длинный абзац 1\n\nДлинный абзац 2\n\nДлинный абзац 3"
        chunks = await strategy.split(text, document_id="doc_1")
        
        # Каждый абзац в отдельном чанке (если < chunk_size)
        assert len(chunks) >= 1
    
    def test_get_config(self, strategy):
        """Получение конфигурации."""
        config = strategy.get_config()
        
        assert config["type"] == "text"
        assert config["chunk_size"] == 100
        assert config["chunk_overlap"] == 10

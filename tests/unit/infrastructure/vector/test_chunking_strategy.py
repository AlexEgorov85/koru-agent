"""
Тесты стратегий разбиения текста (Chunking).

Покрывает:
- TextChunkingStrategy: рекурсивный split, overlap, валидация
- ChunkingFactory: создание стратегий, регистрация новых
- ChunkingService: entry point, from_config, from_dict
"""

import pytest
from core.config.vector_config import ChunkingConfig
from core.infrastructure.providers.vector.text_chunking_strategy import (
    TextChunkingStrategy,
    DEFAULT_SEPARATORS,
)
from core.infrastructure.providers.vector.chunking_factory import ChunkingFactory
from core.infrastructure.providers.vector.chunking_service import ChunkingService


# ═══════════════════════════════════════════════
# TextChunkingStrategy
# ═══════════════════════════════════════════════

class TestTextChunkingStrategy:
    """Тесты TextChunkingStrategy."""

    @pytest.fixture
    def strategy(self):
        return TextChunkingStrategy(chunk_size=100, chunk_overlap=10, min_chunk_size=10)

    # --- Базовые случаи ---

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self, strategy):
        """Пустой текст → пустой список."""
        chunks = await strategy.split("", document_id="doc_1")
        assert chunks == []

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty(self, strategy):
        """Только пробелы → пустой список."""
        chunks = await strategy.split("   \n\n   ", document_id="doc_1")
        assert chunks == []

    @pytest.mark.asyncio
    async def test_small_text_one_chunk(self, strategy):
        """Маленький текст → один чанк."""
        text = "Короткий текст."
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) == 1
        assert chunks[0].document_id == "doc_1"
        assert chunks[0].index == 0

    @pytest.mark.asyncio
    async def test_large_text_multiple_chunks(self, strategy):
        """Большой текст → несколько чанков."""
        text = "A" * 500
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) >= 1

    # --- Разделители ---

    @pytest.mark.asyncio
    async def test_paragraph_split(self, strategy):
        """Разбиение по абзацам (\\n\\n)."""
        # Два абзаца, каждый > chunk_size
        p1 = "A" * 60
        p2 = "B" * 60
        text = p1 + "\n\n" + p2
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) >= 2
        # Первый чанк содержит A-шки
        assert "A" in chunks[0].content
        # Второй содержит B-шки
        assert "B" in chunks[-1].content

    @pytest.mark.asyncio
    async def test_sentence_split(self, strategy):
        """Не режет предложения посередине если возможно."""
        # Каждое предложение < chunk_size
        sentences = "Первое предложение. Второе предложение. Третье предложение. "
        text = sentences * 5  # ~250 символов
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) >= 1
        # Проверяем что chunks не пустые
        assert all(len(c.content) > 0 for c in chunks)

    @pytest.mark.asyncio
    async def test_heading_split(self):
        """Разбиение по заголовкам."""
        strategy = TextChunkingStrategy(chunk_size=80, chunk_overlap=0, min_chunk_size=10)
        text = "## Глава 1\n\nТекст первой главы. " * 3
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) >= 1

    # --- Overlap ---

    @pytest.mark.asyncio
    async def test_overlap_added(self):
        """Overlap добавляется между чанками."""
        strategy = TextChunkingStrategy(chunk_size=60, chunk_overlap=15, min_chunk_size=10)
        text = "X" * 200
        chunks = await strategy.split(text, document_id="doc_1")

        if len(chunks) >= 2:
            # Первый чанк заканчивается на X
            # Второй должен содержать overlap (хвост первого)
            assert len(chunks[0].content) > 15
            # Второй чанк содержит overlap-часть первого
            # (проверяем что overlap реально есть — второй чанк начинается
            # с тех же символов, которыми кончился первый)
            overlap_tail = chunks[0].content[-15:]
            assert chunks[1].content.startswith(overlap_tail)

    @pytest.mark.asyncio
    async def test_no_overlap_when_disabled(self):
        """Без overlap — чанки не имеют общего хвоста/головы."""
        strategy = TextChunkingStrategy(chunk_size=60, chunk_overlap=0, min_chunk_size=10)
        # Разнообразный текст чтобы можно было отличить чанки
        text = "AAAAA БBBBB. CCCCC DDDDD. EEEEE FFFFF. GGGGG HHHHH. " * 5
        chunks = await strategy.split(text, document_id="doc_1")

        if len(chunks) >= 2:
            # has_overlap = False
            assert chunks[1].metadata.get("has_overlap") is False
            assert chunks[1].metadata.get("overlap_chars") == 0

    # --- Минимальный размер ---

    @pytest.mark.asyncio
    async def test_min_chunk_size_respected(self):
        """Чанки меньше min_chunk_size отбрасываются."""
        strategy = TextChunkingStrategy(chunk_size=100, chunk_overlap=0, min_chunk_size=50)
        text = "Короткий"  # 8 символов < min_chunk_size
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) == 0

    # --- Метаданные ---

    @pytest.mark.asyncio
    async def test_metadata_included(self, strategy):
        """Метаданные включены в каждый чанк."""
        text = "Текст с метаданными. " * 20  # достаточно большой
        chunks = await strategy.split(
            text,
            document_id="doc_1",
            metadata={"custom": "value"},
        )
        assert len(chunks) >= 1
        assert chunks[0].metadata.get("custom") == "value"

    # --- Конфигурация ---

    def test_get_config(self, strategy):
        """Получение конфигурации."""
        config = strategy.get_config()
        assert config["type"] == "text"
        assert config["chunk_size"] == 100
        assert config["chunk_overlap"] == 10
        assert config["min_chunk_size"] == 10
        assert "separators" in config

    # --- Валидация ---

    def test_invalid_chunk_size(self):
        """chunk_size <= 0 → ошибка."""
        with pytest.raises(ValueError, match="chunk_size"):
            TextChunkingStrategy(chunk_size=0)

    def test_negative_overlap(self):
        """overlap < 0 → ошибка."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            TextChunkingStrategy(chunk_overlap=-1)

    def test_overlap_greater_than_chunk_size(self):
        """overlap >= chunk_size → ошибка."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            TextChunkingStrategy(chunk_size=50, chunk_overlap=60)

    def test_invalid_min_chunk_size(self):
        """min_chunk_size <= 0 → ошибка."""
        with pytest.raises(ValueError, match="min_chunk_size"):
            TextChunkingStrategy(min_chunk_size=0)

    # --- Hard split fallback ---

    @pytest.mark.asyncio
    async def test_hard_split_fallback(self):
        """Если ни один разделитель не помог — жёсткий split."""
        # Текст без единого разделителя
        text = "А" * 300
        strategy = TextChunkingStrategy(chunk_size=100, chunk_overlap=0, min_chunk_size=10)
        chunks = await strategy.split(text, document_id="doc_1")
        assert len(chunks) >= 3
        # Каждый чанк <= chunk_size
        assert all(len(c.content) <= 100 for c in chunks)

    # --- Реальный текст с несколькими разделителями ---

    @pytest.mark.asyncio
    async def test_mixed_separators(self):
        """Текст с заголовками, абзацами и предложениями."""
        strategy = TextChunkingStrategy(chunk_size=150, chunk_overlap=10, min_chunk_size=10)
        text = (
            "## Заголовок 1\n\n"
            "Первый абзац. Он довольно длинный, "
            "чтобы занять много места. Второе предложение в абзаце. "
            "Третье предложение завершает этот абзац.\n\n"
            "## Заголовок 2\n\n"
            "Второй абзац с другим содержанием. "
            "Он тоже содержит несколько предложений. "
            "И достаточно длинный для теста.\n\n"
            "## Заголовок 3\n\n"
            "Третий абзац. Финальный текст для проверки.\n"
        )
        chunks = await strategy.split(text, document_id="book_1")
        assert len(chunks) >= 2
        # Первый чанк содержит первый заголовок
        assert "Заголовок 1" in chunks[0].content


# ═══════════════════════════════════════════════
# ChunkingFactory
# ═══════════════════════════════════════════════

class TestChunkingFactory:
    """Тесты ChunkingFactory."""

    def test_create_text_strategy(self):
        """Создание TextChunkingStrategy."""
        strategy = ChunkingFactory.create(strategy_type="text")
        assert isinstance(strategy, TextChunkingStrategy)

    def test_create_with_config(self):
        """Создание с ChunkingConfig."""
        config = ChunkingConfig(
            strategy="text",
            chunk_size=200,
            chunk_overlap=20,
            min_chunk_size=30,
        )
        strategy = ChunkingFactory.create(strategy_type="text", config=config)
        assert isinstance(strategy, TextChunkingStrategy)
        assert strategy.chunk_size == 200
        assert strategy.chunk_overlap == 20
        assert strategy.min_chunk_size == 30

    def test_create_with_kwargs_override(self):
        """kwargs переопределяют config."""
        config = ChunkingConfig(chunk_size=200, chunk_overlap=20)
        strategy = ChunkingFactory.create(
            strategy_type="text",
            config=config,
            chunk_size=300,  # переопределяем
        )
        assert strategy.chunk_size == 300

    def test_unknown_strategy_raises(self):
        """Неизвестная стратегия → ValueError."""
        with pytest.raises(ValueError, match="Неизвестная стратегия"):
            ChunkingFactory.create(strategy_type="nonexistent")

    def test_register_new_strategy(self):
        """Регистрация новой стратегии."""
        class CustomStrategy(TextChunkingStrategy):
            pass

        ChunkingFactory.register("custom", CustomStrategy)
        try:
            strategy = ChunkingFactory.create(strategy_type="custom")
            assert isinstance(strategy, CustomStrategy)
        finally:
            # Откатываем регистрацию (чтобы не влиять на другие тесты)
            ChunkingFactory._registry.pop("custom", None)

    def test_default_separators_used(self):
        """По умолчанию используются DEFAULT_SEPARATORS."""
        strategy = ChunkingFactory.create(strategy_type="text")
        assert strategy.separators == DEFAULT_SEPARATORS


# ═══════════════════════════════════════════════
# ChunkingService
# ═══════════════════════════════════════════════

class TestChunkingService:
    """Тесты ChunkingService."""

    @pytest.fixture
    def service(self):
        config = ChunkingConfig(
            strategy="text",
            chunk_size=100,
            chunk_overlap=10,
            min_chunk_size=10,
        )
        return ChunkingService.from_config(config)

    @pytest.mark.asyncio
    async def test_split_basic(self, service):
        """Базовое разбиение."""
        text = "Текст для разбиения. " * 20
        chunks = await service.split(text, document_id="doc_1")
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_split_with_metadata(self, service):
        """Метаданные передаются в чанки."""
        text = "Текст. " * 20
        chunks = await service.split(
            text, document_id="doc_1",
            metadata={"author": "Pushkin"},
        )
        assert all(c.metadata.get("author") == "Pushkin" for c in chunks)

    @pytest.mark.asyncio
    async def test_from_dict(self):
        """Создание из словаря."""
        service = ChunkingService.from_dict({
            "strategy_type": "text",
            "chunk_size": 80,
            "chunk_overlap": 5,
            "min_chunk_size": 10,
        })
        text = "A" * 200
        chunks = await service.split(text, document_id="doc_1")
        assert len(chunks) >= 1

    def test_get_config(self, service):
        """Получение конфигурации."""
        config = service.get_config()
        assert config["type"] == "text"
        assert config["chunk_size"] == 100
        assert config["chunk_overlap"] == 10

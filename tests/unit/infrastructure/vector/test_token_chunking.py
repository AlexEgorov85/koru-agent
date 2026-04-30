"""
Тесты для токен-ориентированного чанкинга в ChunkingService.

ТЕСТЫ:
- Переключение между символами и токенами
- Корректность разбиения по токенам
- Overlap в токенах
- Fallback при отсутствии tiktoken
"""
import pytest
from unittest.mock import patch, MagicMock
from core.infrastructure.providers.vector.chunking_service import (
    ChunkingService,
    _get_tiktoken_encoder,
    _estimate_chars_per_token,
)


class TestTokenChunking:
    """Тесты токен-ориентированного чанкинга."""

    def test_tiktoken_encoder_available(self):
        """Проверка получения encoder при наличии tiktoken."""
        encoder = _get_tiktoken_encoder("gpt-4")
        # Если tiktoken установлен, encoder должен быть не None
        # Если нет — тест просто проверит, что функция не падает
        assert encoder is None or hasattr(encoder, 'encode')

    def test_estimate_chars_per_token_russian(self):
        """Оценка символов на токен для русского текста."""
        text = "Привет мир! Как дела?" * 10
        ratio = _estimate_chars_per_token(text)
        assert ratio == pytest.approx(2.2, abs=0.1)

    def test_estimate_chars_per_token_english(self):
        """Оценка символов на токен для английского текста."""
        text = "Hello world! How are you?" * 10
        ratio = _estimate_chars_per_token(text)
        assert ratio == pytest.approx(3.5, abs=0.1)

    @patch('core.infrastructure.providers.vector.chunking_service._get_tiktoken_encoder')
    def test_chunking_service_init_token_mode(self, mock_get_encoder):
        """Инициализация ChunkingService в токен-режиме."""
        mock_encoder = MagicMock()
        mock_get_encoder.return_value = mock_encoder

        service = ChunkingService(
            use_tokens=True,
            model_name="gpt-4",
            max_tokens_per_chunk=2000,
            token_overlap=100
        )
        assert service.use_tokens is True
        assert service._token_encoder is not None
        assert service.max_tokens_per_chunk == 2000
        assert service.token_overlap == 100

    def test_chunking_service_init_char_mode(self):
        """Инициализация ChunkingService в символ-режиме."""
        service = ChunkingService(
            chunk_size_chars=4000,
            chunk_size_rows=50
        )
        assert service.use_tokens is False
        assert service.chunk_size_chars == 4000

    @patch('core.infrastructure.providers.vector.chunking_service._get_tiktoken_encoder')
    def test_chunk_text_tokens_mock(self, mock_get_encoder):
        """Тест разбиения по токенам с мокнутым encoder."""
        # Создаем мок encoder
        mock_encoder = MagicMock()
        # Для текста длиной 100 токенов
        mock_encoder.encode.return_value = list(range(100))
        mock_encoder.decode.return_value = "chunk text"
        mock_get_encoder.return_value = mock_encoder

        service = ChunkingService(
            use_tokens=True,
            model_name="gpt-4",
            max_tokens_per_chunk=30,
            token_overlap=5
        )

        text = "A " * 100  # 100 слов
        chunks = service.chunk_text_tokens(text)

        assert len(chunks) > 1
        assert all(c["mode"] == "tokens" for c in chunks)
        assert all("token_count" in c for c in chunks)

    @patch('core.infrastructure.providers.vector.chunking_service._get_tiktoken_encoder')
    def test_chunk_text_tokens_fallback_without_encoder(self, mock_get_encoder):
        """Fallback к символам при отсутствии encoder."""
        mock_get_encoder.return_value = None

        service = ChunkingService(
            use_tokens=True,
            model_name="gpt-4",
        )
        # use_tokens остаётся True, но encoder=None
        assert service.use_tokens is True
        assert service._token_encoder is None

        # При чанкинге произойдёт fallback к символам
        text = "Sample text " * 100
        chunks = service.chunk_text(text)
        assert len(chunks) > 0
        assert chunks[0]["mode"] == "chars"

    @patch('core.infrastructure.providers.vector.chunking_service._get_tiktoken_encoder')
    def test_get_config_includes_token_settings(self, mock_get_encoder):
        """Проверка, что get_config возвращает настройки токенов."""
        mock_encoder = MagicMock()
        mock_get_encoder.return_value = mock_encoder

        service = ChunkingService(
            use_tokens=True,
            model_name="gpt-4",
            max_tokens_per_chunk=1500,
            token_overlap=80
        )
        config = service.get_config()
        assert config["use_tokens"] is True
        assert config["model_name"] == "gpt-4"
        assert config["max_tokens_per_chunk"] == 1500
        assert config["token_overlap"] == 80

    def test_get_stats_token_mode(self):
        """Статистика для токен-режима."""
        chunks = [
            {"type": "text", "mode": "tokens", "token_count": 100, "char_count": 300, "model": "gpt-4"},
            {"type": "text", "mode": "tokens", "token_count": 150, "char_count": 400, "model": "gpt-4"},
        ]
        service = ChunkingService()
        stats = service.get_stats(chunks)

        assert stats["token_mode"] is True
        assert stats["total_tokens"] == 250
        assert stats["avg_tokens_per_chunk"] == 125
        assert stats["token_model"] == "gpt-4"

    def test_get_stats_char_mode(self):
        """Статистика для символ-режима."""
        chunks = [
            {"type": "text", "mode": "chars", "char_count": 1000},
            {"type": "text", "mode": "chars", "char_count": 1500},
        ]
        service = ChunkingService()
        stats = service.get_stats(chunks)

        assert stats["token_mode"] is False
        assert "total_tokens" not in stats

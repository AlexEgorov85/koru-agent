"""
Тесты Mock Embedding провайдера.
"""

import pytest
from core.infrastructure.providers.embedding.mock_embedding_provider import MockEmbeddingProvider


class TestMockEmbeddingProvider:
    """Тесты MockEmbeddingProvider."""
    
    @pytest.fixture
    def provider(self):
        return MockEmbeddingProvider(dimension=384)
    
    @pytest.mark.asyncio
    async def test_initialize(self, provider):
        """Инициализация."""
        await provider.initialize()
        # Mock не требует инициализации
        assert True
    
    @pytest.mark.asyncio
    async def test_generate_single(self, provider):
        """Генерация одного вектора."""
        vector = await provider.generate_single("тест")
        
        assert len(vector) == 384
        assert isinstance(vector, list)
    
    @pytest.mark.asyncio
    async def test_generate_multiple(self, provider):
        """Генерация нескольких векторов."""
        texts = ["текст 1", "текст 2", "текст 3"]
        vectors = await provider.generate(texts)
        
        assert len(vectors) == 3
        assert all(len(v) == 384 for v in vectors)
    
    @pytest.mark.asyncio
    async def test_generate_empty(self, provider):
        """Генерация пустого списка."""
        vectors = await provider.generate([])
        
        assert vectors == []
    
    @pytest.mark.asyncio
    async def test_vector_normalized(self, provider):
        """Векторы нормализованы."""
        vector = await provider.generate_single("тест")
        
        # Проверяем нормализацию (сумма квадратов ≈ 1)
        norm = sum(x ** 2 for x in vector) ** 0.5
        
        assert abs(norm - 1.0) < 0.01  # Допускаем небольшую погрешность
    
    def test_get_dimension(self, provider):
        """Получение размерности."""
        dim = provider.get_dimension()
        
        assert dim == 384
    
    @pytest.mark.asyncio
    async def test_shutdown(self, provider):
        """Закрытие."""
        await provider.shutdown()
        # Mock не требует очистки
        assert True

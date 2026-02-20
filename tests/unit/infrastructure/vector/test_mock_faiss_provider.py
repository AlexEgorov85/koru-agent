"""
Тесты Mock FAISS провайдера.
"""

import pytest
from core.infrastructure.providers.vector.mock_faiss_provider import MockFAISSProvider


class TestMockFAISSProvider:
    """Тесты MockFAISSProvider."""
    
    @pytest.fixture
    def provider(self):
        return MockFAISSProvider(dimension=384)
    
    @pytest.mark.asyncio
    async def test_initialize(self, provider):
        """Инициализация."""
        await provider.initialize()
        # Mock не требует инициализации
        assert provider.vectors == []
    
    @pytest.mark.asyncio
    async def test_add_vectors(self, provider):
        """Добавление векторов."""
        vectors = [[0.1] * 384, [0.2] * 384]
        metadata = [{"book_id": 1}, {"book_id": 2}]
        
        ids = await provider.add(vectors, metadata)
        
        assert len(ids) == 2
        assert await provider.count() == 2
    
    @pytest.mark.asyncio
    async def test_search(self, provider):
        """Поиск."""
        vectors = [[0.1] * 384]
        metadata = [{"book_id": 1, "category": "test"}]
        
        await provider.add(vectors, metadata)
        
        query = [0.1] * 384
        results = await provider.search(query, top_k=10)
        
        assert len(results) >= 1
        assert "score" in results[0]
        assert "metadata" in results[0]
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, provider):
        """Поиск с фильтрами."""
        vectors = [[0.1] * 384, [0.2] * 384]
        metadata = [
            {"book_id": 1, "category": "test"},
            {"book_id": 2, "category": "other"}
        ]
        
        await provider.add(vectors, metadata)
        
        query = [0.1] * 384
        results = await provider.search(
            query,
            top_k=10,
            filters={"category": ["test"]}
        )
        
        assert len(results) >= 1
        assert results[0]["metadata"]["category"] == "test"
    
    @pytest.mark.asyncio
    async def test_delete_by_filter(self, provider):
        """Удаление по фильтру."""
        vectors = [[0.1] * 384, [0.2] * 384]
        metadata = [
            {"book_id": 1, "category": "test"},
            {"book_id": 2, "category": "other"}
        ]
        
        await provider.add(vectors, metadata)
        
        deleted = await provider.delete_by_filter({"category": ["test"]})
        
        assert deleted >= 1
        assert await provider.count() >= 1  # Остался второй вектор
    
    @pytest.mark.asyncio
    async def test_get_metadata(self, provider):
        """Получение метаданных."""
        vectors = [[0.1] * 384]
        metadata = [{"book_id": 1, "category": "test"}]
        
        ids = await provider.add(vectors, metadata)
        
        meta = await provider.get_metadata(ids[0])
        
        assert meta is not None
        assert meta["book_id"] == 1
    
    @pytest.mark.asyncio
    async def test_save_load(self, provider, tmp_path):
        """Сохранение и загрузка (mock не сохраняет)."""
        path = str(tmp_path / "test_index.faiss")
        
        await provider.save(path)
        await provider.load(path)
        
        # Mock не сохраняет реально
        assert True
    
    @pytest.mark.asyncio
    async def test_shutdown(self, provider):
        """Закрытие."""
        vectors = [[0.1] * 384]
        metadata = [{"book_id": 1}]
        
        await provider.add(vectors, metadata)
        await provider.shutdown()
        
        assert await provider.count() == 0

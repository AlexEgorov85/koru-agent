"""
Адаптеры для VectorPort.

АДАПТЕРЫ = Реализации портов для конкретных векторных провайдеров.
Использует существующие провайдеры через адаптер.
"""
from typing import Dict, Any, List, Optional
import hashlib

from core.infrastructure.interfaces.ports import VectorPort


class FAISSAdapter(VectorPort):
    """
    Адаптер FAISS для VectorPort.
    
    ОБЁРТКА вокруг FAISSProvider для работы через порт.
    
    USAGE:
    ```python
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from core.config.vector_config import FAISSConfig
    
    config = FAISSConfig(index_type="Flat", dimension=384)
    provider = FAISSProvider(dimension=384, config=config)
    await provider.initialize()
    
    adapter = FAISSAdapter(provider, embedding_function)
    
    # Использование через порт
    results = await adapter.search(query="поиск документов", top_k=5)
    ids = await adapter.add(documents=[{"content": "text", "metadata": {...}}])
    ```
    """
    
    def __init__(self, provider, embedding_function):
        """
        ARGS:
        - provider: Экземпляр FAISSProvider
        - embedding_function: Функция для получения эмбеддингов из текста
        """
        self._provider = provider
        self._embedding_function = embedding_function
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих векторов.
        
        ARGS:
        - query: Текстовый запрос
        - top_k: Количество результатов
        - filters: Фильтры по метаданным
        - threshold: Порог схожести (0.0-1.0)
        
        RETURNS:
        - Список результатов с полями: id, content, metadata, score
        """
        if not self._provider.index:
            await self._provider.initialize()
        
        # Получаем эмбеддинг запроса
        query_vector = await self._get_embedding(query)
        
        # Поиск через провайдер
        results = await self._provider.search(
            query_vector=query_vector,
            top_k=top_k,
            filters=filters
        )
        
        # Фильтруем по threshold и форматируем результат
        filtered_results = []
        for result in results:
            score = result.get("score", 0)
            
            # Нормализуем score к диапазону 0-1 (FAISS возвращает inner product)
            normalized_score = (score + 1) / 2  # Из [-1, 1] в [0, 1]
            
            if normalized_score >= threshold:
                filtered_results.append({
                    "id": str(result.get("vector_id", "")),
                    "content": result.get("metadata", {}).get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "score": normalized_score
                })
        
        return filtered_results
    
    async def add(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Добавить документы в индекс.
        
        ARGS:
        - documents: Документы с полями: content, metadata
        
        RETURNS:
        - Список ID добавленных документов
        """
        if not self._provider.index:
            await self._provider.initialize()
        
        # Извлекаем контент и метаданные
        contents = []
        metadata_list = []
        
        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            # Добавляем content в metadata для хранения
            metadata["content"] = content
            
            contents.append(content)
            metadata_list.append(metadata)
        
        # Получаем эмбеддинги
        vectors = await self._get_embeddings(contents)
        
        # Добавляем через провайдер
        vector_ids = await self._provider.add(
            vectors=vectors,
            metadata=metadata_list
        )
        
        # Возвращаем строковые ID
        return [str(vid) for vid in vector_ids]
    
    async def delete(self, ids: List[str]) -> int:
        """
        Удалить документы по ID.
        
        FAISS не поддерживает прямое удаление, поэтому используем фильтр.
        """
        # Создаём фильтр по ID
        # В текущей реализации FAISSProvider delete_by_filter удаляет только метаданные
        deleted = 0
        
        for doc_id in ids:
            # Пытаемся удалить по ID
            filter_result = await self._provider.delete_by_filter(
                filters={"id": doc_id}
            )
            deleted += filter_result
        
        return deleted
    
    async def rebuild_index(self) -> bool:
        """
        Перестроить индекс (после массового добавления).
        
        Для FAISS это может означать переобучение IVF индекса.
        """
        # В текущей реализации FAISSProvider это не требуется
        # IVF индекс обучается автоматически при добавлении
        return True
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Получить эмбеддинг для текста."""
        embeddings = await self._get_embeddings([text])
        return embeddings[0] if embeddings else []
    
    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Получить эмбеддинги для списка текстов."""
        if callable(self._embedding_function):
            # Если функция асинхронная
            import asyncio
            if asyncio.iscoroutinefunction(self._embedding_function):
                return await self._embedding_function(texts)
            else:
                # Синхронная функция
                return self._embedding_function(texts)
        else:
            # Mock-эмбеддинги (для тестирования)
            return [self._mock_embedding(text) for text in texts]
    
    def _mock_embedding(self, text: str) -> List[float]:
        """
        Создать mock-эмбеддинг на основе хэша текста.
        
        ДЛЯ ТЕСТИРОВАНИЯ без реальной embedding модели.
        """
        # Создаём детерминированный вектор на основе хэша
        hash_bytes = hashlib.md5(text.encode()).digest()
        
        # Генерируем вектор размерности 384 (стандарт для many models)
        dimension = 384
        vector = []
        
        for i in range(dimension):
            byte_idx = i % len(hash_bytes)
            # Конвертируем байт в float [-1, 1]
            value = (hash_bytes[byte_idx] - 128) / 128.0
            vector.append(value)
        
        # Нормализуем вектор
        import math
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector


class MockVectorAdapter(VectorPort):
    """
    Mock-адаптер для VectorPort.
    
    ДЛЯ ТЕСТИРОВАНИЯ без реального FAISS.
    
    USAGE:
    ```python
    adapter = MockVectorAdapter(predefined_results=[
        {"id": "1", "content": "Test doc", "score": 0.95}
    ])
    results = await adapter.search(query="test")
    ```
    """
    
    def __init__(
        self,
        predefined_results: Optional[List[Dict[str, Any]]] = None
    ):
        """
        ARGS:
        - predefined_results: Предопределённые результаты поиска
        """
        self._results = predefined_results or []
        self._documents: List[Dict[str, Any]] = []
        self._search_calls: List[Dict[str, Any]] = []
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        self._search_calls.append({
            "query": query,
            "top_k": top_k,
            "filters": filters,
            "threshold": threshold
        })
        
        # Возвращаем предопределённые результаты
        return self._results[:top_k]
    
    async def add(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        ids = []
        for i, doc in enumerate(documents):
            doc_id = f"mock_{len(self._documents) + i}"
            doc["id"] = doc_id
            self._documents.append(doc)
            ids.append(doc_id)
        
        return ids
    
    async def delete(self, ids: List[str]) -> int:
        count = 0
        for doc_id in ids:
            for i, doc in enumerate(self._documents):
                if doc.get("id") == doc_id:
                    self._documents.pop(i)
                    count += 1
                    break
        
        return count
    
    async def rebuild_index(self) -> bool:
        return True
    
    @property
    def search_calls(self) -> List[Dict[str, Any]]:
        return self._search_calls
    
    @property
    def documents(self) -> List[Dict[str, Any]]:
        return self._documents

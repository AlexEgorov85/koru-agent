"""
Интерфейс FAISS провайдера.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple


class IFAISSProvider(ABC):
    """
    Интерфейс FAISS провайдера.
    
    Пример использования:
        provider = FAISSProvider(dimension=384, metric="IP")
        await provider.add(vectors, metadata)
        results = await provider.search(query_vector, top_k=10)
    """
    
    @abstractmethod
    async def initialize(self):
        """Инициализация провайдера."""
        pass
    
    @abstractmethod
    async def add(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Добавление векторов в индекс.
        
        Args:
            vectors: Список векторов
            metadata: Список метаданных (по одному на вектор)
        
        Returns:
            Список ID добавленных векторов
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск ближайших векторов.
        
        Args:
            query_vector: Вектор запроса
            top_k: Количество результатов
            filters: Фильтры по метаданным
        
        Returns:
            Список результатов (vector_id, score, metadata)
        """
        pass
    
    @abstractmethod
    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """
        Удаление векторов по фильтру.
        
        Args:
            filters: Фильтры для удаления
        
        Returns:
            Количество удалённых векторов
        """
        pass
    
    @abstractmethod
    async def save(self, path: str):
        """Сохранение индекса на диск."""
        pass
    
    @abstractmethod
    async def load(self, path: str):
        """Загрузка индекса с диска."""
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """Получить количество векторов в индексе."""
        pass
    
    @abstractmethod
    async def get_metadata(self, vector_id: int) -> Optional[Dict[str, Any]]:
        """Получить метаданные по ID вектора."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Закрытие провайдера."""
        pass

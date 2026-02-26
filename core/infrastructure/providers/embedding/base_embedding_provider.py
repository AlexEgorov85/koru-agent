"""
Интерфейс Embedding провайдера.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class IEmbeddingProvider(ABC):
    """
    Интерфейс Embedding провайдера.
    
    Пример использования:
        provider = SentenceTransformersProvider(model_name="all-MiniLM-L6-v2")
        await provider.initialize()
        vectors = await provider.generate(["текст 1", "текст 2"])
    """
    
    @abstractmethod
    async def initialize(self):
        """Инициализация провайдера."""
        pass
    
    @abstractmethod
    async def generate(self, texts: List[str]) -> List[List[float]]:
        """
        Генерация эмбеддингов для текстов.
        
        Args:
            texts: Список текстов
        
        Returns:
            Список векторов
        """
        pass
    
    @abstractmethod
    async def generate_single(self, text: str) -> List[float]:
        """
        Генерация эмбеддинга для одного текста.
        
        Args:
            text: Текст
        
        Returns:
            Вектор
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Получить размерность векторов."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Закрытие провайдера."""
        pass

"""
Mock Embedding провайдер для тестов.
"""

from typing import List, Optional
import random
from core.infrastructure.providers.embedding.base_embedding_provider import IEmbeddingProvider


class MockEmbeddingProvider(IEmbeddingProvider):
    """
    Mock Embedding провайдера для тестов.
    
    Не требует SentenceTransformers, генерирует псевдо-векторы.
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
    
    async def initialize(self):
        """Инициализация (пустая для mock)."""
        pass
    
    async def generate(self, texts: List[str]) -> List[List[float]]:
        """Генерация псевдо-векторов."""
        
        vectors = []
        for _ in texts:
            # Генерируем псевдо-вектор (нормализованный)
            vector = [random.gauss(0, 1) for _ in range(self.dimension)]
            
            # Нормализуем
            norm = sum(x ** 2 for x in vector) ** 0.5
            vector = [x / norm for x in vector]
            
            vectors.append(vector)
        
        return vectors
    
    async def generate_single(self, text: str) -> List[float]:
        """Генерация псевдо-вектора для одного текста."""
        vectors = await self.generate([text])
        return vectors[0] if vectors else []
    
    def get_dimension(self) -> int:
        """Получить размерность."""
        return self.dimension
    
    async def shutdown(self):
        """Закрытие (пустая для mock)."""
        pass

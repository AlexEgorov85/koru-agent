"""
Mock FAISS провайдер для тестов.
"""

from typing import List, Optional, Dict, Any
import random
from core.infrastructure.providers.vector.base_faiss_provider import IFAISSProvider


class MockFAISSProvider(IFAISSProvider):
    """
    Mock FAISS провайдера для тестов.
    
    Не требует FAISS, генерирует псевдо-результаты.
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: List[List[float]] = []
        self.metadata: Dict[int, Dict[str, Any]] = {}
        self.id_counter = 0
    
    async def initialize(self):
        """Инициализация (пустая для mock)."""
        pass
    
    async def add(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> List[int]:
        """Добавление векторов."""
        
        start_id = self.id_counter
        for i, (vec, meta) in enumerate(zip(vectors, metadata)):
            self.vectors.append(vec)
            self.metadata[start_id + i] = meta
        
        self.id_counter += len(vectors)
        return list(range(start_id, start_id + len(vectors)))
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск (возвращает псевдо-результаты)."""
        
        results = []
        for vid, meta in self.metadata.items():
            # Применяем фильтры
            if filters and not self._matches_filters(meta, filters):
                continue
            
            # Псевдо-score (рандомный для тестов)
            score = random.uniform(0.5, 1.0)
            
            results.append({
                "vector_id": vid,
                "score": score,
                "metadata": meta
            })
        
        # Сортируем по score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]
    
    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Проверка фильтров."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            meta_value = metadata[key]
            if isinstance(value, list):
                if meta_value not in value:
                    return False
            else:
                if meta_value != value:
                    return False
        
        return True
    
    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Удаление по фильтру."""
        deleted = 0
        vector_ids_to_delete = [
            vid for vid, meta in self.metadata.items()
            if self._matches_filters(meta, filters)
        ]
        
        for vid in vector_ids_to_delete:
            del self.metadata[vid]
            deleted += 1
        
        return deleted
    
    async def save(self, path: str):
        """Сохранение (пустая для mock)."""
        pass
    
    async def load(self, path: str):
        """Загрузка (пустая для mock)."""
        pass
    
    async def count(self) -> int:
        """Количество векторов."""
        return len(self.vectors)
    
    async def get_metadata(self, vector_id: int) -> Optional[Dict[str, Any]]:
        """Получение метаданных."""
        return self.metadata.get(vector_id)
    
    async def shutdown(self):
        """Закрытие."""
        self.vectors = []
        self.metadata = {}
        self.id_counter = 0

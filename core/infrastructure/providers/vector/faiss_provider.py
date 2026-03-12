"""
FAISS провайдер для векторного поиска.
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None

from core.infrastructure.providers.vector.base_faiss_provider import IFAISSProvider
from core.config.vector_config import FAISSConfig


class FAISSProvider(IFAISSProvider):
    """
    Реализация FAISS провайдера.
    
    Поддерживаемые индексы:
    - Flat: точный поиск (медленно для больших данных)
    - IVF: инвертированный файл (быстро для больших данных)
    - HNSW: граф (очень быстро, больше памяти)
    """
    
    def __init__(
        self,
        dimension: int = 384,
        config: Optional[FAISSConfig] = None
    ):
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not installed. Install with: pip install faiss-cpu")
        
        self.dimension = dimension
        self.config = config or FAISSConfig()
        self.index = None
        self.metadata: Dict[int, Dict[str, Any]] = {}
        self.id_counter = 0
    
    async def initialize(self):
        """Инициализация индекса."""
        
        if self.config.index_type == "Flat":
            # Flat index - точный поиск
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product для косинусного
        
        elif self.config.index_type == "IVF":
            # IVF index - для больших данных
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(
                quantizer,
                self.dimension,
                self.config.nlist,
                faiss.METRIC_INNER_PRODUCT
            )
            # Нужно обучить индекс перед использованием
            # Но для начала просто создаём
        
        elif self.config.index_type == "HNSW":
            # HNSW index - очень быстро
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)
        
        else:
            raise ValueError(f"Unknown index type: {self.config.index_type}")
    
    async def add(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> List[int]:
        """Добавление векторов в индекс."""
        
        if not vectors:
            return []
        
        # Конвертируем в numpy array
        vectors_array = np.array(vectors, dtype=np.float32)
        
        # Нормализуем для косинусного сходства
        faiss.normalize_L2(vectors_array)
        
        # Обучаем индекс если нужно (для IVF)
        if self.config.index_type == "IVF" and not self.index.is_trained:
            self.index.train(vectors_array)
        
        # Добавляем векторы
        start_id = self.id_counter
        self.index.add(vectors_array)
        
        # Сохраняем метаданные
        for i, meta in enumerate(metadata):
            vector_id = start_id + i
            self.metadata[vector_id] = meta
        
        self.id_counter += len(vectors)
        
        return list(range(start_id, start_id + len(vectors)))
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск ближайших векторов."""
        
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Конвертируем и нормализуем запрос
        query_array = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(query_array)
        
        # Поиск
        scores, indices = self.index.search(query_array, top_k * 3)  # Берём с запасом для фильтрации
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS возвращает -1 для пустых результатов
                continue
            
            meta = self.metadata.get(idx, {})
            
            # Применяем фильтры
            if filters and not self._matches_filters(meta, filters):
                continue
            
            results.append({
                "vector_id": idx,
                "score": float(score),
                "metadata": meta
            })
            
            if len(results) >= top_k:
                break
        
        return results
    
    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Проверка соответствия метаданных фильтрам."""
        
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            meta_value = metadata[key]
            
            # Если фильтр - список, проверяем вхождение
            if isinstance(value, list):
                if meta_value not in value:
                    return False
            else:
                if meta_value != value:
                    return False
        
        return True
    
    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Удаление векторов по фильтру."""
        
        # FAISS не поддерживает прямое удаление, нужно пересоздавать индекс
        # Для простоты просто удаляем метаданные
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
        """Сохранение индекса на диск."""
        
        # Сохраняем индекс
        faiss.write_index(self.index, path)
        
        # Сохраняем метаданные
        metadata_path = path.replace(".faiss", "_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": self.metadata,
                "id_counter": self.id_counter
            }, f, ensure_ascii=False, indent=2)
    
    async def load(self, path: str):
        """Загрузка индекса с диска."""
        
        # Загружаем индекс
        self.index = faiss.read_index(path)
        
        # Загружаем метаданные
        metadata_path = path.replace(".faiss", "_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.metadata = {int(k): v for k, v in data["metadata"].items()}
                self.id_counter = data.get("id_counter", 0)
    
    async def count(self) -> int:
        """Получить количество векторов."""
        return self.index.ntotal if self.index else 0
    
    async def get_metadata(self, vector_id: int) -> Optional[Dict[str, Any]]:
        """Получить метаданные по ID вектора."""
        return self.metadata.get(vector_id)

    async def shutdown(self):
        """Закрытие провайдера."""
        self.index = None
        self.metadata = {}

    # Методы для совместимости с VectorInterface
    # ПРИМЕЧАНИЕ: search(query) и add(documents) требуют embedding функции
    # Используйте search(query_vector) и add(vectors, metadata) напрямую

    async def delete(self, ids: List[str]) -> int:
        """
        Удалить документы по ID (для совместимости с VectorInterface).
        """
        deleted = 0
        for doc_id in ids:
            # Пытаемся удалить по ID через фильтр
            filter_result = await self.delete_by_filter({"id": doc_id})
            deleted += filter_result
        return deleted

    async def rebuild_index(self) -> bool:
        """
        Перестроить индекс (для совместимости с VectorInterface).
        Для FAISS это может означать переобучение IVF индекса.
        """
        # В текущей реализации FAISSProvider это не требуется
        # IVF индекс обучается автоматически при добавлении
        return True

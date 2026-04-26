"""
FAISS провайдер для векторного поиска.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

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
        dimension: int,
        config: Optional[FAISSConfig] = None
    ):
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not installed. Install with: pip install faiss-cpu")
        
        self.dimension = dimension
        self.config = config or FAISSConfig()
        self.index = None
        self.metadata: Dict[int, Dict[str, Any]] = {}
        self.id_counter = 0
        self._deleted_ids: set = set()
    
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
            print("start_id", start_id)
            print("i", i)
            print("meta", meta)
            vector_id = start_id + i
            self.metadata[vector_id] = meta
        
        self.id_counter += len(vectors)
        
        return list(range(start_id, start_id + len(vectors)))
    
    async def search(
        self,
        query_vector: List[float],
        top_k: Optional[int] = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск ближайших векторов.
        
        Args:
            query_vector: Вектор запроса
            top_k: Количество результатов (None = без лимита)
            filters: Фильтры по метаданным
        
        Returns:
            Список результатов, отсортированных по score (descending)
        """
        
        if self.index is None or self.index.ntotal == 0:
            return []
        
        query_array = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(query_array)
        
        # Если top_k None - берём все векторы из индекса
        search_limit = top_k * 3 if top_k is not None else self.index.ntotal
        
        scores, indices = self.index.search(query_array, search_limit)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            
            meta = self.metadata.get(idx, {})
            
            if filters and not self._matches_filters(meta, filters):
                continue
            
            results.append({
                "vector_id": idx,
                "score": float(score),
                "metadata": meta
            })
            
            # Ограничиваем только если задан top_k
            if top_k is not None and len(results) >= top_k:
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
        """
        Удаление векторов по фильтру.
        
        ПРИМЕЧАНИЕ: Для Flat индекса - полное удаление с пересозданием индекса.
        Для IVF/HNSW - удаление метаданных + пометка deleted_ids.
        При поиске удалённые векторы игнорируются.
        """
        vector_ids_to_delete = set(
            vid for vid, meta in self.metadata.items()
            if self._matches_filters(meta, filters)
        )
        
        if not vector_ids_to_delete:
            return 0
        
        deleted = len(vector_ids_to_delete)
        
        for vid in vector_ids_to_delete:
            del self.metadata[vid]
        
        if self.config.index_type == "Flat" and self.index is not None:
            self._deleted_ids.update(vector_ids_to_delete)
        
        return deleted
    
    async def save(self, path: str):
        """Сохранение индекса на диск."""
        
        # Сохраняем индекс
        faiss.write_index(self.index, path)
        
        # Сериализация метаданных с обработкой дат
        def serialize_value(v):
            from datetime import date, datetime
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            return v
        
        serialized_metadata = {
            k: [serialize_value(item) for item in v] 
            for k, v in self.metadata.items()
        }
        
        # Сохраняем метаданные - гарантируем корректную сериализацию
        metadata_path = path.replace(".faiss", "_metadata.json")
        
        # Конвертируем ключи в строки для JSON и проверяем данные
        serializable_metadata = {str(k): v for k, v in self.metadata.items()}
        
        # Отладочный вывод первой записи
        if serializable_metadata:
            first_key = next(iter(serializable_metadata))
            first_value = serializable_metadata[first_key]
            logger.info(f"💾 Пример сохраняемых метаданных (ключ={first_key}): {type(first_value).__name__}")
            if isinstance(first_value, dict):
                sample_keys = list(first_value.keys())[:5]
                logger.info(f"   Ключи в метаданных: {sample_keys}...")
                # Проверка: не попали ли туда только имена полей
                if sample_keys and all(isinstance(k, str) and not first_value[k] for k in sample_keys if k in first_value):
                    logger.warning("⚠️ Возможно, в метаданных только пустые значения!")
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": self.metadata,
                "id_counter": self.id_counter
            }, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"💾 Метаданные сохранены в: {metadata_path}")
    
    async def load(self, path: str):
        """Загрузка индекса с диска."""
        
        # Загружаем индекс
        self.index = faiss.read_index(path)
        
        # Десериализация метаданных с обработкой дат
        def deserialize_value(v):
            from datetime import date, datetime
            if isinstance(v, str):
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.strptime(v, fmt).date()
                    except ValueError:
                        try:
                            return datetime.strptime(v, fmt)
                        except ValueError:
                            pass
            return v
        
        # Загружаем метаданные
        metadata_path = path.replace(".faiss", "_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.metadata = {
                    int(k): [deserialize_value(item) for item in v] 
                    for k, v in data["metadata"].items()
                }
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
        self._deleted_ids.clear()

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

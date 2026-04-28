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
    - Flat (IndexFlatIP): точный поиск, 100% recall, рекомендуется для старта
    - IVF (IndexIVFFlat): инвертированный файл, быстрее для больших данных
    - HNSW (IndexHNSWFlat): графовый, очень быстро, больше памяти

    ВАЖНО: Для косинусного сходства все индексы используют Inner Product (IP)
    с обязательной L2-нормализацией векторов через faiss.normalize_L2().
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
        """Инициализация индекса в зависимости от конфигурации."""
        index_type = self.config.index_type

        if index_type == "Flat":
            # Flat index - точный поиск, 100% recall
            self.index = faiss.IndexFlatIP(self.dimension)

        elif index_type == "IVF":
            # IVF index - для больших данных (10k+ векторов)
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(
                quantizer,
                self.dimension,
                self.config.nlist,
                faiss.METRIC_INNER_PRODUCT
            )

        elif index_type == "HNSW":
            # HNSW index - очень быстро, требует больше памяти
            # M=32 — стандарт (количество связей на уровне)
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)
            self.index.hnsw.efConstruction = self.config.hnsw_ef_construction
            self.index.hnsw.efSearch = self.config.hnsw_ef_search

        else:
            raise ValueError(f"Unknown index type: {index_type}")

    async def _ensure_trained(self, vectors_array: np.ndarray):
        """Обучение индекса если нужно (для IVF)."""
        if self.config.index_type == "IVF" and not self.index.is_trained:
            if len(vectors_array) < self.config.nlist:
                raise ValueError(
                    f"Для обучения IVF нужно минимум {self.config.nlist} векторов, "
                    f"получено {len(vectors_array)}"
                )
            self.index.train(vectors_array)
    
    async def add(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> List[int]:
        """Добавление векторов в индекс."""
        if not vectors:
            return []

        # Конвертируем в numpy array (обязательно contiguous для FAISS)
        vectors_array = np.ascontiguousarray(np.array(vectors, dtype=np.float32))

        # Нормализуем для косинусного сходства (IP = косинус при нормализации)
        faiss.normalize_L2(vectors_array)

        # Обучаем индекс если нужно (для IVF)
        await self._ensure_trained(vectors_array)

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
        top_k: Optional[int] = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск ближайших векторов.

        Args:
            query_vector: Вектор запроса
            top_k: Количество результатов (если None — все)
            filters: Фильтры по метаданным

        Returns:
            Список результатов, отсортированных по score (descending)
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Обязательная нормализация запроса
        query_array = np.ascontiguousarray(np.array([query_vector], dtype=np.float32))
        faiss.normalize_L2(query_array)

        # Лимит поиска: либо top_k, либо все векторы
        search_limit = top_k if top_k is not None else self.index.ntotal

        scores, indices = self.index.search(query_array, search_limit)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                break  # FAISS возвращает -1 для "пустых" результатов

            # Пропускаем удалённые векторы
            if int(idx) in self._deleted_ids:
                continue

            meta = self.metadata.get(int(idx), {})

            # Пропускаем если метаданные пустые (вектор был удалён)
            if not meta:
                continue

            # Фильтрация по метаданным (если заданы)
            if filters and not self._matches_filters(meta, filters):
                continue

            results.append({
                "score": float(score),
                "metadata": meta
            })

            # Если top_k задан — ограничиваем
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

        ВАЖНО: FAISS не поддерживает удаление напрямую.
        - Для всех типов: удаляем метаданные + помечаем в _deleted_ids
        - При поиске удалённые векторы игнорируются (проверка в search())
        - Для полной очистки используйте rebuild_index()
        """
        vector_ids_to_delete = set(
            vid for vid, meta in self.metadata.items()
            if self._matches_filters(meta, filters)
        )

        if not vector_ids_to_delete:
            return 0

        deleted = len(vector_ids_to_delete)

        for vid in vector_ids_to_delete:
            if vid in self.metadata:
                del self.metadata[vid]

        # Помечаем как удалённые (для всех типов индексов)
        self._deleted_ids.update(vector_ids_to_delete)

        return deleted
    
    async def save(self, path: str):
        """Сохранение индекса на диск."""
        if self.index is None:
            raise ValueError("Индекс не инициализирован. Вызовите initialize() перед save().")

        # Путь к метаданным (рядом с индексом)
        metadata_path = path.replace(".faiss", "_metadata.json")

        # Сохраняем индекс
        faiss.write_index(self.index, path)

        # Сериализация метаданных с обработкой дат
        def serialize_value(v):
            from datetime import date, datetime
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            return v

        # Сериализуем метаданные для JSON (исключая удалённые)
        serializable_metadata = {
            k: serialize_value(v) if isinstance(v, (date, datetime)) else v
            for k, v in self.metadata.items()
            if int(k) not in self._deleted_ids
        }

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
                "metadata": serializable_metadata,
                "id_counter": self.id_counter
            }, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"💾 Индекс и метаданные сохранены: {path}")
    
    async def load(self, path: str):
        """Загрузка индекса с диска."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Файл индекса не найден: {path}")

        # Загружаем индекс
        self.index = faiss.read_index(path)

        # Загружаем метаданные
        metadata_path = path.replace(".faiss", "_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)

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

                self.metadata = {
                    int(k): deserialize_value(v) if isinstance(v, dict) else v
                    for k, v in data["metadata"].items()
                }
                self.id_counter = data.get("id_counter", 0)

                # Восстанавливаем список удалённых ID
                self._deleted_ids = set(
                    int(k) for k in data["metadata"].keys()
                    if int(k) not in self.metadata
                )
        else:
            self.metadata = {}
            self.id_counter = 0
            self._deleted_ids = set()
    
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
        Перестроить индекс с полной очисткой удалённых векторов.

        Для всех типов индексов:
        1. Собирает все активные векторы и метаданные
        2. Создаёт новый индекс с тем же типом
        3. Переучивает (для IVF) и добавляет данные заново
        4. Очищает _deleted_ids

        Returns:
            True если перестроение прошло успешно
        """
        try:
            # Собираем все активные векторы и метаданные
            active_items = [
                (idx, meta) for idx, meta in self.metadata.items()
                if int(idx) not in self._deleted_ids
            ]

            if not active_items:
                # Если данных нет — просто инициализируем пустой индекс
                await self.initialize()
                self.metadata = {}
                self.id_counter = 0
                self._deleted_ids.clear()
                return True

            # Временно сохраняем для переиндексации
            # ВАЖНО: Для пересоздания нам нужны векторы, но FAISS не даёт
            # их достать обратно. Поэтому rebuild_index требует, чтобы
            # векторы были восстановлены извне (например, из БД).
            # Этот метод — заглушка для совместимости.
            logger.warning(
                "rebuild_index() требует внешней реализации: "
                "FAISS не позволяет извлечь векторы обратно из индекса. "
                "Для полной перестройки нужно заново добавить данные через add()."
            )
            return False

        except Exception as e:
            logger.error(f"Ошибка при перестроении индекса: {e}")
            return False

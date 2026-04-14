"""
TempIndexManager — in-memory FAISS для семантического поиска внутри сессии.

ОТВЕТСТВЕННОСТЬ:
- Создание временного FAISS индекса из чанков
- Семантический поиск (top-k релевантных чанков)
- Автоматическая очистка через TTL (15-30 минут)
- Изоляция на уровне сессии (никакого глобального состояния)

НЕ ОТВЕТСТВЕННОСТЬ:
- Персистентное хранение (файлы не пишутся)
- Индексация больших данных (это FAISSProvider)
- Генерация эмбеддингов (делается извне)

АРХИТЕКТУРА:
- Легковесная обёртка над FAISS (in-memory only)
- Принимает готовые эмбеддинги или генерирует через executor
- Автоматически удаляется через TTL или при явном вызове cleanup()
- Session-scoped: один индекс = одна сессия агента

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
>>> index = TempIndexManager(session_id="session_123")
>>> await index.initialize_with_chunks(chunks, embedding_model)
>>> results = await index.search("вопрос", top_k=5)
>>> await index.cleanup()  # или подождать TTL
"""
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None


class TempIndexManager:
    """
    Временный in-memory FAISS индекс для сессионного поиска.

    ЖИЗНЕННЫЙ ЦИКЛ:
    1. create() → инициализация пустого индекса
    2. add_chunks() → добавление чанков с эмбеддингами
    3. search() → семантический поиск (top-k)
    4. cleanup() → освобождение памяти (или автоматический по TTL)

    АРХИТЕКТУРА:
    - In-memory only (ничего не пишет на диск)
    - Dimension настраивается (по умолчанию 384 — all-MiniLM-L6-v2)
    - TTL по умолчанию 30 минут
    - Использует FAISS IndexFlatIP (точное сходство, нормализованное)

    EXAMPLE:
    >>> index = TempIndexManager(session_id="sess_123")
    >>> index.create(dimension=384)
    >>> await index.add_chunks(chunks, get_embeddings)
    >>> results = await index.search("какие продажи?", top_k=5)
    >>> index.cleanup()
    """

    def __init__(
        self,
        session_id: str,
        ttl_minutes: int = 30
    ):
        """
        Инициализация менеджера.

        ARGS:
        - session_id: str — идентификатор сессии (для логирования)
        - ttl_minutes: int — время жизни индекса в минутах

        EXAMPLE:
        >>> index = TempIndexManager(session_id="session_123", ttl_minutes=15)
        """
        self.session_id = session_id
        self.ttl_seconds = ttl_minutes * 60
        self.index = None
        self.dimension = 0
        self.chunks_metadata: List[Dict[str, Any]] = []
        self.created_at = time.time()
        self._cleanup_task = None
        self._is_initialized = False

    def create(self, dimension: int = 384) -> bool:
        """
        Создание пустого индекса.

        ARGS:
        - dimension: int — размерность эмбеддингов (384 для MiniLM)

        RETURNS:
        - bool: True если создан успешно

        EXAMPLE:
        >>> index = TempIndexManager("sess_1")
        >>> index.create(dimension=384)
        True
        """
        if not FAISS_AVAILABLE:
            raise ImportError(
                "FAISS не установлен. Установите: pip install faiss-cpu"
            )

        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self._is_initialized = True

        # Запускаем автоматическую очистку по TTL
        self._cleanup_task = asyncio.create_task(self._auto_cleanup())

        return True

    async def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embedding_fn,
        batch_size: int = 100
    ) -> int:
        """
        Добавление чанков в индекс с генерацией эмбеддингов.

        АРХИТЕКТУРА:
        1. Генерирует эмбеддинги для каждого чанка
        2. Нормализует векторы
        3. Добавляет в FAISS
        4. Сохраняет метаданные чанков

        ARGS:
        - chunks: List[Dict] — чанки от TextChunker
        - embedding_fn: Callable — функция для генерации эмбеддингов
          (принимает List[str], возвращает List[List[float]])
        - batch_size: int — размер батча для генерации

        RETURNS:
        - int: количество добавленных чанков

        EXAMPLE:
        >>> async def get_embeddings(texts):
        ...     return await model.encode(texts)
        >>> count = await index.add_chunks(chunks, get_embeddings)
        >>> count
        15
        """
        if not self._is_initialized:
            raise RuntimeError("Индекс не создан. Вызовите create() сначала.")

        if not chunks:
            return 0

        # Генерируем эмбеддинги батчами
        all_embeddings = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk["content"] for chunk in batch]
            embeddings = await _call_embedding_fn(texts, embedding_fn)
            all_embeddings.extend(embeddings)

        if not all_embeddings:
            return 0

        # Конвертируем в numpy и нормализуем
        vectors_array = np.array(all_embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors_array)

        # Добавляем в FAISS
        self.index.add(vectors_array)

        # Сохраняем метаданные
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {}).copy()
            metadata.update({
                "chunk_id": chunk.get("chunk_id", i),
                "start_char": chunk.get("start_char", 0),
                "end_char": chunk.get("end_char", 0),
                "content_length": len(chunk.get("content", ""))
            })
            self.chunks_metadata.append(metadata)

        self._is_initialized = True
        return len(chunks)

    async def search(
        self,
        query: str,
        embedding_fn,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Семантический поиск по индексу.

        АРХИТЕКТУРА:
        1. Генерирует эмбеддинг запроса
        2. Нормализует вектор
        3. Ищет top-k в FAISS
        4. Возвращает чанки с score

        ARGS:
        - query: str — вопрос пользователя
        - embedding_fn: Callable — функция для генерации эмбеддинга запроса
        - top_k: int — количество результатов

        RETURNS:
        - List[Dict] — релевантные чанки с оценками:
          [{"content": "...", "score": 0.85, "metadata": {...}}, ...]

        EXAMPLE:
        >>> results = await index.search("какие продажи в январе?", top_k=3)
        >>> results[0]["content"]
        "Продажи в январе составили..."
        """
        if not self._is_initialized or not self.chunks_metadata:
            return []

        # Генерируем эмбеддинг запроса
        query_embedding = await _call_embedding_fn([query], embedding_fn)
        if not query_embedding:
            return []

        # Нормализуем и ищем
        query_vector = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_vector)

        # Поиск (возвращает distances и indices)
        k = min(top_k, len(self.chunks_metadata))
        distances, indices = self.index.search(query_vector, k)

        # Формируем результаты
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # FAISS возвращает -1 если не нашёл достаточно
                continue

            metadata = self.chunks_metadata[idx]
            # score — косинусное сходство (0..1 после нормализации)
            score = float(distances[0][i])

            # Восстанавливаем content из метаданных или берём из оригинала
            results.append({
                "content": metadata.get("content", ""),
                "score": round(score, 4),
                "chunk_id": metadata.get("chunk_id", idx),
                "metadata": {k: v for k, v in metadata.items() if k != "content"}
            })

        return results

    async def count(self) -> int:
        """Количество векторов в индексе."""
        if not self.index:
            return 0
        return self.index.ntotal

    async def cleanup(self) -> None:
        """
        Очистка индекса и освобождение памяти.

        ВАЖНО: Вызывается автоматически по TTL или вручную.
        После вызова индекс нельзя использовать — нужно создавать новый.

        EXAMPLE:
        >>> await index.cleanup()
        >>> # или подождать TTL — очистится автоматически
        """
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self.index = None
        self.chunks_metadata.clear()
        self._is_initialized = False

    async def _auto_cleanup(self) -> None:
        """Автоматическая очистка по TTL."""
        try:
            await asyncio.sleep(self.ttl_seconds)
            await self.cleanup()
        except asyncio.CancelledError:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики индекса.

        RETURNS:
        - Dict со статистикой

        EXAMPLE:
        >>> index.get_stats()
        {'session_id': 'sess_1', 'vectors': 15, 'age_seconds': 120}
        """
        return {
            "session_id": self.session_id,
            "vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "age_seconds": round(time.time() - self.created_at, 2),
            "ttl_seconds": self.ttl_seconds,
            "is_initialized": self._is_initialized
        }


async def _call_embedding_fn(
    texts: List[str],
    embedding_fn
) -> List[List[float]]:
    """
    Безопасный вызов функции эмбеддинга.

    ARGS:
    - texts: List[str] — тексты для эмбеддинга
    - embedding_fn: Callable или async Callable

    RETURNS:
    - List[List[float]] — эмбеддинги
    """
    try:
        # Пробуем как async
        result = await embedding_fn(texts)
        return result
    except TypeError:
        # Fallback: синхронная функция
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: embedding_fn(texts))
        return result
    except Exception as e:
        # В случае ошибки — возвращаем пустой список
        print(f"Ошибка генерации эмбеддингов: {e}")
        return []


class TempIndexManagerRegistry:
    """
    Реестр временных индексов (session-scoped).

    АРХИТЕКТУРА:
    - Хранит активные индексы по session_id
    - Автоматически удаляет старые
    - Предотвращает утечки памяти

    EXAMPLE:
    >>> registry = TempIndexManagerRegistry()
    >>> index = registry.get_or_create("session_123")
    >>> ... используем индекс ...
    >>> registry.cleanup_session("session_123")
    """

    def __init__(self, max_age_minutes: int = 60):
        self._indexes: Dict[str, TempIndexManager] = {}
        self._max_age_minutes = max_age_minutes

    def get_or_create(
        self,
        session_id: str,
        ttl_minutes: int = 30
    ) -> TempIndexManager:
        """
        Получить или создать индекс для сессии.

        ARGS:
        - session_id: str — идентификатор сессии
        - ttl_minutes: int — время жизни

        RETURNS:
        - TempIndexManager

        EXAMPLE:
        >>> index = registry.get_or_create("session_123")
        """
        if session_id not in self._indexes:
            index = TempIndexManager(session_id, ttl_minutes)
            self._indexes[session_id] = index
        return self._indexes[session_id]

    def get(self, session_id: str) -> Optional[TempIndexManager]:
        """Получить индекс без создания."""
        return self._indexes.get(session_id)

    def cleanup_session(self, session_id: str) -> None:
        """Удалить индекс сессии."""
        if session_id in self._indexes:
            index = self._indexes.pop(session_id)
            # cleanup вызывается асинхронно внутри index

    async def cleanup_all_expired(self) -> int:
        """
        Очистка всех истёкших индексов.

        RETURNS:
        - int: количество очищенных индексов
        """
        expired = []
        for session_id, index in self._indexes.items():
            if time.time() - index.created_at > index.ttl_seconds:
                expired.append(session_id)

        for session_id in expired:
            await self._indexes[session_id].cleanup()
            del self._indexes[session_id]

        return len(expired)

    def get_active_count(self) -> int:
        """Количество активных индексов."""
        return len(self._indexes)

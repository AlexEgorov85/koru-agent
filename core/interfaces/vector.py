"""
Интерфейс для векторного поиска.

Определяет контракт для всех реализаций (FAISS, и т.д.).
"""

from typing import Protocol, List, Optional, Dict, Any
import numpy as np


class VectorInterface(Protocol):
    """
    Интерфейс для векторного поиска.

    АБСТРАКЦИЯ: Определяет что нужно для векторного поиска.
    РЕАЛИЗАЦИИ: FAISSProvider.
    """

    async def initialize(self) -> None:
        """Инициализация провайдера."""
        ...

    async def add(
        self,
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Добавить векторы в индекс.

        ARGS:
        - vectors: Матрица векторов (n x d)
        - metadata: Метаданные для каждого вектора
        """
        ...

    async def search(
        self,
        query: np.ndarray,
        top_k: int = 5
    ) -> tuple:
        """
        Поиск ближайших векторов.

        ARGS:
        - query: Вектор запроса
        - top_k: Количество результатов

        RETURNS:
        - (distances, indices) кортеж
        """
        ...

    async def save(self, path: str) -> None:
        """
        Сохранить индекс в файл.

        ARGS:
        - path: Путь к файлу
        """
        ...

    async def load(self, path: str) -> None:
        """
        Загрузить индекс из файла.

        ARGS:
        - path: Путь к файлу
        """
        ...

    async def shutdown(self) -> None:
        """Завершение работы провайдера."""
        ...

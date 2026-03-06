"""
Интерфейс для векторного поиска.

Определяет контракт для всех реализаций векторных хранилищ (FAISS, Chroma, QDrant, и т.д.).
"""

from typing import Protocol, List, Dict, Any, Optional


class VectorInterface(Protocol):
    """
    Интерфейс для векторного поиска.

    АБСТРАКЦИЯ: Определяет что нужно для семантического поиска.
    РЕАЛИЗАЦИИ: FAISSProvider, ChromaProvider, MockVectorProvider.
    """

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
        ...

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
        ...

    async def delete(self, ids: List[str]) -> int:
        """
        Удалить документы по ID.

        ARGS:
        - ids: Список ID для удаления

        RETURNS:
        - Количество удалённых документов
        """
        ...

    async def rebuild_index(self) -> bool:
        """
        Перестроить индекс (после массового добавления).

        RETURNS:
        - True если успешно
        """
        ...

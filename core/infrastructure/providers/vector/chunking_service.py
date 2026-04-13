"""
ChunkingService — единая точка входа для разбиения текста на чанки.

Инстанциируется из конфигурации, делегирует стратегию через ChunkingFactory.

ИСПОЛЬЗОВАНИЕ:
    # Из конфигурации
    service = ChunkingService.from_config(vs_config.chunking)
    chunks = await service.split(text, document_id="book_1")

    # Вручную
    service = ChunkingService(strategy=TextChunkingStrategy(chunk_size=500))
    chunks = await service.split(text, document_id="doc_1")
"""

from typing import Optional, Dict, List, Any
from core.config.vector_config import ChunkingConfig
from core.models.types.vector_types import VectorChunk
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy
from core.infrastructure.providers.vector.chunking_factory import ChunkingFactory


class ChunkingService:
    """
    Сервис разбиения текста на чанки.

    Обёртка над IChunkingStrategy с единым API.
    """

    def __init__(self, strategy: IChunkingStrategy):
        """
        Args:
            strategy: Экземпляр стратегии разбиения
        """
        self._strategy = strategy

    @classmethod
    def from_config(cls, config: ChunkingConfig) -> "ChunkingService":
        """
        Создать сервис из конфигурации.

        Args:
            config: ChunkingConfig из vector_config

        Returns:
            Настроенный ChunkingService
        """
        strategy = ChunkingFactory.create(
            strategy_type=config.strategy,
            config=config,
        )
        return cls(strategy=strategy)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ChunkingService":
        """
        Создать сервис из словаря.

        Args:
            config_dict: Словарь с параметрами:
                - strategy_type (str): тип стратегии
                - chunk_size (int)
                - chunk_overlap (int)
                - min_chunk_size (int)
                - separators (list)

        Returns:
            Настроенный ChunkingService
        """
        strategy_type = config_dict.pop("strategy_type", "text")
        strategy = ChunkingFactory.create(
            strategy_type=strategy_type,
            **config_dict,
        )
        return cls(strategy=strategy)

    async def split(
        self,
        content: str,
        document_id: str,
        metadata: Optional[Dict] = None,
    ) -> List[VectorChunk]:
        """
        Разбиение текста на чанки.

        Args:
            content: Текст для разбиения
            document_id: ID документа (для генерации chunk_id)
            metadata: Дополнительные метаданные (добавляются к каждому чанку)

        Returns:
            Список VectorChunk
        """
        return await self._strategy.split(content, document_id, metadata)

    def get_config(self) -> dict:
        """Получить конфигурацию текущей стратегии."""
        return self._strategy.get_config()

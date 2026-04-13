"""
Фабрика стратегий chunking.

Создаёт стратегию разбиения по типу из конфигурации.
В данный момент поддерживает только «text» — остальные
стратегии (semantic, hybrid) могут быть добавлены позже
без изменения API фабрики.
"""

from typing import Any, Dict
from core.config.vector_config import ChunkingConfig
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy
from core.infrastructure.providers.vector.text_chunking_strategy import (
    TextChunkingStrategy,
    DEFAULT_SEPARATORS,
)


class ChunkingFactory:
    """Фабрика стратегий разбиения текста."""

    _registry: Dict[str, type[IChunkingStrategy]] = {
        "text": TextChunkingStrategy,
    }

    @classmethod
    def register(cls, strategy_type: str, strategy_class: type[IChunkingStrategy]) -> None:
        """
        Зарегистрировать новую стратегию.

        Позволяет добавлять стратегии без изменения кода фабрики:
            ChunkingFactory.register("semantic", SemanticChunkingStrategy)

        Args:
            strategy_type: Ключ стратегии (например, "semantic")
            strategy_class: Класс стратегии
        """
        cls._registry[strategy_type] = strategy_class

    @classmethod
    def create(
        cls,
        strategy_type: str = "text",
        config: ChunkingConfig | None = None,
        **kwargs: Any,
    ) -> IChunkingStrategy:
        """
        Создать стратегию разбиения.

        Args:
            strategy_type: Тип стратегии ("text", ...)
            config: Конфигурация chunking (если None — kwargs)
            **kwargs: Дополнительные параметры (переопределяют config)

        Returns:
            Экземпляр IChunkingStrategy

        Raises:
            ValueError: если strategy_type не зарегистрирован
        """
        if strategy_type not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Неизвестная стратегия chunking: '{strategy_type}'. "
                f"Доступные: {available}"
            )

        strategy_class = cls._registry[strategy_type]

        if config is not None:
            # Собираем параметры из ChunkingConfig
            params: Dict[str, Any] = {
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap,
                "min_chunk_size": config.min_chunk_size,
                "separators": config.separators if config.separators else DEFAULT_SEPARATORS,
            }
            # kwargs имеют приоритет над config
            params.update(kwargs)
            return strategy_class(**params)

        # Без config — используем kwargs напрямую
        return strategy_class(**kwargs) if kwargs else strategy_class()

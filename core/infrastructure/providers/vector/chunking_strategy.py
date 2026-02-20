"""
Интерфейс стратегии разбиения на чанки.

Позволяет добавлять новые стратегии без изменения кода:
- TextChunkingStrategy (по тексту)
- SemanticChunkingStrategy (по смыслу)
- HybridChunkingStrategy (комбо)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from core.models.types.vector_types import VectorChunk


class IChunkingStrategy(ABC):
    """
    Интерфейс стратегии разбиения.
    
    Пример использования:
        strategy = TextChunkingStrategy(chunk_size=500, chunk_overlap=50)
        chunks = await strategy.split(text, document_id="doc_1")
    """
    
    @abstractmethod
    async def split(
        self,
        content: str,
        document_id: str,
        metadata: Optional[Dict] = None
    ) -> List[VectorChunk]:
        """
        Разбиение текста на чанки.
        
        Args:
            content: Текст для разбиения
            document_id: ID документа
            metadata: Дополнительные метаданные
        
        Returns:
            Список VectorChunk
        """
        pass
    
    @abstractmethod
    def get_config(self) -> dict:
        """
        Получить конфигурацию стратегии.
        
        Returns:
            dict с конфигурацией
        """
        pass

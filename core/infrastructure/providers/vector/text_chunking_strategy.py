"""
Стратегия разбиения по тексту.

Параметры:
- chunk_size: размер чанка
- chunk_overlap: перекрытие
- separators: разделители по приоритету
"""

from typing import List, Optional, Dict
from core.models.types.vector_types import VectorChunk
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy


class TextChunkingStrategy(IChunkingStrategy):
    """
    Разбиение по тексту (разделители, размер).
    
    Алгоритм:
    1. Разделить по заголовкам (\\n## )
    2. Разделить по абзацам (\\n\\n)
    3. Разделить по предложениям (. )
    4. Принудительное разбиение больших chunks
    5. Добавить перекрытие
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        separators: List[str] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.separators = separators or [
            "\n## ",
            "\n### ",
            "\n\n",
            "\n",
            ". ",
            "! ",
            "? ",
            " ",
            ""
        ]
    
    async def split(
        self,
        content: str,
        document_id: str,
        metadata: Optional[Dict] = None
    ) -> List[VectorChunk]:
        """Разбиение текста на чанки."""
        
        chunks = []
        
        # 1. Разделение по разделам (заголовки)
        sections = self._split_by_separator(content, "\n## ")
        
        chunk_index = 0
        for section in sections:
            # 2. Разделение по абзацам
            paragraphs = self._split_by_separator(section, "\n\n")
            
            for paragraph in paragraphs:
                # 3. Маленький абзац → один чанк
                if len(paragraph) <= self.chunk_size:
                    if len(paragraph) >= self.min_chunk_size:
                        chunks.append(self._create_chunk(
                            content=paragraph,
                            document_id=document_id,
                            index=chunk_index,
                            metadata=metadata
                        ))
                        chunk_index += 1
                else:
                    # 4. Большой абзац → разбить с перекрытием
                    sub_chunks = self._split_with_overlap(paragraph)
                    for sub_chunk in sub_chunks:
                        chunks.append(self._create_chunk(
                            content=sub_chunk,
                            document_id=document_id,
                            index=chunk_index,
                            metadata=metadata
                        ))
                        chunk_index += 1
        
        return chunks
    
    def _split_by_separator(self, text: str, separator: str) -> List[str]:
        """Разделение по разделителю."""
        parts = text.split(separator)
        # Добавляем разделитель обратно (кроме последнего)
        result = []
        for i, part in enumerate(parts):
            if part.strip():
                if i < len(parts) - 1:
                    result.append(part + separator)
                else:
                    result.append(part)
        return result
    
    def _split_with_overlap(self, text: str) -> List[str]:
        """Разбиение текста с перекрытием."""
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Если это не последний чанк
            if end < len(text):
                # Ищем лучшую точку разрыва
                best_break = self._find_best_break(text[start:end])
                if best_break > 0:
                    end = start + best_break
            
            chunk = text[start:end].strip()
            if chunk:  # Не добавлять пустые чанки
                chunks.append(chunk)
            
            # Следующий чанк начинается с перекрытием
            start = end - self.chunk_overlap
            if start < 0:
                start = 0
        
        return chunks
    
    def _find_best_break(self, text: str) -> int:
        """Поиск лучшей точки разрыва (не резать слова)."""
        
        # 1. Ищем пробел в конце (80-100% chunk_size)
        min_pos = int(len(text) * 0.8)
        last_space = text.rfind(' ', min_pos)
        if last_space > 0:
            return last_space
        
        # 2. Ищем точку
        last_dot = text.rfind('.')
        if last_dot > int(len(text) * 0.5):
            return last_dot + 1
        
        # 3. По умолчанию режем посередине
        return len(text)
    
    def _create_chunk(
        self,
        content: str,
        document_id: str,
        index: int,
        metadata: Optional[Dict]
    ) -> VectorChunk:
        """Создание VectorChunk."""
        
        chunk_id = f"{document_id}_chunk_{index}"
        
        chunk_metadata = {
            "chunk_size": len(content),
            "has_overlap": self.chunk_overlap > 0,
            "overlap_chars": self.chunk_overlap,
            **(metadata or {})
        }
        
        return VectorChunk(
            id=chunk_id,
            document_id=document_id,
            content=content,
            metadata=chunk_metadata,
            index=index
        )
    
    def get_config(self) -> dict:
        """Получить конфигурацию."""
        return {
            "type": "text",
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "min_chunk_size": self.min_chunk_size,
            "separators": self.separators
        }

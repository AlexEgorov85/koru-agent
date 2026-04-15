"""
ChunkingService — сервис разбиения данных на чанки.

ПОДДЕРЖИВАЕТ:
- Текст (str) → текстовые чанки
- Строки (List[Dict]) → чанки-таблицы
- Конфигурация из ChunkingConfig
- Стратегии через ChunkingFactory

ИСПОЛЬЗОВАНИЕ:
    # Из конфигурации
    service = ChunkingService.from_config(vs_config.chunking)
    chunks = await service.split_text("текст...", document_id="doc_1")

    # Строки (разбиение по количеству)
    chunks = service.chunk_rows([{"col": 1}, ...], chunk_size=50)

    # Автоматически
    chunks = service.chunk(data)
"""
from typing import Optional, Dict, List, Any, Union
from core.config.vector_config import ChunkingConfig
from core.models.types.vector_types import VectorChunk
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy
from core.infrastructure.providers.vector.chunking_factory import ChunkingFactory


class ChunkingService:
    DEFAULT_CHUNK_SIZE_CHARS = 4000
    DEFAULT_CHUNK_SIZE_ROWS = 50

    def __init__(
        self,
        strategy: Optional[IChunkingStrategy] = None,
        chunk_size_chars: int = DEFAULT_CHUNK_SIZE_CHARS,
        chunk_size_rows: int = DEFAULT_CHUNK_SIZE_ROWS
    ):
        self._strategy = strategy
        self.chunk_size_chars = chunk_size_chars
        self.chunk_size_rows = chunk_size_rows

    @classmethod
    def from_config(cls, config: ChunkingConfig) -> "ChunkingService":
        strategy = ChunkingFactory.create(
            strategy_type=config.strategy,
            config=config,
        )
        return cls(strategy=strategy)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ChunkingService":
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
        if self._strategy:
            return await self._strategy.split(content, document_id, metadata)
        return self._split_text_simple(content, document_id, metadata)

    async def split_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict] = None,
    ) -> List[VectorChunk]:
        return await self.split(text, document_id, metadata)

    def chunk(
        self,
        data: Any
    ) -> List[Dict[str, Any]]:
        if isinstance(data, str):
            return self.chunk_text(data)
        elif isinstance(data, list):
            return self.chunk_rows(data)
        else:
            raise ValueError(f"Неподдерживаемый тип данных: {type(data)}")

    def chunk_text(
        self,
        text: str,
        chunk_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not text:
            return []

        size = chunk_size or self.chunk_size_chars

        if len(text) <= size:
            return [{
                "content": text,
                "chunk_id": 0,
                "char_start": 0,
                "char_end": len(text),
                "char_count": len(text),
                "type": "text"
            }]

        chunks = []
        for i in range(0, len(text), size):
            chunk_text = text[i:i + size]
            chunks.append({
                "content": chunk_text,
                "chunk_id": len(chunks),
                "char_start": i,
                "char_end": min(i + size, len(text)),
                "char_count": len(chunk_text),
                "type": "text"
            })

        return chunks

    def chunk_rows(
        self,
        rows: List[Dict[str, Any]],
        chunk_size: Optional[int] = None,
        max_chunk_chars: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not rows:
            return []

        headers = list(rows[0].keys())

        if chunk_size is None:
            chunk_size = self._calculate_rows_per_chunk(rows, headers, max_chunk_chars)

        if len(rows) <= chunk_size:
            return [{
                "content": self._rows_to_text(rows, headers),
                "chunk_id": 0,
                "row_start": 0,
                "row_end": len(rows),
                "row_count": len(rows),
                "headers": headers,
                "type": "rows",
                "avg_row_chars": self._estimate_row_chars(rows[0], headers)
            }]

        chunks = []

        for i in range(0, len(rows), chunk_size):
            chunk_rows = rows[i:i + chunk_size]
            chunks.append({
                "content": self._rows_to_text(chunk_rows, headers),
                "chunk_id": len(chunks),
                "row_start": i,
                "row_end": i + len(chunk_rows),
                "row_count": len(chunk_rows),
                "headers": headers,
                "type": "rows",
                "avg_row_chars": self._estimate_row_chars(chunk_rows[0] if chunk_rows else rows[0], headers)
            })

        return chunks

    def _calculate_rows_per_chunk(
        self,
        rows: List[Dict[str, Any]],
        headers: List[str],
        max_chunk_chars: Optional[int] = None
    ) -> int:
        """
        Расчёт оптимального количества строк на чанк.

        Алгоритм:
        1. Считаем средний размер строки в символах
        2. Учитываем размер заголовка
        3. Делим max_chunk_chars на avg_row_chars
        """
        if not rows:
            return self.chunk_size_rows

        target_chars = max_chunk_chars or self.chunk_size_chars
        avg_row_chars = self._estimate_row_chars(rows[0], headers)

        if avg_row_chars == 0:
            return self.chunk_size_rows

        rows_per_chunk = max(1, target_chars // avg_row_chars)

        min_rows = 10
        max_rows = self.chunk_size_rows * 2

        return max(min_rows, min(rows_per_chunk, max_rows))

    def _estimate_row_chars(self, row: Dict[str, Any], headers: List[str]) -> int:
        """
        Оценка размера строки в символах.

        Учитывает:
        - Длину значений
        - Разделители ( | )
        - Перенос строки
        """
        if not row:
            return 100

        total = sum(len(str(row.get(h, ""))) for h in headers)
        total += len(headers) * 3
        total += 2

        return max(total, 10)

    async def split_rows(
        self,
        rows: List[Dict[str, Any]],
        document_id: str,
        chunk_size_rows: Optional[int] = None,
        max_chunk_chars: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> List[VectorChunk]:
        if not rows:
            return []

        headers = list(rows[0].keys())

        if chunk_size_rows is None:
            chunk_size_rows = self._calculate_rows_per_chunk(rows, headers, max_chunk_chars)

        chunks = []

        for i in range(0, len(rows), chunk_size_rows):
            chunk_rows = rows[i:i + chunk_size_rows]
            chunks.append(VectorChunk(
                id=f"{document_id}_chunk_{len(chunks)}",
                document_id=document_id,
                content=self._rows_to_text(chunk_rows, headers),
                metadata={
                    **(metadata or {}),
                    "row_start": i,
                    "row_end": i + len(chunk_rows),
                    "row_count": len(chunk_rows),
                    "headers": headers,
                    "avg_row_chars": self._estimate_row_chars(chunk_rows[0] if chunk_rows else rows[0], headers)
                },
                index=len(chunks)
            ))

        return chunks

    def _rows_to_text(
        self,
        rows: List[Dict[str, Any]],
        headers: List[str]
    ) -> str:
        header_line = " | ".join(headers)
        separator = "|---" * len(headers)

        lines = [header_line, separator]
        for row in rows:
            values = [str(row.get(h, "")) for h in headers]
            lines.append(" | ".join(values))

        return "\n".join(lines)

    def _split_text_simple(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict] = None,
    ) -> List[VectorChunk]:
        chunk_size = self.chunk_size_chars
        chunks = []

        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i + chunk_size]
            chunks.append(VectorChunk(
                id=f"{document_id}_chunk_{len(chunks)}",
                document_id=document_id,
                content=chunk_text,
                metadata={**(metadata or {}), "char_start": i},
                index=len(chunks)
            ))

        return chunks

    def get_config(self) -> dict:
        if self._strategy:
            return self._strategy.get_config()
        return {
            "chunk_size_chars": self.chunk_size_chars,
            "chunk_size_rows": self.chunk_size_rows
        }

    def get_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not chunks:
            return {"total_chunks": 0}

        types = set(c.get("type", "unknown") for c in chunks)
        stats = {"total_chunks": len(chunks), "types": list(types)}

        if any(c.get("type") == "rows" for c in chunks):
            stats["total_rows"] = sum(c.get("row_count", 0) for c in chunks)

        if any(c.get("type") == "text" for c in chunks):
            stats["total_chars"] = sum(c.get("char_count", 0) for c in chunks)

        return stats

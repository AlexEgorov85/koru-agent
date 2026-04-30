"""
ChunkingService — сервис разбиения данных на чанки.

ПОДДЕРЖИВАЕТ:
- Текст (str) → текстовые чанки (символы или токены)
- Строки (List[Dict]) → чанки-таблицы
- Конфигурация из ChunkingConfig
- Стратегии через ChunkingFactory
- Токен-ориентированный чанкинг (через tiktoken)

ИСПОЛЬЗОВАНИЕ:
    # Из конфигурации
    service = ChunkingService.from_config(vs_config.chunking)
    chunks = await service.split_text("текст...", document_id="doc_1")

    # Строки (разбиение по количеству)
    chunks = service.chunk_rows([{"col": 1}, ...], chunk_size=50)

    # Автоматически
    chunks = service.chunk(data)

    # Токен-ориентированный чанкинг
    service = ChunkingService(use_tokens=True, model_name="gpt-4")
    chunks = service.chunk_text_tokens("текст...", max_tokens=2000)
"""
import os
from typing import Optional, Dict, List, Any, Union
from core.config.vector_config import ChunkingConfig
from core.models.types.vector_types import VectorChunk
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy
from core.infrastructure.providers.vector.chunking_factory import ChunkingFactory


# Ленивая загрузка tiktoken
def _get_tiktoken_encoder(model_name: str = "gpt-4"):
    """Получить tiktoken encoder с обработкой ошибок."""
    try:
        import tiktoken
        return tiktoken.encoding_for_model(model_name)
    except ImportError:
        return None
    except Exception:
        return None


def _estimate_chars_per_token(text_sample: str = "sample text") -> float:
    """Оценка среднего количества символов на токен для текста."""
    cyrillic = sum(1 for c in text_sample if '\u0400' <= c <= '\u04FF')
    ratio = cyrillic / max(len(text_sample), 1)
    if ratio > 0.3:
        return 2.2  # Русский текст плотнее
    return 3.5  # Английский/смешанный


class ChunkingService:
    DEFAULT_CHUNK_SIZE_CHARS = 4000
    DEFAULT_CHUNK_SIZE_ROWS = 50
    DEFAULT_MAX_TOKENS_PER_CHUNK = 2000
    DEFAULT_TOKEN_OVERLAP = 100  # токенов

    def __init__(
        self,
        strategy: Optional[IChunkingStrategy] = None,
        chunk_size_chars: int = DEFAULT_CHUNK_SIZE_CHARS,
        chunk_size_rows: int = DEFAULT_CHUNK_SIZE_ROWS,
        use_tokens: bool = False,
        model_name: str = "gpt-4",
        max_tokens_per_chunk: Optional[int] = None,
        token_overlap: Optional[int] = None,
    ):
        self._strategy = strategy
        self.chunk_size_chars = chunk_size_chars
        self.chunk_size_rows = chunk_size_rows
        self.use_tokens = use_tokens
        self.model_name = model_name
        self.max_tokens_per_chunk = max_tokens_per_chunk or self.DEFAULT_MAX_TOKENS_PER_CHUNK
        self.token_overlap = token_overlap or self.DEFAULT_TOKEN_OVERLAP

        self._token_encoder = None
        if self.use_tokens:
            self._token_encoder = _get_tiktoken_encoder(self.model_name)
            # Не сбрасываем use_tokens - проверка будет при чанкинге

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

        # Токен-ориентированный режим (проверяем encoder, а не флаг)
        if self._token_encoder is not None:
            return self.chunk_text_tokens(text)

        size = chunk_size or self.chunk_size_chars

        if len(text) <= size:
            return [{
                "content": text,
                "chunk_id": 0,
                "char_start": 0,
                "char_end": len(text),
                "char_count": len(text),
                "type": "text",
                "mode": "chars"
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
                "type": "text",
                "mode": "chars"
            })

        return chunks

    def chunk_text_tokens(
        self,
        text: str,
        max_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Разбиение текста по токенам с overlap.
        
        АРХИТЕКТУРА:
        - Использует tiktoken для точного подсчёта токенов
        - Сохраняет overlap в токенах (не символах)
        - Fallback к символам при отсутствии encoder
        
        ПАРАМЕТРЫ:
        - max_tokens: максимум токенов на чанк (по умолчанию self.max_tokens_per_chunk)
        - overlap_tokens: перекрытие в токенах (по умолчанию self.token_overlap)
        """
        if not text:
            return []

        if not self._token_encoder:
            # Fallback к символам
            return self.chunk_text(text)

        max_tok = max_tokens or self.max_tokens_per_chunk
        overlap_tok = overlap_tokens or self.token_overlap

        # Получаем токены
        tokens = self._token_encoder.encode(text)

        if len(tokens) <= max_tok:
            return [{
                "content": text,
                "chunk_id": 0,
                "token_start": 0,
                "token_end": len(tokens),
                "token_count": len(tokens),
                "char_count": len(text),
                "type": "text",
                "mode": "tokens",
                "model": self.model_name
            }]

        chunks = []
        start = 0
        chunk_id = 0

        while start < len(tokens):
            end = min(start + max_tok, len(tokens))

            # Декодируем токены обратно в текст
            chunk_tokens = tokens[start:end]
            chunk_text = self._token_encoder.decode(chunk_tokens)

            chunks.append({
                "content": chunk_text,
                "chunk_id": chunk_id,
                "token_start": start,
                "token_end": end,
                "token_count": len(chunk_tokens),
                "char_count": len(chunk_text),
                "type": "text",
                "mode": "tokens",
                "model": self.model_name
            })

            chunk_id += 1

            # Следующий чанк начинается с учётом overlap
            start = end - overlap_tok if end < len(tokens) else len(tokens)
            if start >= end:  # Защита от бесконечного цикла
                start = end

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
            "chunk_size_rows": self.chunk_size_rows,
            "use_tokens": self.use_tokens,
            "model_name": self.model_name,
            "max_tokens_per_chunk": self.max_tokens_per_chunk,
            "token_overlap": self.token_overlap,
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

            # Добавляем статистику по токенам, если режим токенов
            if any(c.get("mode") == "tokens" for c in chunks):
                stats["total_tokens"] = sum(c.get("token_count", 0) for c in chunks)
                stats["avg_tokens_per_chunk"] = stats["total_tokens"] / len(chunks)
                stats["token_mode"] = True
                # Показываем модель
                models = set(c.get("model", "") for c in chunks if c.get("mode") == "tokens")
                if models:
                    stats["token_model"] = list(models)[0]
            else:
                stats["token_mode"] = False

        return stats

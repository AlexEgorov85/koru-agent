"""
Стратегия рекурсивного разбиения текста по разделителям.

Алгоритм:
1. Рекурсивно делим по разделителям в порядке приоритета:
   заголовки → абзацы → предложения → слова → символы
2. Если кусок всё ещё > chunk_size — жёстко режем по размеру
3. Добавляем overlap: хвост предыдущего чанка дублируется в начало следующего

Параметры:
- chunk_size: максимальный размер чанка (символы)
- chunk_overlap: перекрытие между соседними чанками (символы)
- min_chunk_size: минимальный размер чанка (меньше — отбрасывается)
- separators: разделители по приоритету (от грубого к мелкому)
"""

from typing import List, Optional, Dict
from core.models.types.vector_types import VectorChunk
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy


# Разделители по умолчанию — от структурных к мелким
DEFAULT_SEPARATORS = [
    "\n## ",      # Заголовки H2
    "\n### ",     # Заголовки H3
    "\n#### ",    # Заголовки H4
    "\n\n",       # Абзацы
    "\n",         # Строки
    ". ",         # Предложения (точка)
    "! ",         # Восклицания
    "? ",         # Вопросы
    "; ",         # Точка с запятой
    "。 ",        # Японские/китайские предложения
    " ",          # Слова
    "—",          # Тире
    "-",          # Дефис
]


class TextChunkingStrategy(IChunkingStrategy):
    """
    Рекурсивное разбиение текста по разделителям.

    Не режет слова и предложения посередине — сначала ищет
    естественную границу (абзац, предложение), и только если
    не нашёл — жёстко по chunk_size.

    Пример использования:
        strategy = TextChunkingStrategy(chunk_size=500, chunk_overlap=50)
        chunks = await strategy.split(text, document_id="doc_1")
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        separators: Optional[List[str]] = None,
    ):
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be > 0, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be >= 0, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
            )
        if min_chunk_size <= 0:
            raise ValueError(f"min_chunk_size must be > 0, got {min_chunk_size}")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.separators = separators or DEFAULT_SEPARATORS

    # ──────────────────────────────────────────────
    # Публичный API (IChunkingStrategy)
    # ──────────────────────────────────────────────

    async def split(
        self,
        content: str,
        document_id: str,
        metadata: Optional[Dict] = None,
    ) -> List[VectorChunk]:
        """
        Разбиение текста на чанки.

        Алгоритм:
        1. Рекурсивное разбиение по разделителям
        2. Добавление overlap
        3. Создание VectorChunk
        """
        if not content or not content.strip():
            return []

        # Шаг 1: рекурсивное разбиение
        raw_pieces = self._recursive_split(content, depth=0)

        # Шаг 2: добавляем overlap
        pieces = self._apply_overlap(raw_pieces)

        # Шаг 3: создаём VectorChunk
        chunks: List[VectorChunk] = []
        for idx, piece in enumerate(pieces):
            stripped = piece.strip()
            if not stripped or len(stripped) < self.min_chunk_size:
                continue

            chunk_id = f"{document_id}_chunk_{idx}"
            chunk_meta = {
                "chunk_size": len(stripped),
                "has_overlap": self.chunk_overlap > 0 and idx > 0,
                "overlap_chars": self.chunk_overlap if self.chunk_overlap > 0 and idx > 0 else 0,
                **(metadata or {}),
            }

            chunks.append(VectorChunk(
                id=chunk_id,
                document_id=document_id,
                content=stripped,
                metadata=chunk_meta,
                index=idx,
            ))

        return chunks

    def get_config(self) -> dict:
        """Получить конфигурацию стратегии."""
        return {
            "type": "text",
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "min_chunk_size": self.min_chunk_size,
            "separators": self.separators,
        }

    # ──────────────────────────────────────────────
    # Рекурсивное разбиение
    # ──────────────────────────────────────────────

    def _recursive_split(self, text: str, depth: int) -> List[str]:
        """
        Рекурсивно делим текст по разделителям.

        На каждом уровне глубины пробуем свой разделитель.
        Если текст влезает в chunk_size — возвращаем как есть.
        Если разделители кончились — жёстко режем по chunk_size.
        """
        # База: текст помещается в один чанк
        if len(text) <= self.chunk_size:
            return [text] if len(text) >= self.min_chunk_size else []

        # База: разделители кончились → жёсткий split
        if depth >= len(self.separators):
            return self._hard_split(text)

        separator = self.separators[depth]

        # Если разделитель пустой (последний fallback), не сплитим
        if separator == "":
            return self._hard_split(text)

        parts = text.split(separator)

        # Если split не помог (одна часть) — идём глубже
        if len(parts) <= 1:
            return self._recursive_split(text, depth + 1)

        # Собираем результат, сохраняя разделитель в кусках
        result: List[str] = []
        current = ""

        for part in parts:
            candidate = current + separator + part if current else part

            if len(candidate) <= self.chunk_size:
                # Кусок влезает — аккумулируем
                current = candidate
            else:
                # Не влезает
                if current:
                    result.extend(self._recursive_split(current, depth + 1))
                # Если часть сама по себе > chunk_size — попробуем разбить её
                if len(part) > self.chunk_size:
                    result.extend(self._recursive_split(part, depth + 1))
                else:
                    current = part

        if current:
            result.extend(self._recursive_split(current, depth + 1))

        return result

    def _hard_split(self, text: str) -> List[str]:
        """
        Жёсткое разбиение по chunk_size с поиском лучшей точки разрыва.

        Старается не резать посередине слова — ищет ближайший пробел
        в диапазоне 80-100% от chunk_size.
        """
        if len(text) <= self.chunk_size:
            return [text] if len(text) >= self.min_chunk_size else []

        chunks: List[str] = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                # Последний кусок — берём весь остаток
                chunk = text[start:].strip()
                if chunk and len(chunk) >= self.min_chunk_size:
                    chunks.append(chunk)
                break

            # Ищем лучшую точку разрыва
            best_break = self._find_best_break(text[start:end])
            actual_end = start + best_break

            chunk = text[start:actual_end].strip()
            if chunk and len(chunk) >= self.min_chunk_size:
                chunks.append(chunk)

            start = actual_end
            if start >= len(text):
                break

        return chunks

    def _find_best_break(self, text: str) -> int:
        """
        Ищем лучшую точку разрыва в пределах текста.

        Приоритет:
        1. Пробел в последних 20% текста
        2. Знак препинания (.!?)
        3. Середина (fallback)
        """
        min_pos = int(len(text) * 0.8)

        # 1. Пробел
        space_pos = text.rfind(" ", min_pos)
        if space_pos > 0:
            return space_pos + 1  # Включая пробел

        # 2. Точка / восклицание / вопрос
        for punct in (".", "!", "?"):
            punct_pos = text.rfind(punct, min_pos)
            if punct_pos > int(len(text) * 0.5):
                return punct_pos + 1

        # 3. Fallback — середина
        return max(len(text) // 2, 1)

    # ──────────────────────────────────────────────
    # Overlap
    # ──────────────────────────────────────────────

    def _apply_overlap(self, pieces: List[str]) -> List[str]:
        """
        Добавляет overlap: конец предыдущего куска дублируется в начало следующего.

        Пример:
            Без overlap:  ["Первый абзац.", "Второй абзац."]
            С overlap=15: ["Первый абзац.", "вый абзац. Второй абзац."]
                          ↑ хвост предыдущего
        """
        if self.chunk_overlap <= 0 or len(pieces) <= 1:
            return pieces

        result = [pieces[0]]

        for i in range(1, len(pieces)):
            prev = result[-1]
            # Берём хвост предыдущего куска
            overlap_tail = prev[-self.chunk_overlap:]
            # Добавляем к началу текущего
            new_piece = overlap_tail + pieces[i]
            result.append(new_piece)

        return result

"""
TextChunker — рекурсивное разбиение текста на чанки.

ОТВЕТСТВЕННОСТЬ:
- Разбиение больших текстов на управляемые чанки
- Сохранение контекста через overlap
- Приоритетное разбиение по структуре (заголовки → абзацы → предложения)
- Контроль размера чанков (токены/символы)

НЕ ОТВЕТСТВЕННОСТЬ:
- Векторизация (это TempIndexManager)
- Семантический поиск (это TempIndexManager)
- Модификация исходного текста

АРХИТЕКТУРА:
- Рекурсивный splitter: пробует разные стратегии
- Сначала по заголовкам, потом по абзацам, потом по предложениям
- Добавляет overlap для сохранения контекста
- Возвращает List[Dict] с метаданными

ПРИМЕР:
>>> chunks = TextChunker.split(large_text, chunk_size=2000, overlap=200)
>>> # [{'content': '...', 'chunk_id': 0, 'metadata': {...}}, ...]
"""
import re
from typing import List, Dict, Any, Optional


class TextChunker:
    """
    Рекурсивный чанкер текста с сохранением контекста.

    СТРАТЕГИЯ (по приоритету):
    1. По заголовкам (##, #, ###)
    2. По абзацам (двойные переносы строк)
    3. По предложениям (.!?)
    4. По символам (fallback)

    АРХИТЕКТУРА:
    - chunk_size: целевой размер чанка (в символах, ~4 символа = 1 токен)
    - overlap: перекрытие между чанками для контекста
    - min_chunk_size: минимальный размер чанка (меньше —合并)

    EXAMPLE:
    >>> chunks = TextChunker.split(text, chunk_size=2000, overlap=200)
    >>> len(chunks)
    5
    """

    @staticmethod
    def split(
        text: str,
        chunk_size: int = 2000,
        overlap: int = 200,
        min_chunk_size: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Разбиение текста на чанки.

        АРХИТЕКТУРА:
        1. Пробуем split_by_headings
        2. Если чанки слишком большие → split_by_paragraphs
        3. Если всё ещё большие → split_by_sentences
        4. Fallback → split_by_characters

        ARGS:
        - text: str — исходный текст
        - chunk_size: целевой размер чанка (символы)
        - overlap: размер перекрытия (символы)
        - min_chunk_size: минимальный размер чанка

        RETURNS:
        - List[Dict] с полями:
          - content: str — текст чанка
          - chunk_id: int — идентификатор
          - start_char: int — начальная позиция в исходном тексте
          - end_char: int — конечная позиция
          - metadata: Dict — дополнительная информация

        EXAMPLE:
        >>> text = "# Глава 1\\n\\nТекст главы..."
        >>> chunks = TextChunker.split(text, chunk_size=1000)
        >>> chunks[0]
        {'content': '# Глава 1\\n\\nТекст...', 'chunk_id': 0, ...}
        """
        if not text:
            return []

        # Если текст маленький — не нужно чанкать
        if len(text) <= chunk_size:
            return [{
                "content": text,
                "chunk_id": 0,
                "start_char": 0,
                "end_char": len(text),
                "metadata": {
                    "split_strategy": "no_split",
                    "char_count": len(text),
                    "estimated_tokens": len(text) // 4
                }
            }]

        # Пробуем стратегии по приоритету
        chunks = TextChunker._split_by_headings(text, chunk_size, overlap)
        strategy = "headings"

        if not chunks or max(len(c["content"]) for c in chunks) > chunk_size * 1.5:
            chunks = TextChunker._split_by_paragraphs(text, chunk_size, overlap)
            strategy = "paragraphs"

        if not chunks or max(len(c["content"]) for c in chunks) > chunk_size * 1.5:
            chunks = TextChunker._split_by_sentences(text, chunk_size, overlap)
            strategy = "sentences"

        if not chunks or max(len(c["content"]) for c in chunks) > chunk_size * 1.5:
            chunks = TextChunker._split_by_characters(text, chunk_size, overlap)
            strategy = "characters"

        #合并 слишком маленькие чанки
        if min_chunk_size > 0:
            chunks = TextChunker._merge_small_chunks(chunks, min_chunk_size)

        # Добавляем метаданные
        for i, chunk in enumerate(chunks):
            chunk["chunk_id"] = i
            chunk["metadata"]["split_strategy"] = strategy
            chunk["metadata"]["char_count"] = len(chunk["content"])
            chunk["metadata"]["estimated_tokens"] = len(chunk["content"]) // 4

        return chunks

    @staticmethod
    def _split_by_headings(
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[Dict[str, Any]]:
        """Разбиение по заголовкам (##, #, ###)."""
        # Паттерн для заголовков Markdown
        heading_pattern = r'^(#{1,6}\s+.+)$'
        lines = text.split('\n')

        chunks = []
        current_content = []
        current_start = 0

        for i, line in enumerate(lines):
            if re.match(heading_pattern, line.strip()):
                # Нашли заголовок — начинаем новый чанк
                if current_content:
                    content = '\n'.join(current_content)
                    chunks.append({
                        "content": content,
                        "start_char": current_start,
                        "end_char": current_start + len(content),
                        "metadata": {}
                    })

                # Начинаем новый чанк с заголовком
                char_pos = sum(len(l) + 1 for l in lines[:i])
                current_start = char_pos
                current_content = [line]
            else:
                current_content.append(line)

        # Последний чанк
        if current_content:
            content = '\n'.join(current_content)
            chunks.append({
                "content": content,
                "start_char": current_start,
                "end_char": current_start + len(content),
                "metadata": {}
            })

        # Добавляем overlap
        if overlap > 0 and len(chunks) > 1:
            chunks = TextChunker._add_overlap(chunks, overlap)

        return chunks

    @staticmethod
    def _split_by_paragraphs(
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[Dict[str, Any]]:
        """Разбиение по абзацам (двойные переносы строк)."""
        paragraphs = re.split(r'\n\n+', text)

        chunks = []
        current_content = []
        current_length = 0
        current_start = 0
        char_pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                char_pos += 2  # \n\n
                continue

            para_len = len(para)

            # Если абзац сам по себе больше chunk_size — нужно дальше делить
            if para_len > chunk_size:
                if current_content:
                    content = '\n\n'.join(current_content)
                    chunks.append({
                        "content": content,
                        "start_char": current_start,
                        "end_char": current_start + len(content),
                        "metadata": {}
                    })
                    current_content = []
                    current_length = 0
                
                # Этот абзац будет разделён на sentences
                    # (обработается на следующем уровне рекурсии)
                chunks.append({
                    "content": para,
                    "start_char": char_pos,
                    "end_char": char_pos + para_len,
                    "metadata": {}
                })
            elif current_length + para_len > chunk_size and current_content:
                # Превысили размер — создаём чанк
                content = '\n\n'.join(current_content)
                chunks.append({
                    "content": content,
                    "start_char": current_start,
                    "end_char": current_start + len(content),
                    "metadata": {}
                })
                
                # Новый чанк с overlap
                if overlap > 0 and current_content:
                    overlap_text = current_content[-1]
                    current_content = [overlap_text, para]
                    current_length = len(overlap_text) + para_len
                    current_start = char_pos - len(overlap_text)
                else:
                    current_content = [para]
                    current_length = para_len
                    current_start = char_pos
            else:
                current_content.append(para)
                current_length += para_len
                if not current_start:
                    current_start = char_pos

            char_pos += para_len + 2

        # Последний чанк
        if current_content:
            content = '\n\n'.join(current_content)
            chunks.append({
                "content": content,
                "start_char": current_start,
                "end_char": current_start + len(content),
                "metadata": {}
            })

        return chunks

    @staticmethod
    def _split_by_sentences(
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[Dict[str, Any]]:
        """Разбиение по предложениям (.!?)."""
        # Паттерн для конца предложений
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_content = []
        current_length = 0
        current_start = 0
        char_pos = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sent_len = len(sentence)

            if sent_len > chunk_size:
                # Предложение слишком длинное — идём дальше
                if current_content:
                    content = ' '.join(current_content)
                    chunks.append({
                        "content": content,
                        "start_char": current_start,
                        "end_char": current_start + len(content),
                        "metadata": {}
                    })
                    current_content = []
                    current_length = 0
                
                chunks.append({
                    "content": sentence,
                    "start_char": char_pos,
                    "end_char": char_pos + sent_len,
                    "metadata": {}
                })
            elif current_length + sent_len > chunk_size and current_content:
                content = ' '.join(current_content)
                chunks.append({
                    "content": content,
                    "start_char": current_start,
                    "end_char": current_start + len(content),
                    "metadata": {}
                })

                # overlap
                if overlap > 0 and current_content:
                    overlap_text = current_content[-1]
                    current_content = [overlap_text, sentence]
                    current_length = len(overlap_text) + sent_len
                    current_start = char_pos - len(overlap_text)
                else:
                    current_content = [sentence]
                    current_length = sent_len
                    current_start = char_pos
            else:
                current_content.append(sentence)
                current_length += sent_len
                if not current_start:
                    current_start = char_pos

            char_pos += sent_len + 1

        if current_content:
            content = ' '.join(current_content)
            chunks.append({
                "content": content,
                "start_char": current_start,
                "end_char": current_start + len(content),
                "metadata": {}
            })

        return chunks

    @staticmethod
    def _split_by_characters(
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[Dict[str, Any]]:
        """Fallback: разбиение по символам."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            content = text[start:end]
            
            chunks.append({
                "content": content,
                "start_char": start,
                "end_char": end,
                "metadata": {}
            })

            # Следующий чанк начинается с overlap
            if end >= len(text):
                break
            
            start = end - overlap if overlap < end else 0

        return chunks

    @staticmethod
    def _add_overlap(
        chunks: List[Dict[str, Any]],
        overlap: int
    ) -> List[Dict[str, Any]]:
        """Добавление перекрытия между чанками."""
        if overlap <= 0 or len(chunks) <= 1:
            return chunks

        for i in range(1, len(chunks)):
            prev_content = chunks[i - 1]["content"]
            # Берём последние overlap символов предыдущего чанка
            overlap_text = prev_content[-overlap:] if len(prev_content) > overlap else prev_content
            
            chunks[i]["content"] = overlap_text + "\n" + chunks[i]["content"]
            chunks[i]["start_char"] -= len(overlap_text)

        return chunks

    @staticmethod
    def _merge_small_chunks(
        chunks: List[Dict[str, Any]],
        min_size: int
    ) -> List[Dict[str, Any]]:
        """合并 слишком маленьких чанков."""
        if not chunks:
            return []

        merged = []
        current = chunks[0].copy()

        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            
            if len(current["content"]) < min_size:
                #合并
                current["content"] += "\n" + next_chunk["content"]
                current["end_char"] = next_chunk["end_char"]
            else:
                merged.append(current)
                current = next_chunk.copy()

        merged.append(current)
        return merged

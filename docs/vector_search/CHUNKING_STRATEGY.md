# ✂️ Chunking: Разбиение на чанки

**Версия:** 2.0.0  
**Дата:** 2026-02-19  
**Статус:** ✅ Утверждено

---

## 📋 Обзор

**ChunkingService — отдельный, расширяемый компонент.**

Позволяет добавлять новые стратегии без изменения кода:
- TextChunkingStrategy (по тексту)
- SemanticChunkingStrategy (по смыслу)
- HybridChunkingStrategy (комбо)
- TableChunkingStrategy (для таблиц)
- CodeChunkingStrategy (для кода)

---

## 🏗️ Архитектура

### Компоненты

```
┌─────────────────────────────────────────────────────────────┐
│                    ChunkingService                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  IChunkingStrategy (интерфейс)                       │  │
│  │  └─ split(text) → List[Chunk]                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│         ┌──────────────────┼──────────────────┐             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ TextChunking │  │ Semantic     │  │ Hybrid       │      │
│  │ Strategy     │  │ Chunking     │  │ Chunking     │      │
│  │ (по тексту)  │  │ (по смыслу)  │  │ (комбо)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  + ChunkingFactory (создание стратегий)                     │
│  + ChunkingConfig (настройки)                               │
└─────────────────────────────────────────────────────────────┘
```

### Интерфейс

```python
# core/infrastructure/providers/vector/chunking_strategy.py

class IChunkingStrategy(ABC):
    """Интерфейс стратегии разбиения."""
    
    @abstractmethod
    async def split(
        self,
        content: str,
        document_id: str,
        metadata: Optional[Dict] = None
    ) -> List[VectorChunk]:
        """Разбиение текста на чанки."""
        pass
    
    @abstractmethod
    def get_config(self) -> dict:
        """Получить конфигурацию стратегии."""
        pass
```

---

## 🎯 Параметры

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| **chunk_size** | 500 символов | Оптимально для эмбеддингов (SentenceTransformers) |
| **chunk_overlap** | 50 символов (10%) | Сохраняет контекст между чанками |
| **min_chunk_size** | 100 символов | Не разбивать маленькие чанки |

---

## 🔧 Стратегии

### 1. TextChunkingStrategy (по тексту)

**Когда использовать:** По умолчанию, для большинства текстов

**Алгоритм:**
```
1. Разделить по заголовкам (\n## )
2. Разделить по абзацам (\n\n)
3. Разделить по предложениям (. )
4. Принудительно по размеру (500 символов)
5. Добавить перекрытие (50 символов)
```

**Конфигурация:**
```yaml
strategy: "text"
config:
  chunk_size: 500
  chunk_overlap: 50
  separators:
    - "\n## "
    - "\n\n"
    - "\n"
    - ". "
```

---

### 2. SemanticChunkingStrategy (по смыслу)

**Когда использовать:** Для сложных текстов, где важны смысловые границы

**Алгоритм:**
```
1. Разделить на предложения
2. Сгенерировать эмбеддинги предложений
3. Найти границы тем (cosine similarity < threshold)
4. Объединить предложения в чанки по темам
```

**Конфигурация:**
```yaml
strategy: "semantic"
config:
  embedding_model: "all-MiniLM-L6-v2"
  similarity_threshold: 0.5  # Ниже = больше чанков
  min_chunk_size: 100
  max_chunk_size: 1000
```

**Преимущества:**
- ✅ Чанки соответствуют смысловым границам
- ✅ Лучшее качество поиска
- ✅ Меньше потери контекста

**Недостатки:**
- ⚠️ Медленнее (требуется генерация эмбеддингов)
- ⚠️ Требует embedding модель

---

### 3. HybridChunkingStrategy (комбо)

**Когда использовать:** Для больших документов со сложной структурой

**Алгоритм:**
```
1. Сначала разбить по тексту (заголовки, абзацы)
2. Затем уточнить границы по смыслу
3. Объединить маленькие чанки
```

**Конфигурация:**
```yaml
strategy: "hybrid"
config:
  text:
    chunk_size: 500
    chunk_overlap: 50
  semantic:
    similarity_threshold: 0.5
    max_chunk_size: 1000
```

---

### 4. TableChunkingStrategy (для таблиц)

**Когда использовать:** Для документов с таблицами

**Алгоритм:**
```
1. Найти таблицы в тексте
2. Каждая таблица → отдельный чанк
3. Текст вокруг → по тексту
```

**Конфигурация:**
```yaml
strategy: "table"
config:
  max_table_rows: 50  # Максимум строк в чанке
  include_headers: true  # Сохранять заголовки
```

---

### 5. CodeChunkingStrategy (для кода)

**Когда использовать:** Для документов с кодом

**Алгоритм:**
```
1. Найти блоки кода
2. Каждый блок → отдельный чанк
3. Сохранять отступы
4. Добавлять язык кода в метаданные
```

**Конфигурация:**
```yaml
strategy: "code"
config:
  max_code_lines: 100  # Максимум строк в чанке
  preserve_indentation: true  # Сохранять отступы
```

---

## 🏭 Фабрика стратегий

```python
# core/infrastructure/providers/vector/chunking_factory.py

class ChunkingFactory:
    """Фабрика стратегий chunking."""
    
    @staticmethod
    def create(
        strategy_type: Literal["text", "semantic", "hybrid", "table", "code"],
        config: Dict[str, Any]
    ) -> IChunkingStrategy:
        """Создание стратегии по типу."""
        
        if strategy_type == "text":
            return TextChunkingStrategy(**config)
        
        elif strategy_type == "semantic":
            return SemanticChunkingStrategy(**config)
        
        elif strategy_type == "hybrid":
            text = ChunkingFactory.create("text", config.get("text", {}))
            semantic = ChunkingFactory.create("semantic", config.get("semantic", {}))
            return HybridChunkingStrategy(text, semantic)
        
        elif strategy_type == "table":
            return TableChunkingStrategy(**config)
        
        elif strategy_type == "code":
            return CodeChunkingStrategy(**config)
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
```

---

## ⚙️ Конфигурация

```yaml
# registry.yaml

vector_search:
  chunking:
    # Тип стратегии (text/semantic/hybrid/table/code)
    strategy: "text"
    
    # Конфигурация стратегии
    config:
      chunk_size: 500
      chunk_overlap: 50
      separators:
        - "\n## "
        - "\n\n"
        - "\n"
        - ". "
    
    # Будущая конфигурация semantic
    # strategy: "semantic"
    # config:
    #   embedding_model: "all-MiniLM-L6-v2"
    #   similarity_threshold: 0.5
    #   min_chunk_size: 100
    #   max_chunk_size: 1000
    
    # Будущая конфигурация hybrid
    # strategy: "hybrid"
    # config:
    #   text:
    #     chunk_size: 500
    #     chunk_overlap: 50
    #   semantic:
    #     similarity_threshold: 0.5
    #     max_chunk_size: 1000
```

---

## 🔄 Алгоритм разбиения

### Многоуровневое разбиение

```
┌─────────────────────────────────────────────────────────────┐
│  ПРИОРИТЕТЫ РАЗБИЕНИЯ                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. По главам/разделам                                      │
│     └→ Если раздел < 500 символов → один чанк               │
│                                                             │
│  2. По абзацам                                              │
│     └→ Если абзац < 500 символов → один чанк                │
│                                                             │
│  3. По предложениям                                         │
│     └→ Если предложение < 500 символов → один чанк          │
│                                                             │
│  4. Принудительное разбиение                                │
│     └→ Разбить по 500 символов с перекрытием 50             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Разделители (по приоритету)

```python
SEPARATORS = [
    "\n## ",      # Заголовки H2
    "\n### ",     # Заголовки H3
    "\n\n",       # Абзацы
    "\n",         # Строки
    ". ",         # Предложения
    "! ",         # Восклицания
    "? ",         # Вопросы
    " ",          # Слова
    ""            # Символы
]
```

---

## 🔧 Реализация

### ChunkingService

```python
# core/infrastructure/providers/vector/chunking_service.py

from typing import List, Optional, Dict
from core.models.types.vector_types import VectorChunk


class ChunkingService:
    """Сервис разбиения текста на чанки."""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.separators = [
            "\n## ", "\n### ", "\n\n", "\n",
            ". ", "! ", "? ", " ", ""
        ]
    
    async def split(
        self,
        content: str,
        chapter: Optional[int] = None,
        document_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[VectorChunk]:
        """
        Разбиение текста на чанки.
        
        Args:
            content: Текст для разбиения
            chapter: Номер главы (для книг)
            document_id: ID документа
            metadata: Дополнительные метаданные
        
        Returns:
            Список VectorChunk
        """
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
                            chapter=chapter,
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
                            chapter=chapter,
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
        chapter: Optional[int],
        document_id: Optional[str],
        index: int,
        metadata: Optional[Dict]
    ) -> VectorChunk:
        """Создание VectorChunk."""
        
        chunk_id = f"{document_id}_chunk_{index}" if document_id else f"chunk_{index}"
        
        chunk_metadata = {
            "chapter": chapter,
            "chunk_size": len(content),
            "has_overlap": self.chunk_overlap > 0,
            "overlap_chars": self.chunk_overlap,
            **(metadata or {})
        }
        
        return VectorChunk(
            id=chunk_id,
            document_id=document_id or "unknown",
            content=content,
            metadata=chunk_metadata,
            index=index,
            chapter=chapter
        )
```

---

## 📊 Примеры

### Пример 1: Маленький текст (< 500 символов)

**Вход:**
```
Глава 1

Мой дядя самых честных правил,
Когда не в шутку занемог...
(150 символов)
```

**Выход:**
```
Chunk 0:
  content: "Глава 1\n\nМой дядя самых честных правил..."
  chapter: 1
  chunk_size: 150
```

---

### Пример 2: Средний текст (600 символов)

**Вход:**
```
Глава 1

Мой дядя самых честных правил,
Когда не в шутку занемог,
Он уважать себя заставил
И лучше выдумать не мог.

Его пример другим наука;
Но, боже мой, какая скука
С больным сидеть и день и ночь,
Не отходя ни шагу прочь!
(600 символов)
```

**Выход:**
```
Chunk 0 (0-500):
  content: "Глава 1\n\nМой дядя самых честных правил...\nНо, боже мой, какая скука"
  chapter: 1
  chunk_size: 500

Chunk 1 (450-600):
  content: "какая скука\nС больным сидеть и день и ночь..."
  chapter: 1
  chunk_size: 150
  overlap: 50 символов ("какая скука\n")
```

---

### Пример 3: Большой текст (2000 символов)

**Вход:**
```
Глава 1
(2000 символов сплошного текста)
```

**Выход:**
```
Chunk 0 (0-500):
  content: "текст..."
  chunk_size: 500

Chunk 1 (450-950):
  content: "текст..."
  chunk_size: 500
  overlap: 50 символов

Chunk 2 (900-1400):
  content: "текст..."
  chunk_size: 500
  overlap: 50 символов

Chunk 3 (1350-2000):
  content: "текст..."
  chunk_size: 650
  overlap: 50 символов
```

---

## 🎯 Перекрытие (Overlap)

### Зачем нужно?

```
┌─────────────────────────────────────────────────────────────┐
│  БЕЗ ПЕРЕКРЫТИЯ                                             │
├─────────────────────────────────────────────────────────────┤
│  Chunk 0: "...он сказал что пойдёт..."                      │
│  Chunk 1: "...завтра утром в магазин..."                    │
│                                                             │
│  Проблема: Потерян контекст!                                │
│  - Chunk 0: Кто сказал?                                     │
│  - Chunk 1: Что завтра?                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  С ПЕРЕКРЫТИЕМ (50 символов)                                │
├─────────────────────────────────────────────────────────────┤
│  Chunk 0: "...он сказал что пойдёт..."                      │
│  Chunk 1: "...пойдёт завтра утром в магазин..."             │
│            ↑                                                │
│         Перекрытие                                         │
│                                                             │
│  Преимущество: Контекст сохранён!                           │
│  - Chunk 1 содержит "пойдёт" из Chunk 0                     │
│  - Поиск найдёт оба чанка по запросу "пойдёт завтра"        │
└─────────────────────────────────────────────────────────────┘
```

### Размер перекрытия

| chunk_size | overlap | % | Когда использовать |
|------------|---------|---|-------------------|
| 500 | 50 | 10% | По умолчанию (оптимально) |
| 500 | 100 | 20% | Для сложных текстов |
| 1000 | 100 | 10% | Для больших документов |
| 200 | 50 | 25% | Для коротких текстов |

---

## 📈 Метрики

### Метрики chunking

```python
{
    "total_documents": 150,
    "total_chunks": 7500,
    "avg_chunks_per_document": 50,
    "avg_chunk_size": 485,
    "min_chunk_size": 100,
    "max_chunk_size": 500,
    "overlap_size": 50,
    "processing_time_seconds": 45.2
}
```

---

## 🧪 Тесты

```python
# tests/unit/infrastructure/vector/test_chunking_service.py

import pytest
from core.infrastructure.providers.vector.chunking_service import ChunkingService


class TestChunkingService:
    
    @pytest.fixture
    def chunking(self):
        return ChunkingService(chunk_size=500, chunk_overlap=50)
    
    def test_small_text_one_chunk(self, chunking):
        """Маленький текст → один чанк."""
        text = "Короткий текст " * 5  # ~75 символов
        chunks = chunking.split(text, document_id="doc_1")
        
        assert len(chunks) == 1
        assert chunks[0].document_id == "doc_1"
        assert chunks[0].index == 0
    
    def test_large_text_multiple_chunks(self, chunking):
        """Большой текст → несколько чанков."""
        text = "A" * 1200  # 1200 символов
        chunks = chunking.split(text, document_id="doc_1")
        
        assert len(chunks) >= 3  # 1200 / 500 = 2.4 → 3 чанка
        assert chunks[0].chunk_size <= 500
    
    def test_overlap_exists(self, chunking):
        """Перекрытие существует."""
        text = "A" * 1200
        chunks = chunking.split(text, document_id="doc_1")
        
        # Проверяем перекрытие между chunk_0 и chunk_1
        if len(chunks) >= 2:
            chunk_0_end = chunks[0].content[-50:]
            chunk_1_start = chunks[1].content[:50]
            assert chunk_0_end == chunk_1_start
    
    def test_chapter_metadata(self, chunking):
        """Метаданные главы."""
        text = "Текст главы..."
        chunks = chunking.split(text, chapter=5, document_id="book_1")
        
        assert all(c.chapter == 5 for c in chunks)
        assert all(c.document_id == "book_1" for c in chunks)
    
    def test_paragraph_split(self, chunking):
        """Разбиение по абзацам."""
        text = "Абзац 1\n\nАбзац 2\n\nАбзац 3"
        chunks = chunking.split(text, document_id="doc_1")
        
        # Каждый абзац в отдельном чанке (если < 500)
        assert len(chunks) >= 3
    
    def test_min_chunk_size(self, chunking):
        """Минимальный размер чанка."""
        text = "Коротко"  # < 100 символов
        chunks = chunking.split(text, document_id="doc_1")
        
        # Всё равно создаётся чанк (но маленький)
        assert len(chunks) == 1
```

---

## 📋 Чек-лист

### Реализация

```
□ ChunkingService создан
□ chunk_size настраиваемый (по умолчанию 500)
□ chunk_overlap настраиваемый (по умолчанию 50)
□ Многоуровневое разбиение (главы → абзацы → предложения)
□ Перекрытие между чанками
□ Метаданные чанка (chapter, chunk_index, etc.)
□ Тесты написаны
```

### Конфигурация

```
□ chunk_size в конфиге
□ chunk_overlap в конфиге
□ separators в конфиге
□ min_chunk_size в конфиге
```

---

*Документ создан: 2026-02-19*  
*Версия: 1.0.0*  
*Статус: ✅ Утверждено*

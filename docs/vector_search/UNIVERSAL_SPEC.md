# 📘 Универсальная спецификация Vector Search

**Версия:** 3.0.0  
**Дата:** 2026-04-17  
**Статус:** ✅ Утверждено

---

## 🎯 Принцип архитектуры

**Универсальные механизмы** вместо узкой специализации.

Каждый инструмент работает с **любым источником** через универсальные интерфейсы.

---

## 🏗️ Архитектура

### Поток данных: SQL → Вектор → SQL

```
SQL (TEXT) → Chunking → Embedding → FAISS (vector + metadata) → Поиск → SQL (полный текст)
```

**Где что хранится:**

| Данные | Хранение | Формат |
|--------|----------|--------|
| Исходный текст | SQL (book_texts.content) | TEXT |
| Векторы | FAISS (books_index.faiss) | binary (384 dim) |
| Метаданные | JSON (books_metadata.json) | JSON |
| Связь | metadata.book_id → books.id | integer |

### Компоненты

```
┌─────────────────────────────────────────────────────────────┐
│                         АГЕНТ                               │
└─────────────────────────────────────────────────────────────┘
                            │
    ┌───────────┬───────────┼───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Vector  │ │Vector  │ │Vector  │ │Vector  │ │  SQL   │
│Knowledge│ │History │ │ Docs   │ │ Books  │ │ Tool   │
│ Tool   │ │ Tool   │ │ Tool   │ │ Tool   │ │        │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    │          │          │          │           │
    └──────────┴──────────┴──────────┴───────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  FAISS Provider  │ │  SQL Provider    │ │  LLM Provider    │
│  (универсальный) │ │  (универсальный) │ │  (универсальный) │
└──────────────────┘ └──────────────────┘ └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Analysis Cache  │
                     │ (универсальный)  │
                     └──────────────────┘
```

---

## 🔄 Детальный поток данных

### 1. Индексация (SQL → FAISS)

```python
# 1. Получаем текст из SQL
chapters = await sql.fetch("""
    SELECT chapter, content FROM book_texts
    WHERE book_id = ? ORDER BY chapter
""", (book_id,))

# 2. Разбиваем на чанки
chunks = await chunking.split(content=chapter["content"])

# 3. Генерируем векторы
vectors = await embedding.generate([chunk.content for chunk in chunks])

# 4. Добавляем в FAISS с метаданными
metadata = {
    "chunk_id": f"book_{book_id}_chunk_0",
    "document_id": f"book_{book_id}",
    "book_id": book_id,  ← Ссылка на SQL
    "chapter": 1,
    "chunk_index": 0
}
await faiss.add(vectors, metadata)
```

### 2. Поиск (FAISS → SQL)

```python
# 1. Генерируем вектор запроса
query_vector = await embedding.generate(["найди про любовь"])

# 2. Ищем в FAISS
results = await faiss.search(query_vector, top_k=10)
# results[0].metadata = {"book_id": 1, "chapter": 1, ...}

# 3. Получаем полный текст из SQL
text = await sql.fetch("""
    SELECT content FROM book_texts
    WHERE book_id = ? AND chapter = ?
""", (results[0].metadata["book_id"], results[0].metadata["chapter"]))
```

---

## 📁 Структура файлов

```
core/models/types/
├── vector_types.py              ← Универсальные модели
└── analysis.py                  ← Универсальный LLM анализ

core/config/
└── vector_config.py             ← Конфигурация

core/infrastructure/providers/vector/
├── base_faiss_provider.py       ← Базовый класс (универсальный)
├── faiss_provider.py            ← FAISS (универсальный)
├── embedding_provider.py        ← Embeddings (универсальный)
├── chunking_service.py          ← Chunking (универсальный)
└── mock_faiss_provider.py       ← Mock

core/infrastructure/cache/
└── analysis_cache.py            ← Кэш (универсальный)

core/application/tools/
├── vector_knowledge_tool.py     ← Knowledge (универсальный)
├── vector_history_tool.py       ← History (универсальный)
├── vector_docs_tool.py          ← Docs (универсальный)
└── vector_books_tool.py         ← Books (универсальный + SQL)

core/application/services/
└── document_indexing_service.py ← Индексация (универсальный)

core/common/exceptions/
└── vector_exceptions.py         ← Исключения
```

---

## ЭТАП 1: Модели данных

### 1.1 Универсальные модели (core/models/types/vector_types.py)

```python
# core/models/types/vector_types.py
"""Универсальные модели векторного поиска."""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class VectorSearchResult(BaseModel):
    """
    Универсальный результат поиска.
    
    Attributes:
        id: Уникальный ID
        document_id: ID документа
        chunk_id: ID чанка
        score: Оценка релевантности
        content: Содержимое
        metadata: Любые метаданные
        source: Источник (любой string)
    """
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    score: float = Field(ge=0.0, le=1.0)
    content: str
    metadata: Dict[str, Any]
    source: str  # Любой источник (не enum!)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "result_001",
                "document_id": "book_123",
                "chunk_id": "chunk_456",
                "score": 0.92,
                "content": "текст...",
                "metadata": {"book_title": "Евгений Онегин"},
                "source": "books"
            }
        }


class VectorQuery(BaseModel):
    """
    Универсальный запрос на поиск.
    """
    query: Optional[str] = None
    vector: Optional[List[float]] = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None  # Любые фильтры
    offset: int = Field(default=0, ge=0)


class VectorDocument(BaseModel):
    """
    Универсальный документ для индексации.
    """
    id: Optional[str] = None
    content: str
    metadata: Dict[str, Any]
    source: str  # Любой источник
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class VectorChunk(BaseModel):
    """
    Универсальный чанк.
    """
    id: str
    document_id: str
    content: str
    vector: Optional[List[float]] = None
    metadata: Dict[str, Any]
    index: int
    chapter: Optional[int] = None  # Опционально для книг


class VectorIndexInfo(BaseModel):
    """
    Информация об индексе.
    """
    source: str
    total_documents: int
    total_chunks: int
    index_size_mb: float
    dimension: int
    index_type: str
    created_at: datetime
    updated_at: datetime


class RowMetadata(BaseModel):
    """
    Универсальные метаданные строки БД для векторного индекса.

    Структура хранит полную строку из БД для возврата без дополнительных запросов.
    Поддерживает как обычные записи, так и чанкнутые документы.
    """
    source: str = Field(description="Имя источника (audits, violations, books, ...)")
    table: str = Field(description="Полное имя таблицы (schema.table)")
    primary_key: str = Field(description="Имя поля primary key")
    pk_value: Any = Field(description="Значение primary key")
    row: Dict[str, Any] = Field(description="Все поля строки из БД")
    chunk_index: int = Field(default=0, description="Индекс чанка в документе")
    total_chunks: int = Field(default=1, description="Всего чанков в документе")
    search_text: str = Field(description="Текст который был векторизован")
    content: str = Field(description="Текст конкретного чанка")

    def get_row_field(self, field_name: str, default: Any = None) -> Any:
        """Получить значение поля из строки БД."""
        return self.row.get(field_name, default)

    def get_id(self) -> Any:
        """Получить значение primary key."""
        return self.pk_value

    def is_single_chunk(self) -> bool:
        """Проверяет что документ не разбит на чанки."""
        return self.total_chunks == 1
```

---

## 📊 Управление top_k

### Безлимитный поиск

Для поиска всех релевантных результатов (без ограничения по количеству):

```python
# input contract: top_k: nullable: true
{"query": "...", "top_k": null, "min_score": 0.5}
```

### Константы (core/components/tools/vector_search_tool.py)

```python
class VectorSearchDefaults:
    """Константы для типичных сценариев поиска."""
    TOP_K_DEFAULT = 10        # ограничить 10 результатами
    TOP_K_ALL = None         # без лимита
    MIN_SCORE_DEFAULT = 0.5
    MIN_SCORE_LENIENT = 0.3  # для широкого поиска
    MIN_SCORE_STRICT = 0.7   # для точного поиска
```

### Примеры использования

```python
# 1. Ограничить 10 результатами (по умолчанию)
{"query": "...", "top_k": 10}

# 2. Без лимита — только min_score
{"query": "...", "top_k": null, "min_score": 0.5}

# 3. Все с score > 0.3
{"query": "...", "top_k": null, "min_score": 0.3}

# 4. Для валидации — top_k=1
{"query": "...", "top_k": 1, "source": "violations"}
```

### Логика отбора

| top_k | min_score | Поведение |
|-------|-----------|-----------|
| 10 | 0.5 | Макс 10, score ≥ 0.5 |
| null | 0.5 | Все с score ≥ 0.5 (без лимита) |
| null | 0.3 | Все с score ≥ 0.3 |
| 1 | 0.0 | Только 1 лучший результат |

---

## 🔍 ParamValidator — каскадная валидация параметров

### Пайплайн (3 ступени)

```
┌─────────────────────────────────────────────────────────────┐
│  ШАГ 1: Enum ИЛИ SQL ILIKE (развилка)                    │
│  ├── type="enum" → проверка по списку allowed_values      │
│  └── type="search" → SQL ILIKE поиск в БД                │
│      Что быстрее найдёт — то и возвращаем                  │
├─────────────────────────────────────────────────────────────┤
│  ШАГ 2: Vector search (если ШАГ 1 не нашёл)              │
│  └── Семантический поиск через FAISS                       │
├─────────────────────────────────────────────────────────────┤
│  ШАГ 3: Fuzzy matching (если ШАГ 2 не нашёл)             │
│  └── Расстояние Левенштейна                               │
└─────────────────────────────────────────────────────────────┘
```

### Ключевая особенность: НЕ блокирующий

```python
{
    "valid": True,              # всегда True
    "corrected_value": "...",   # найденное значение (или None)
    "warning": "...",          # предупреждение
    "suggestions": [...]       # варианты для выбора
}
```

### Конфигурация в скриптах

```python
SCRIPTS_REGISTRY = {
    "get_violations_by_status": {
        "parameters": {
            "status": {
                "type": "like",
                "validation": {
                    "type": "enum",
                    "allowed_values": ["Открыто", "В работе", "Устранено"]
                }
            },
            "author": {
                "type": "like",
                "validation": {
                    "type": "search",
                    "table": "authors",
                    "search_fields": ["first_name", "last_name"],
                    "vector_source": "authors",
                    "vector_min_score": 0.7,
                    "vector_top_k": 3
                }
            }
        }
    }
}
```

### Примеры Flow

**"Открыто" (enum):**
```
Шаг 1 (enum): found → {"corrected_value": "Открыто"} ✅
```

**"Пушк" (SQL ILIKE):**
```
Шаг 1 (enum): not found
Шаг 1 (SQL): "Пушк%" → "Пушкин" ✅
```

**"писатель 19 века" (semantic):**
```
Шаг 1 (SQL): not found
Шаг 2 (Vector): score=0.82 → "Пушкин" ✅
```

**"Пушкн" (опечатка):**
```
Шаг 1 (SQL): not found
Шаг 2 (Vector): score < 0.7, skip
Шаг 3 (Fuzzy): Levenshtein("Пушкн", candidates) → "Пушкин" ✅
```

### Тесты пайплайна

| Тест | Проверяет |
|------|-----------|
| `test_enum_found_stops_immediately` | Enum нашёл → 0 запросов |
| `test_enum_not_found_continues_to_vector` | Enum не нашёл → suggestions сохраняются |
| `test_sql_ilike_finds_value` | SQL ILIKE → 1 запрос, без Vector |
| `test_sql_not_found_continues_to_vector` | SQL пусто → переход к Vector |
| `test_vector_finds_with_high_score` | Vector с высоким score → возврат |
| `test_vector_low_score_continues_to_fuzzy` | Vector с низким score → переход к Fuzzy |
| `test_no_vector_source_skips_vector` | Без vector_source → Vector не вызывается |
| `test_exception_in_sql_does_not_crash` | Исключение SQL → продолжение |
| `test_exception_in_vector_does_not_crash` | Исключение Vector → продолжение |

---

### 1.2 Универсальный анализ (core/models/types/analysis.py)

```python
# core/models/types/analysis.py
"""Универсальные модели LLM анализа."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class AnalysisResult(BaseModel):
    """
    Универсальный результат LLM анализа.
    
    Подходит для:
    - Анализа героев книг
    - Анализа тем документов
    - Классификации контента
    - Извлечения сущностей
    
    Attributes:
        entity_id: ID сущности (book_id, doc_id, etc.)
        analysis_type: Тип анализа ("character", "theme", etc.)
        result: Любые результаты анализа
        confidence: Уверенность (0-1)
        reasoning: Обоснование
        analyzed_at: Дата анализа
        error: Ошибка
    """
    entity_id: str
    analysis_type: str
    result: Dict[str, Any]  # Универсальный результат
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Проверка валидности."""
        return self.error is None and self.confidence >= 0.8
    
    def to_dict(self) -> dict:
        """Конвертация в dict."""
        return {
            "entity_id": self.entity_id,
            "analysis_type": self.analysis_type,
            "result": self.result,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "analyzed_at": self.analyzed_at.isoformat(),
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisResult":
        """Создание из dict."""
        return cls(
            entity_id=data["entity_id"],
            analysis_type=data["analysis_type"],
            result=data.get("result", {}),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning"),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            error=data.get("error")
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "book_1",
                "analysis_type": "character",
                "result": {
                    "main_character": "Евгений Онегин",
                    "gender": "male"
                },
                "confidence": 0.95,
                "reasoning": "Имя в названии"
            }
        }
```

---

### 1.3 Конфигурация (core/config/vector_config.py)

```python
# core/config/vector_config.py
"""Универсальная конфигурация."""

from pydantic import BaseModel, Field
from typing import Literal, Dict


class FAISSConfig(BaseModel):
    index_type: Literal["Flat", "IVF", "HNSW"] = "Flat"
    nlist: int = 100
    nprobe: int = 10
    metric: Literal["L2", "IP"] = "IP"


class EmbeddingConfig(BaseModel):
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = 32


class ChunkingConfig(BaseModel):
    enabled: bool = True
    chunk_size: int = 500
    chunk_overlap: int = 50


class VectorStorageConfig(BaseModel):
    base_path: str = "./data/vector"
    backup_enabled: bool = True


class AnalysisCacheConfig(BaseModel):
    enabled: bool = True
    ttl_hours: int = 168  # 7 дней
    max_size_mb: int = 100


class VectorSearchConfig(BaseModel):
    """Универсальная конфигурация."""
    enabled: bool = True
    indexes: Dict[str, str] = {
        "knowledge": "knowledge_index.faiss",
        "history": "history_index.faiss",
        "docs": "docs_index.faiss",
        "books": "books_index.faiss"
    }
    faiss: FAISSConfig = Field(default_factory=FAISSConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    storage: VectorStorageConfig = Field(default_factory=VectorStorageConfig)
    cache: AnalysisCacheConfig = Field(default_factory=AnalysisCacheConfig)
    default_top_k: int = 10
    max_top_k: int = 100
    default_min_score: float = 0.5
```

---

## ЭТАП 2: Тесты

### Универсальные тесты

```python
# tests/unit/models/test_vector_types.py
"""Тесты универсальных моделей."""

def test_vector_search_result_any_source():
    """Тест: любой источник работает."""
    result = VectorSearchResult(
        id="r1", document_id="d1", score=0.9,
        content="text", metadata={},
        source="any_source"  # Любой string!
    )
    assert result.source == "any_source"


def test_vector_search_result_books():
    """Тест: книги работают."""
    result = VectorSearchResult(
        id="r1", document_id="book_1", score=0.9,
        content="текст",
        metadata={"book_title": "Евгений Онегин"},
        source="books"
    )
    assert result.source == "books"
    assert result.metadata["book_title"] == "Евгений Онегин"
```

---

## ЭТАП 3: Реализация

### 3.1 Универсальный VectorBooksTool

```python
# core/application/tools/vector_books_tool.py
"""Универсальный инструмент для книг."""

class VectorBooksTool(BaseTool):
    """
    Универсальный инструмент для работы с книгами.
    
    Capabilities:
    - search: Семантический поиск (FAISS)
    - get_document: Полный текст (SQL)
    - analyze: LLM анализ (универсальный)
    - query: SQL запрос
    """
    
    async def execute(
        self,
        capability: str,
        **kwargs
    ) -> ToolResult:
        
        if capability == "search":
            return await self._search(**kwargs)
        
        elif capability == "get_document":
            return await self._get_document(**kwargs)
        
        elif capability == "analyze":
            return await self._analyze(**kwargs)
        
        elif capability == "query":
            return await self._query(**kwargs)
        
        return ToolResult.error(f"Unknown capability: {capability}")
    
    async def _search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> ToolResult:
        """Семантический поиск по книгам."""
        # FAISS поиск
        results = await self.faiss_provider.search(query, top_k, filters)
        return ToolResult.success({"results": results})
    
    async def _get_document(
        self,
        document_id: str,
        **kwargs
    ) -> ToolResult:
        """Получение полного текста документа."""
        # SQL запрос
        text = await self.sql_provider.fetch(
            "SELECT content FROM book_texts WHERE book_id = ?",
            (document_id,)
        )
        return ToolResult.success({"content": text})
    
    async def _analyze(
        self,
        entity_id: str,
        analysis_type: str,
        prompt: str,
        **kwargs
    ) -> ToolResult:
        """
        Универсальный LLM анализ.
        
        Примеры:
        - analyze(entity_id="book_1", analysis_type="character", prompt="Кто главный герой?")
        - analyze(entity_id="book_1", analysis_type="theme", prompt="Какие основные темы?")
        """
        # Проверка кэша
        cache_key = f"{analysis_type}:{entity_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ToolResult.success(cached)
        
        # Получение контекста
        context = await self._get_context(entity_id)
        
        # LLM анализ
        result = await self.llm_provider.generate_json(
            f"{prompt}\n\nКонтекст: {context}"
        )
        
        # Сохранение в кэш
        analysis = AnalysisResult(
            entity_id=entity_id,
            analysis_type=analysis_type,
            result=result,
            confidence=result.get("confidence", 0.5)
        )
        await self.cache.set(cache_key, analysis.to_dict())
        
        return ToolResult.success(analysis.to_dict())
    
    async def _query(
        self,
        sql: str,
        parameters: Optional[Tuple] = None
    ) -> ToolResult:
        """SQL запрос к базе книг."""
        result = await self.sql_provider.fetch(sql, parameters)
        return ToolResult.success({"data": result})
```

---

### 3.2 Универсальный анализ

**Пример использования:**

```python
# Анализ героя книги
result = await agent.use_tool(
    "vector_books_tool",
    capability="analyze",
    entity_id="book_1",
    analysis_type="character",
    prompt="Кто главный герой? Какой у него пол?"
)

# Анализ темы документа
result = await agent.use_tool(
    "vector_docs_tool",
    capability="analyze",
    entity_id="doc_123",
    analysis_type="theme",
    prompt="Какие основные темы?"
)

# Классификация контента
result = await agent.use_tool(
    "vector_knowledge_tool",
    capability="analyze",
    entity_id="kb_456",
    analysis_type="category",
    prompt="К какой категории относится?"
)
```

---

## ✅ Чек-лист приёмки

### Универсальность

```
□ VectorSearchResult работает с любым source (string)
□ AnalysisResult работает с любым analysis_type
□ VectorBooksTool работает с любыми capabilities
□ Конфигурация поддерживает любые индексы
□ Кэш работает для любых типов анализа
```

### Примеры использования

```
□ Поиск по книгам работает
□ Поиск по документации работает
□ Поиск по knowledge работает
□ LLM анализ героя работает
□ LLM анализ тем работает
□ SQL запросы работают
□ Кэширование работает
```

---

*Документ создан: 2026-02-19*  
*Версия: 2.0.0 (универсальная)*  
*Статус: ✅ Утверждено*

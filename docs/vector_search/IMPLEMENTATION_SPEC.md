# 📘 Полная спецификация реализации Vector Search

**Версия:** 1.0.0  
**Дата:** 2026-02-19  
**Статус:** ✅ Утверждено

---

## 📋 Содержание

1. [Архитектурные решения](#архитектурные-решения)
2. [Структура файлов](#структура-файлов)
3. [ЭТАП 1: Модели данных](#этап-1-модели-данных)
4. [ЭТАП 2: Тесты](#этап-2-тесты)
5. [ЭТАП 3: Реализация](#этап-3-реализация)
6. [ЭТАП 4: Верификация](#этап-4-верификация)
7. [ЭТАП 5: Документация](#этап-5-документация)
8. [Чек-лист приёмки](#чек-лист-приёмки)

---

## 🏗️ Архитектурные решения

### ADR-001: Выбор векторной библиотеки

**Решение:** FAISS (Facebook AI Similarity Search)

**Почему:**
- ✅ Локальное хранение (без внешних сервисов)
- ✅ Нет дополнительных зависимостей (только faiss-cpu)
- ✅ Полный контроль над индексом
- ✅ Быстрый поиск (< 100ms для 10K векторов)

**Недостатки и компенсации:**
- ⚠️ Нет персистентности из коробки → ручное сохранение index.faiss
- ⚠️ Нет фильтрации до поиска → пост-фильтрация результатов
- ⚠️ Нет встроенного chunking → свой ChunkingService

---

### ADR-002: Архитектура индексов

**Решение:** Раздельные индексы на каждый источник

```
data/vector/
├── knowledge_index.faiss    ← Индекс knowledge base
├── knowledge_metadata.json  ← Метаданные knowledge
├── history_index.faiss      ← Индекс истории
├── history_metadata.json    ← Метаданные истории
├── docs_index.faiss         ← Индекс документации
├── docs_metadata.json       ← Метаданные документации
├── books_index.faiss        ← Индекс книг
├── books_metadata.json      ← Метаданные книг
└── config.json              ← Общая конфигурация
```

**Почему раздельные:**
- ✅ Нет проблемы пустых результатов при фильтрации
- ✅ Фильтрация = выбор индекса (быстро)
- ✅ Изоляция сбоев (один индекс упал — другие работают)
- ✅ Проще масштабирование

**Недостатки:**
- ⚠️ Поиск по всем источникам = N запросов (но < 1 сек для 4 индексов)
- ⚠️ Больше файлов (8 вместо 2)

---

### ADR-003: Навыки

**Решение:** Отдельный навык на каждый источник

| Навык | Источник | Индекс |
|-------|----------|-------|
| `VectorKnowledgeTool` | Knowledge base | knowledge_index.faiss |
| `VectorHistoryTool` | History | history_index.faiss |
| `VectorDocsTool` | Documentation | docs_index.faiss |
| `VectorBooksTool` | Books | books_index.faiss + SQL |

**Почему отдельные:**
- ✅ Агент явно выбирает источник
- ✅ Нет поиска по всем источникам (не нужен мультиплексор)
- ✅ Разные промпты для разных источников
- ✅ Проще код (нет сложной логики выбора)

---

### ADR-004: VectorBooksTool — гибридный инструмент

**Решение:** VectorBooksTool содержит всю логику работы с книгами

**Capabilities:**
1. `search` — семантический поиск (FAISS)
2. `get_book_text` — полный текст книги (SQL)
3. `get_chapter_text` — текст главы (SQL)
4. `analyze_character` — LLM анализ героя
5. `find_books_by_character_gender` — поиск по полу героя

**Почему не отдельно BookAnalysisTool:**
- ✅ Нет дублирования кода
- ✅ Меньше файлов
- ✅ Вся логика в одном месте
- ✅ Достаточно для одного сценария использования

---

### ADR-005: Гибридный поиск для книг

**Архитектура:**
```
┌─────────────────────────────────────────────────────────────┐
│                    VectorBooksTool                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ FAISS        │  │ SQL          │  │ LLM          │      │
│  │ (поиск)      │  │ (текст)      │  │ (анализ)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  + AnalysisCache (кэш результатов анализа, 7 дней)         │
└─────────────────────────────────────────────────────────────┘
```

**Сценарии:**

| Запрос | Инструмент | Хранение |
|--------|------------|----------|
| "найди сцену бала" | VectorBooksTool.search | FAISS (чанки) |
| "дай полный текст" | VectorBooksTool.get_book_text | SQL (полный) |
| "кто главный герой?" | VectorBooksTool.analyze_character | LLM + кэш |
| "герой мужчина?" | VectorBooksTool.find_books_by_character_gender | LLM + SQL + FAISS |

---

### ADR-006: Кэширование анализа

**Решение:** AnalysisCache с TTL 7 дней

**Структура:**
```
data/cache/book_analysis/
├── character_analysis_1.json
├── character_analysis_2.json
└── ...
```

**Формат:**
```json
{
    "book_id": 1,
    "main_character": "Евгений Онегин",
    "gender": "male",
    "confidence": 0.95,
    "analyzed_at": "2026-02-19T10:00:00Z",
    "cached_at": "2026-02-19T10:00:00Z",
    "expires_at": "2026-02-26T10:00:00Z"
}
```

**Инвалидация:**
- При обновлении текста книги → удалить кэш
- При переиндексации → удалить кэш

---

### ADR-007: Метаданные чанка

**Структура:**
```json
{
    "chunk_id": "book_chunk_0001_0025",
    "document_id": "book_0001",
    "source": "books",
    "content": "текст чанка (500 символов)",
    "vector_id": 25,
    
    "book_metadata": {
        "book_id": 1,
        "book_title": "Евгений Онегин",
        "author_id": 1,
        "author_name": "Александр Пушкин",
        "year": 1825,
        "genre": "roman"
    },
    
    "chunk_metadata": {
        "chapter": 5,
        "chunk_index": 25,
        "total_chunks": 150
    },
    
    "sql_reference": {
        "enabled": true,
        "table": "book_texts",
        "join_columns": {"book_id": 1, "chapter": 5}
    }
}
```

**Важно:** Хранить минимум в FAISS, полные данные в SQL.

---

## 📁 Структура файлов

### Создаваемые файлы

```
core/models/types/
├── vector_types.py              ← Модели векторного поиска
└── book_analysis.py             ← Модели анализа книг

core/config/
└── vector_config.py             ← Конфигурация vector search

core/infrastructure/providers/vector/
├── base_faiss_provider.py       ← Базовый класс
├── faiss_provider.py            ← FAISS реализация
├── embedding_provider.py        ← SentenceTransformers
├── chunking_service.py          ← Chunking
└── mock_faiss_provider.py       ← Mock для тестов

core/infrastructure/cache/
└── analysis_cache.py            ← Кэш анализа

core/application/tools/
├── vector_knowledge_tool.py     ← Навык knowledge
├── vector_history_tool.py       ← Навык history
├── vector_docs_tool.py          ← Навык docs
└── vector_books_tool.py         ← Навык books (гибридный)

core/application/services/
└── book_indexing_service.py     ← Индексация книг

core/common/exceptions/
└── vector_exceptions.py         ← Исключения

data/contracts/tool/
├── vector_knowledge/            ← Контракты knowledge
│   ├── search_input_v1.0.0.yaml
│   └── search_output_v1.0.0.yaml
├── vector_history/              ← Контракты history
│   ├── search_input_v1.0.0.yaml
│   └── search_output_v1.0.0.yaml
├── vector_docs/                 ← Контракты docs
│   ├── search_input_v1.0.0.yaml
│   └── search_output_v1.0.0.yaml
└── vector_books/                ← Контракты books
    ├── search_input_v1.0.0.yaml
    ├── search_output_v1.0.0.yaml
    ├── get_book_text_input_v1.0.0.yaml
    ├── get_book_text_output_v1.0.0.yaml
    ├── analyze_character_input_v1.0.0.yaml
    ├── analyze_character_output_v1.0.0.yaml
    ├── find_books_by_gender_input_v1.0.0.yaml
    └── find_books_by_gender_output_v1.0.0.yaml

data/manifests/tools/
├── vector_knowledge_tool/
│   └── manifest.yaml
├── vector_history_tool/
│   └── manifest.yaml
├── vector_docs_tool/
│   └── manifest.yaml
└── vector_books_tool/
    └── manifest.yaml

data/vector/                       ← Индексы (создаются при индексации)
├── knowledge_index.faiss
├── knowledge_metadata.json
├── history_index.faiss
├── history_metadata.json
├── docs_index.faiss
├── docs_metadata.json
├── books_index.faiss
├── books_metadata.json
└── config.json

data/cache/book_analysis/          ← Кэш (создаётся автоматически)
└── *.json

tests/unit/models/
├── test_vector_types.py
└── test_book_analysis.py

tests/unit/config/
└── test_vector_config.py

tests/unit/infrastructure/vector/
├── test_faiss_provider.py
├── test_embedding_provider.py
├── test_chunking_service.py
└── test_analysis_cache.py

tests/unit/tools/
├── test_vector_knowledge_tool.py
├── test_vector_history_tool.py
├── test_vector_docs_tool.py
└── test_vector_books_tool.py

tests/integration/vector/
├── test_faiss_integration.py
└── test_vector_tools_integration.py

tests/e2e/vector/
├── test_knowledge_search_e2e.py
├── test_history_search_e2e.py
├── test_docs_search_e2e.py
├── test_books_search_e2e.py
├── test_book_analysis_e2e.py
└── test_find_books_by_gender_e2e.py

benchmarks/
└── test_vector_search.py

docs/api/
└── vector_search_api.md

docs/guides/
├── vector_search.md
└── vector_books_tool.md

examples/
└── vector_search_examples.py
```

---

## ЭТАП 1: Модели данных

### 1.1 Модели (core/models/types/vector_types.py)

**Задачи:**
- [ ] Создать `VectorSearchResult`
- [ ] Создать `VectorQuery`
- [ ] Создать `VectorDocument`
- [ ] Создать `VectorChunk`
- [ ] Создать `VectorIndexInfo`
- [ ] Создать `VectorSearchStats`

**Код:**
```python
# core/models/types/vector_types.py
"""Модели данных для векторного поиска."""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class VectorSearchResult(BaseModel):
    """
    Результат векторного поиска.
    
    Attributes:
        id: Уникальный ID результата
        document_id: ID документа
        chunk_id: ID чанка (опционально)
        score: Оценка релевантности (0-1)
        content: Содержимое чанка
        metadata: Метаданные документа
        source: Источник (knowledge/history/docs/books)
    """
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    score: float = Field(ge=0.0, le=1.0)
    content: str
    metadata: Dict[str, Any]
    source: Literal["knowledge", "history", "docs", "books"]
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "result_001",
                "document_id": "doc_123",
                "chunk_id": "chunk_456",
                "score": 0.92,
                "content": "текст чанка...",
                "metadata": {"category": "technical"},
                "source": "knowledge"
            }
        }


class VectorQuery(BaseModel):
    """
    Запрос на векторный поиск.
    
    Attributes:
        query: Текстовый запрос (или vector)
        vector: Вектор запроса (или query)
        top_k: Количество результатов
        min_score: Минимальный порог
        filters: Фильтры по метаданным
        offset: Смещение для пагинации
    """
    query: Optional[str] = None
    vector: Optional[List[float]] = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None
    offset: int = Field(default=0, ge=0)
    
    @validator('filters')
    def validate_filters(cls, v):
        """Валидация фильтров."""
        if v is None:
            return v
        
        allowed_keys = {'source', 'category', 'tags', 'date_from', 'date_to', 
                       'author_id', 'book_id', 'genre', 'year_from', 'year_to'}
        invalid = set(v.keys()) - allowed_keys
        if invalid:
            raise ValueError(f"Invalid filter keys: {invalid}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "векторный поиск",
                "top_k": 10,
                "min_score": 0.5,
                "filters": {"source": ["knowledge"]}
            }
        }


class VectorDocument(BaseModel):
    """
    Документ для индексации.
    
    Attributes:
        id: Уникальный ID (генерируется если не указан)
        content: Содержимое документа
        metadata: Метаданные
        source: Источник
        chunk_size: Размер чанка
        chunk_overlap: Перекрытие чанков
    """
    id: Optional[str] = None
    content: str
    metadata: Dict[str, Any]
    source: Literal["knowledge", "history", "docs", "books"]
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "текст документа...",
                "metadata": {"category": "technical"},
                "source": "knowledge",
                "chunk_size": 500,
                "chunk_overlap": 50
            }
        }


class VectorChunk(BaseModel):
    """
    Чанк документа.
    
    Attributes:
        id: Уникальный ID чанка
        document_id: ID родительского документа
        content: Содержимое чанка
        vector: Вектор эмбеддинга
        metadata: Метаданные чанка
        index: Индекс чанка в документе
        chapter: Номер главы (для книг)
    """
    id: str
    document_id: str
    content: str
    vector: Optional[List[float]] = None
    metadata: Dict[str, Any]
    index: int
    chapter: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "chunk_001",
                "document_id": "doc_123",
                "content": "текст чанка...",
                "index": 0,
                "chapter": 1
            }
        }


class VectorIndexInfo(BaseModel):
    """
    Информация об индексе.
    
    Attributes:
        source: Источник
        total_documents: Количество документов
        total_chunks: Количество чанков
        index_size_mb: Размер индекса в MB
        dimension: Размерность векторов
        index_type: Тип индекса (Flat/IVF/HNSW)
        created_at: Дата создания
        updated_at: Дата обновления
    """
    source: str
    total_documents: int
    total_chunks: int
    index_size_mb: float
    dimension: int
    index_type: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "source": "knowledge",
                "total_documents": 50,
                "total_chunks": 500,
                "index_size_mb": 5.2,
                "dimension": 384,
                "index_type": "Flat",
                "created_at": "2026-02-19T10:00:00Z",
                "updated_at": "2026-02-19T12:00:00Z"
            }
        }


class VectorSearchStats(BaseModel):
    """
    Статистика поиска.
    
    Attributes:
        query_time_ms: Время выполнения запроса
        total_found: Общее количество найденных
        returned_count: Количество возвращённых
        filters_applied: Применённые фильтры
    """
    query_time_ms: float
    total_found: int
    returned_count: int
    filters_applied: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_time_ms": 45.2,
                "total_found": 150,
                "returned_count": 10,
                "filters_applied": ["source"]
            }
        }
```

**Тесты (tests/unit/models/test_vector_types.py):**
```python
"""Тесты моделей векторного поиска."""

import pytest
from datetime import datetime
from core.models.types.vector_types import (
    VectorSearchResult,
    VectorQuery,
    VectorDocument,
    VectorChunk,
    VectorIndexInfo,
    VectorSearchStats
)


class TestVectorSearchResult:
    """Тесты VectorSearchResult."""
    
    def test_create_valid(self):
        """Создание валидного результата."""
        result = VectorSearchResult(
            id="result_001",
            document_id="doc_123",
            chunk_id="chunk_456",
            score=0.92,
            content="текст чанка",
            metadata={"category": "technical"},
            source="knowledge"
        )
        assert result.id == "result_001"
        assert result.score == 0.92
        assert result.source == "knowledge"
    
    def test_score_validation(self):
        """Валидация score (0-1)."""
        with pytest.raises(ValueError):
            VectorSearchResult(
                id="r1", document_id="d1", score=1.5,
                content="text", metadata={}, source="knowledge"
            )
        
        with pytest.raises(ValueError):
            VectorSearchResult(
                id="r1", document_id="d1", score=-0.1,
                content="text", metadata={}, source="knowledge"
            )
    
    def test_source_validation(self):
        """Валидация source."""
        with pytest.raises(ValueError):
            VectorSearchResult(
                id="r1", document_id="d1", score=0.9,
                content="text", metadata={}, source="invalid"
            )


class TestVectorQuery:
    """Тесты VectorQuery."""
    
    def test_create_with_query(self):
        """Создание с текстовым запросом."""
        query = VectorQuery(
            query="векторный поиск",
            top_k=10
        )
        assert query.query == "векторный поиск"
        assert query.top_k == 10
    
    def test_create_with_vector(self):
        """Создание с вектором."""
        query = VectorQuery(
            vector=[0.1] * 384,
            top_k=10
        )
        assert len(query.vector) == 384
    
    def test_top_k_validation(self):
        """Валидация top_k."""
        with pytest.raises(ValueError):
            VectorQuery(query="test", top_k=0)
        
        with pytest.raises(ValueError):
            VectorQuery(query="test", top_k=101)
    
    def test_filters_validation(self):
        """Валидация фильтров."""
        # Валидные фильтры
        query = VectorQuery(
            query="test",
            filters={"source": ["knowledge"], "category": ["technical"]}
        )
        assert query.filters is not None
        
        # Невалидные фильтры
        with pytest.raises(ValueError):
            VectorQuery(
                query="test",
                filters={"invalid_filter": "value"}
            )


class TestVectorDocument:
    """Тесты VectorDocument."""
    
    def test_create_valid(self):
        """Создание валидного документа."""
        doc = VectorDocument(
            content="текст документа",
            metadata={"category": "technical"},
            source="knowledge"
        )
        assert doc.content == "текст документа"
        assert doc.source == "knowledge"
    
    def test_chunk_size_validation(self):
        """Валидация chunk_size."""
        with pytest.raises(ValueError):
            VectorDocument(
                content="text", metadata={}, source="knowledge",
                chunk_size=50  # < 100
            )


class TestVectorChunk:
    """Тесты VectorChunk."""
    
    def test_create_valid(self):
        """Создание валидного чанка."""
        chunk = VectorChunk(
            id="chunk_001",
            document_id="doc_123",
            content="текст чанка",
            index=0
        )
        assert chunk.id == "chunk_001"
        assert chunk.index == 0


class TestVectorIndexInfo:
    """Тесты VectorIndexInfo."""
    
    def test_create_valid(self):
        """Создание валидной информации."""
        info = VectorIndexInfo(
            source="knowledge",
            total_documents=50,
            total_chunks=500,
            index_size_mb=5.2,
            dimension=384,
            index_type="Flat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert info.total_documents == 50
        assert info.dimension == 384
```

**Критерии завершения:**
- [ ] Все 6 моделей созданы
- [ ] Все валидаторы работают
- [ ] Тесты проходят (100%)
- [ ] Покрытие ≥ 90%
- [ ] Docstrings написаны

---

### 1.2 Модели анализа книг (core/models/types/book_analysis.py)

**Задачи:**
- [ ] Создать `CharacterAnalysis`
- [ ] Создать `BookWithCharacter`

**Код:**
```python
# core/models/types/book_analysis.py
"""Модели для анализа книг."""

from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, List
from datetime import datetime


class CharacterAnalysis(BaseModel):
    """
    Результат анализа главного героя.
    
    Attributes:
        book_id: ID книги
        main_character: Имя главного героя
        gender: Пол героя (male/female/unknown)
        description: Краткое описание
        confidence: Уверенность (0-1)
        reasoning: Обоснование вывода
        analyzed_at: Дата анализа
        error: Ошибка (если была)
    """
    book_id: int
    main_character: Optional[str] = None
    gender: Optional[Literal["male", "female", "unknown"]] = None
    description: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    @validator('gender')
    def validate_gender(cls, v):
        """Валидация пола."""
        if v is not None and v not in ["male", "female", "unknown"]:
            raise ValueError(f"Invalid gender: {v}")
        return v
    
    def is_valid(self) -> bool:
        """Проверка валидности анализа."""
        return self.error is None and self.confidence >= 0.8
    
    def to_dict(self) -> dict:
        """Конвертация в dict."""
        return {
            "book_id": self.book_id,
            "main_character": self.main_character,
            "gender": self.gender,
            "description": self.description,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "analyzed_at": self.analyzed_at.isoformat(),
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CharacterAnalysis":
        """Создание из dict."""
        return cls(
            book_id=data["book_id"],
            main_character=data.get("main_character"),
            gender=data.get("gender"),
            description=data.get("description"),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning"),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            error=data.get("error")
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "book_id": 1,
                "main_character": "Евгений Онегин",
                "gender": "male",
                "description": "Молодой дворянин, скучающий аристократ",
                "confidence": 0.95,
                "reasoning": "Имя героя указано в названии, мужской пол очевиден из текста",
                "analyzed_at": "2026-02-19T10:00:00Z"
            }
        }


class BookWithCharacter(BaseModel):
    """
    Книга с информацией о главном герое.
    
    Attributes:
        book_id: ID книги
        book_title: Название книги
        author_name: Имя автора
        main_character: Имя главного героя
        gender: Пол героя
        confidence: Уверенность
    """
    book_id: int
    book_title: str
    author_name: str
    main_character: Optional[str]
    gender: Optional[str]
    confidence: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "book_id": 1,
                "book_title": "Евгений Онегин",
                "author_name": "Александр Пушкин",
                "main_character": "Евгений Онегин",
                "gender": "male",
                "confidence": 0.95
            }
        }
```

**Тесты (tests/unit/models/test_book_analysis.py):**
```python
"""Тесты моделей анализа книг."""

import pytest
from datetime import datetime
from core.models.types.book_analysis import CharacterAnalysis, BookWithCharacter


class TestCharacterAnalysis:
    """Тесты CharacterAnalysis."""
    
    def test_create_valid(self):
        """Создание валидного анализа."""
        analysis = CharacterAnalysis(
            book_id=1,
            main_character="Евгений Онегин",
            gender="male",
            confidence=0.95,
            reasoning="Имя героя в названии"
        )
        assert analysis.book_id == 1
        assert analysis.main_character == "Евгений Онегин"
        assert analysis.gender == "male"
        assert analysis.confidence == 0.95
    
    def test_is_valid(self):
        """Проверка валидности."""
        valid = CharacterAnalysis(
            book_id=1, main_character="Test", gender="male",
            confidence=0.9
        )
        assert valid.is_valid() is True
        
        invalid = CharacterAnalysis(
            book_id=1, main_character="Test", gender="male",
            confidence=0.5  # < 0.8
        )
        assert invalid.is_valid() is False
        
        error = CharacterAnalysis(
            book_id=1, error="Analysis failed"
        )
        assert error.is_valid() is False
    
    def test_to_from_dict(self):
        """Конвертация в dict и обратно."""
        original = CharacterAnalysis(
            book_id=1,
            main_character="Test",
            gender="female",
            confidence=0.9
        )
        
        data = original.to_dict()
        restored = CharacterAnalysis.from_dict(data)
        
        assert restored.book_id == original.book_id
        assert restored.main_character == original.main_character
        assert restored.gender == original.gender
    
    def test_gender_validation(self):
        """Валидация gender."""
        with pytest.raises(ValueError):
            CharacterAnalysis(
                book_id=1, gender="invalid"
            )


class TestBookWithCharacter:
    """Тесты BookWithCharacter."""
    
    def test_create_valid(self):
        """Создание валидной книги."""
        book = BookWithCharacter(
            book_id=1,
            book_title="Евгений Онегин",
            author_name="Александр Пушкин",
            main_character="Евгений Онегин",
            gender="male",
            confidence=0.95
        )
        assert book.book_title == "Евгений Онегин"
        assert book.gender == "male"
```

**Критерии завершения:**
- [ ] Обе модели созданы
- [ ] Валидаторы работают
- [ ] Тесты проходят (100%)
- [ ] Методы to_dict/from_dict работают

---

### 1.3 Конфигурация (core/config/vector_config.py)

**Задачи:**
- [ ] Создать `FAISSConfig`
- [ ] Создать `EmbeddingConfig`
- [ ] Создать `ChunkingConfig`
- [ ] Создать `VectorStorageConfig`
- [ ] Создать `AnalysisCacheConfig`
- [ ] Создать `VectorSearchConfig`
- [ ] Обновить `SystemConfig`

**Код:**
```python
# core/config/vector_config.py
"""Конфигурация векторного поиска."""

from pydantic import BaseModel, Field, validator
from typing import Literal, Dict, Optional


class FAISSConfig(BaseModel):
    """
    Конфигурация FAISS индекса.
    
    Attributes:
        index_type: Тип индекса (Flat/IVF/HNSW)
        nlist: Количество кластеров (для IVF)
        nprobe: Количество кластеров для поиска (для IVF)
        metric: Метрика расстояния (L2/IP)
    """
    index_type: Literal["Flat", "IVF", "HNSW"] = "Flat"
    nlist: int = Field(default=100, ge=1)
    nprobe: int = Field(default=10, ge=1)
    metric: Literal["L2", "IP"] = "IP"  # Inner Product для косинусного
    
    @validator('nprobe')
    def validate_nprobe(cls, v, values):
        """nprobe не должен превышать nlist."""
        if 'nlist' in values and v > values['nlist']:
            raise ValueError("nprobe cannot be greater than nlist")
        return v


class EmbeddingConfig(BaseModel):
    """
    Конфигурация эмбеддингов.
    
    Attributes:
        model_name: Модель SentenceTransformers
        dimension: Размерность векторов
        device: Устройство (cpu/cuda)
        batch_size: Размер батча
        max_length: Максимальная длина токенов
    """
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = 32
    max_length: int = 512


class ChunkingConfig(BaseModel):
    """
    Конфигурация chunking.
    
    Attributes:
        enabled: Включён ли chunking
        chunk_size: Размер чанка (символы)
        chunk_overlap: Перекрытие (символы)
    """
    enabled: bool = True
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class VectorStorageConfig(BaseModel):
    """
    Конфигурация хранилища.
    
    Attributes:
        base_path: Базовый путь к индексам
        backup_enabled: Включены ли бэкапы
        backup_interval_hours: Интервал бэкапов
    """
    base_path: str = "./data/vector"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


class AnalysisCacheConfig(BaseModel):
    """
    Конфигурация кэша анализа.
    
    Attributes:
        enabled: Включён ли кэш
        ttl_hours: Время жизни (часы)
        max_size_mb: Максимальный размер (MB)
    """
    enabled: bool = True
    ttl_hours: int = 168  # 7 дней
    max_size_mb: int = 100


class VectorSearchConfig(BaseModel):
    """
    Общая конфигурация векторного поиска.
    
    Attributes:
        enabled: Включён ли векторный поиск
        indexes: Пути к индексам по источникам
        faiss: Конфигурация FAISS
        embedding: Конфигурация эмбеддингов
        chunking: Конфигурация chunking
        storage: Конфигурация хранилища
        cache: Конфигурация кэша
        default_top_k: top_k по умолчанию
        max_top_k: Максимальный top_k
        default_min_score: min_score по умолчанию
        max_workers: Количество воркеров
        timeout_seconds: Таймаут операций
    """
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
    
    max_workers: int = 4
    timeout_seconds: float = 30.0
    
    @validator('indexes')
    def validate_indexes(cls, v):
        """Валидация индексов."""
        required = {"knowledge", "history", "docs", "books"}
        if set(v.keys()) != required:
            raise ValueError(f"Indexes must include: {required}")
        return v


# Обновление SystemConfig в core/config/models.py
# Добавить поле:
# vector_search: Optional[VectorSearchConfig] = None
```

**Тесты (tests/unit/config/test_vector_config.py):**
```python
"""Тесты конфигурации векторного поиска."""

import pytest
from core.config.vector_config import (
    FAISSConfig,
    EmbeddingConfig,
    ChunkingConfig,
    VectorStorageConfig,
    AnalysisCacheConfig,
    VectorSearchConfig
)


class TestFAISSConfig:
    """Тесты FAISSConfig."""
    
    def test_default_values(self):
        """Значения по умолчанию."""
        config = FAISSConfig()
        assert config.index_type == "Flat"
        assert config.nlist == 100
        assert config.nprobe == 10
        assert config.metric == "IP"
    
    def test_nprobe_validation(self):
        """Валидация nprobe."""
        with pytest.raises(ValueError):
            FAISSConfig(nlist=50, nprobe=100)  # nprobe > nlist


class TestVectorSearchConfig:
    """Тесты VectorSearchConfig."""
    
    def test_default_values(self):
        """Значения по умолчанию."""
        config = VectorSearchConfig()
        assert config.enabled is True
        assert config.default_top_k == 10
        assert config.max_top_k == 100
        assert len(config.indexes) == 4
    
    def test_indexes_validation(self):
        """Валидация индексов."""
        with pytest.raises(ValueError):
            VectorSearchConfig(indexes={"knowledge": "k.faiss"})  # Неполный
        
        # Полный набор
        config = VectorSearchConfig(
            indexes={
                "knowledge": "k.faiss",
                "history": "h.faiss",
                "docs": "d.faiss",
                "books": "b.faiss"
            }
        )
        assert len(config.indexes) == 4
```

**Критерии завершения:**
- [ ] Все 6 конфигов созданы
- [ ] Валидаторы работают
- [ ] Интеграция с SystemConfig
- [ ] Тесты проходят

---

## Чек-лист приёмки

### ЭТАП 1: Модели данных

```
□ core/models/types/vector_types.py создан
□ core/models/types/book_analysis.py создан
□ core/config/vector_config.py создан
□ SystemConfig обновлён
□ Все модели валидируются Pydantic
□ Все тесты проходят (100%)
□ Покрытие ≥ 90%
□ Docstrings написаны
```

### ЭТАП 2: Тесты

```
□ Mock провайдеры созданы
□ Unit тесты FAISSProvider написаны
□ Unit тесты EmbeddingProvider написаны
□ Unit тесты VectorBooksTool написаны
□ Integration тесты написаны
□ E2E тесты написаны
□ Тесты падают (TDD)
□ Покрытие ≥ 85%
```

### ЭТАП 3: Реализация

```
□ FAISSProvider реализован
□ EmbeddingProvider реализован
□ ChunkingService реализован
□ VectorBooksTool реализован (все 5 capabilities)
□ BookIndexingService реализован
□ AnalysisCache реализован
□ Интеграция с InfrastructureContext
□ Интеграция с ApplicationContext
□ Обработка ошибок реализована
□ Логирование добавлено
```

### ЭТАП 4: Верификация

```
□ Все unit тесты проходят
□ Все integration тесты проходят
□ Все e2e тесты проходят
□ Performance p95 < 1000ms
□ Code review завершён
□ Безопасность проверена
```

### ЭТАП 5: Документация

```
□ API документация создана
□ Руководства созданы
□ Примеры добавлены
□ CHANGELOG обновлён
```

---

*Документ создан: 2026-02-19*  
*Версия: 1.0.0*  
*Статус: ✅ Утверждено*

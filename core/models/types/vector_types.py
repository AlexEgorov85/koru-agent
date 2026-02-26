"""
Модели данных для векторного поиска.

Универсальные модели для работы с любым источником:
- knowledge
- history
- docs
- books
"""

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
    source: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "result_001",
                "document_id": "book_123",
                "chunk_id": "chunk_456",
                "score": 0.92,
                "content": "текст чанка...",
                "metadata": {"book_title": "Евгений Онегин"},
                "source": "books"
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
        
        allowed_keys = {
            'source', 'category', 'tags', 'date_from', 'date_to',
            'author_id', 'book_id', 'genre', 'year_from', 'year_to'
        }
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
                "filters": {"source": ["books"]}
            }
        }


class VectorDocument(BaseModel):
    """
    Документ для индексации.
    
    Attributes:
        id: Уникальный ID (генерируется если не указан)
        content: Содержимое документа
        metadata: Метаданные
        source: Источник (knowledge/history/docs/books)
        chunk_size: Размер чанка
        chunk_overlap: Перекрытие чанков
    """
    id: Optional[str] = None
    content: str
    metadata: Dict[str, Any]
    source: str
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
    metadata: Dict[str, Any] = Field(default_factory=dict)
    index: int
    chapter: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "chunk_001",
                "document_id": "book_123",
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
                "source": "books",
                "total_documents": 150,
                "total_chunks": 7500,
                "index_size_mb": 75.2,
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

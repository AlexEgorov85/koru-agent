"""
Конфигурация векторного поиска.

Универсальная конфигурация для всех компонентов:
- FAISS индексы
- Embedding провайдер
- Chunking сервис
- Кэширование
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Dict, Optional, List, Any


# ===========================================================================
# КОНФИГУРАЦИЯ ИСТОЧНИКОВ ДАННЫХ
# ===========================================================================

SOURCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "authors": {
        "schema": "Lib",
        "table": "authors",
        "select_cols": "id, first_name, last_name, birth_date",
        "text_fields": ["first_name", "last_name"],
        "metadata_fields": ["id", "first_name", "last_name", "birth_date"],
        "pk_column": "id",
        "where_clause": "WHERE last_name IS NOT NULL",
        "order_by": "ORDER BY last_name, first_name",
        "instruction": "Дан вопрос о людях (авторах). Необходимо найти абзац текста с ответом о человеке.",
    },
    "audits": {
        "schema": "oarb",
        "table": "audits",
        "select_cols": "id, title, audit_type, planned_date, actual_date, status, auditee_entity",
        "text_fields": ["title", "auditee_entity", "audit_type"],
        "metadata_fields": ["id", "title", "audit_type", "status", "auditee_entity"],
        "pk_column": "id",
        "where_clause": "WHERE title IS NOT NULL",
        "order_by": "ORDER BY id",
        "instruction": "Дан вопрос об аудите. Необходимо найти абзац текста с описанием аудита.",
    },
    "violations": {
        "schema": "oarb",
        "table": "violations v",
        "select_cols": """v.id, v.violation_code, v.description, v.recommendation,
                          v.severity, v.status, v.responsible, v.deadline, v.audit_id,
                          a.title as audit_title, a.status as audit_status""",
        "text_fields": ["description", "violation_code", "audit_title"],
        "metadata_fields": ["id", "violation_code", "description", "severity", "status", "responsible", "deadline", "audit_id", "audit_title", "audit_status"],
        "pk_column": "id",
        "where_clause": "WHERE v.description IS NOT NULL",
        "order_by": "ORDER BY v.id",
        "join_clause": "JOIN oarb.audits a ON v.audit_id = a.id",
        "instruction": "Дан вопрос о нарушении. Необходимо найти абзац текста с описанием нарушения.",
    },
    "books": {
        "schema": "Lib",
        "table": "books",
        "select_cols": "id, title, isbn, publication_date, author_id",
        "text_fields": ["title"],
        "metadata_fields": ["id", "title", "isbn", "publication_date", "author_id"],
        "pk_column": "id",
        "where_clause": "WHERE title IS NOT NULL",
        "order_by": "ORDER BY title",
        "instruction": "Дан вопрос о книге. Необходимо найти абзац текста с названием или описанием книги.",
    }
}


class FAISSConfig(BaseModel):
    """
    Конфигурация FAISS индекса.

    Attributes:
        index_type: Тип индекса (Flat/IVF/HNSW)
        nlist: Количество кластеров (для IVF)
        nprobe: Количество кластеров для поиска (для IVF)
        metric: Метрика расстояния (L2/IP)
        hnsw_ef_construction: Качество построения (для HNSW, больше = точнее, медленнее)
        hnsw_ef_search: Качество поиска (для HNSW, больше = точнее, медленнее)
    """
    index_type: Literal["Flat", "IVF", "HNSW"] = "Flat"
    nlist: int = Field(default=100, ge=1)
    nprobe: int = Field(default=10, ge=1)
    metric: Literal["L2", "IP"] = "IP"  # Inner Product для косинусного
    hnsw_ef_construction: int = Field(default=40, ge=1, le=500)
    hnsw_ef_search: int = Field(default=16, ge=1, le=500)

    @field_validator('nprobe')
    @classmethod
    def validate_nprobe(cls, v, info):
        """nprobe не должен превышать nlist."""
        if 'nlist' in info.data and v > info.data['nlist']:
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
        instruction: Инструкция для query (Instruct: {task}\nQuery: {query})
        use_instruction: Использовать инструкцию для запросов
        local_model_path: Путь к локальной папке с моделью (переопределяет model_name)
    """
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = 32
    max_length: int = 512
    instruction: Optional[str] = "Дан вопрос, необходимо найти абзац текста с ответом"
    use_instruction: bool = True
    local_model_path: Optional[str] = Field(
        default=None, 
        description="Путь к локальной папке с моделью (переопределяет model_name)"
    )


class ChunkingConfig(BaseModel):
    """
    Конфигурация chunking.

    Attributes:
        enabled: Включён ли chunking
        strategy: Стратегия (text/semantic/hybrid)
        chunk_size: Размер чанка (символы)
        chunk_overlap: Перекрытие (символы)
        min_chunk_size: Минимальный размер чанка (символы)
        separators: Разделители по приоритету
    """
    enabled: bool = True
    strategy: Literal["text", "semantic", "hybrid"] = "text"
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)
    min_chunk_size: int = Field(default=100, ge=10, le=500)
    separators: List[str] = [
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
    enabled: bool = True  # ✅ Включено по умолчанию для production использования
    
    indexes: Dict[str, str] = {
        "books": "books_index.faiss",
        "authors": "authors_index.faiss",
        "audits": "audits_index.faiss",
        "violations": "violations_index.faiss",
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

    @field_validator('indexes')
    @classmethod
    def validate_indexes(cls, v):
        """Валидация индексов (допускается любой набор)."""
        allowed = {"books", "authors", "audits", "violations", "docs", "knowledge"}
        unknown = set(v.keys()) - allowed
        if unknown:
            raise ValueError(f"Unknown indexes: {unknown}. Allowed: {allowed}")
        return v

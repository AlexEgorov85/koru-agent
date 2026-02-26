"""
Конфигурация векторного поиска.

Универсальная конфигурация для всех компонентов:
- FAISS индексы
- Embedding провайдер
- Chunking сервис
- Кэширование
"""

from pydantic import BaseModel, Field, validator
from typing import Literal, Dict, Optional, List


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
        strategy: Стратегия (text/semantic/hybrid)
        chunk_size: Размер чанка (символы)
        chunk_overlap: Перекрытие (символы)
        separators: Разделители по приоритету
    """
    enabled: bool = True
    strategy: Literal["text", "semantic", "hybrid"] = "text"
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)
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

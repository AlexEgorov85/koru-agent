"""
SentenceTransformers провайдер для генерации эмбеддингов.
"""

from typing import List, Optional
from core.infrastructure.providers.embedding.base_embedding_provider import IEmbeddingProvider
from core.config.vector_config import EmbeddingConfig


class SentenceTransformersProvider(IEmbeddingProvider):
    """
    Реализация Embedding провайдера через SentenceTransformers.
    
    Модель по умолчанию: all-MiniLM-L6-v2
    - Размерность: 384
    - Скорость: ~1000 предложений/сек (CPU)
    - Качество: STS benchmark ~0.82
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.model = None
    
    async def initialize(self):
        """Инициализация модели."""
        try:
            from sentence_transformers import SentenceTransformer
            
            self.model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device
            )
        except ImportError:
            raise ImportError(
                "SentenceTransformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
    
    async def generate(self, texts: List[str]) -> List[List[float]]:
        """Генерация эмбеддингов для текстов."""
        
        if not self.model:
            await self.initialize()
        
        if not texts:
            return []
        
        # Генерация батчами
        embeddings = self.model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        
        return embeddings.tolist()
    
    async def generate_single(self, text: str) -> List[float]:
        """Генерация эмбеддинга для одного текста."""
        embeddings = await self.generate([text])
        return embeddings[0] if embeddings else []
    
    def get_dimension(self) -> int:
        """Получить размерность векторов."""
        return self.config.dimension
    
    async def shutdown(self):
        """Закрытие провайдера."""
        self.model = None

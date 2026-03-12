"""
SentenceTransformers провайдер для генерации эмбеддингов.

Только локальная модель — онлайн загрузка отключена.
"""

import os
from pathlib import Path
from typing import List, Optional
from core.infrastructure.providers.embedding.base_embedding_provider import IEmbeddingProvider
from core.config.vector_config import EmbeddingConfig


# Полностью отключаем онлайн режим для HF Hub
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_NO_ONLINE'] = '1'


class SentenceTransformersProvider(IEmbeddingProvider):
    """
    Реализация Embedding провайдера через SentenceTransformers.

    Модель по умолчанию: all-MiniLM-L6-v2
    - Размерность: 384
    - Скорость: ~1000 предложений/сек (CPU)
    - Качество: STS benchmark ~0.82

    ⚠️ ТОЛЬКО ЛОКАЛЬНАЯ МОДЕЛЬ — онлайн загрузка отключена.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.model = None

    def _validate_local_model(self, model_path: str) -> None:
        """Проверка существования локальной модели."""
        # Если это путь к файлу/папке
        if os.path.exists(model_path):
            return
        
        # Если это имя модели (не путь), проверяем наличие в кэше
        if not any(x in model_path for x in ['/', '\\']):
            from huggingface_hub import try_to_load_from_cache
            try:
                # Проверяем кэш
                cache_path = try_to_load_from_cache(
                    repo_id=model_path,
                    filename='modules.json'
                )
                if cache_path is not None:
                    return
            except Exception:
                pass
        
        raise FileNotFoundError(
            f"Локальная модель не найдена: {model_path}\n"
            f"Онлайн загрузка отключена.\n"
            f"Скачайте модель командой:\n"
            f"  python download_model.py"
        )

    async def initialize(self):
        """Инициализация модели."""
        try:
            from sentence_transformers import SentenceTransformer

            # Проверяем существование локальной модели
            self._validate_local_model(self.config.model_name)

            self.model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device,
                local_files_only=True  # Только локальные файлы
            )
        except ImportError:
            raise ImportError(
                "SentenceTransformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
        except FileNotFoundError as e:
            # Пробрасываем нашу ошибку
            raise
        except Exception as e:
            raise RuntimeError(
                f"Не удалось загрузить локальную модель {self.config.model_name}: {e}\n"
                f"Онлайн загрузка отключена."
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

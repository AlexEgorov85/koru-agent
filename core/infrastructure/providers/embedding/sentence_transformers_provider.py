"""
SentenceTransformers провайдер для генерации эмбеддингов.

Только локальная модель — онлайн загрузка отключена.
"""

import os
from pathlib import Path
from typing import List, Optional
from core.infrastructure.providers.embedding.base_embedding_provider import IEmbeddingProvider
from core.config.vector_config import EmbeddingConfig

# Импортируем hf_hub_utils ДО блокировки онлайна
try:
    from huggingface_hub import try_to_load_from_cache
except ImportError:
    try_to_load_from_cache = None

# Полностью отключаем онлайн режим для HF Hub
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_NO_ONLINE'] = '1'


class SentenceTransformersProvider(IEmbeddingProvider):
    """
    Реализация Embedding провайдера через SentenceTransformers.

    Модель по умолчанию: Giga-Embeddings-instruct
    - Размерность: 2048
    - Тип: LLM-based embeddings (GigaChat Instruct)
    - Конфигурация: models/embedding/Giga-Embeddings-instruct

    ⚠️ ТОЛЬКО ЛОКАЛЬНАЯ МОДЕЛЬ — онлайн загрузка отключена.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.model = None

    def _validate_local_model(self, model_path: str) -> None:
        """Проверка существования локальной модели."""
        from pathlib import Path
        
        # Резолвим относительные пути относительно проекта
        path = Path(model_path)
        if not path.is_absolute():
            project_root = Path(__file__).parent.parent.parent.parent.parent
            path = project_root / model_path
        
        if path.exists():
            return

        if not any(x in model_path for x in ['/', '\\']):
            if try_to_load_from_cache is not None:
                # Пробуем разные форматы имени модели
                repo_ids = [
                    model_path,
                    f"sentence-transformers/{model_path}",
                    f"{model_path}-v1",  # fallback для других неймспейсов
                ]
                for repo_id in repo_ids:
                    try:
                        resolved_path = try_to_load_from_cache(
                            repo_id=repo_id,
                            filename='modules.json'
                        )
                        if resolved_path is not None:
                            return
                    except Exception:
                        pass

        raise FileNotFoundError(
            f"Локальная модель не найдена: {model_path}\n"
            f"Искали в: {path}\n"
            f"Также проверьте HF кэш: ~/.cache/huggingface/hub/\n"
            f"Онлайн загрузка отключена."
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

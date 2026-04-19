"""
Giga-Embeddings провайдер для генерации эмбеддингов.

Использует transformers напрямую (не SentenceTransformers) для Giga-Embeddings-instruct.

Особенности модели:
- Требует инструкцию перед запросом (query), но НЕ перед документами
- Шаблон: f'Instruct: {task}\nQuery: {query}'
- Для retrieval: "Дан вопрос, необходимо найти абзац текста с ответом"
- Для симметричных задач: инструкция перед каждым текстом
"""

import os
from typing import List, Optional
import torch
import numpy as np
from core.infrastructure.providers.embedding.base_embedding_provider import IEmbeddingProvider
from core.config.vector_config import EmbeddingConfig


class GigaEmbeddingsProvider(IEmbeddingProvider):
    """
    Провайдер для Giga-Embeddings-instruct модели.
    
    Особенности:
    - Загружается через transformers напрямую
    - Использует flash_attention_2 для ускорения (на CUDA)
    - Возвращает эмбеддинги через return_embeddings=True
    - Добавляет инструкцию только к query (не к документам при retrieval)
    
    Требования:
    - transformers==4.51.0
    - sentence-transformers==5.1.1
    - torch с поддержкой CUDA (желательно)
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.model = None
        self.tokenizer = None
        self._device = None

    def _apply_instruction(self, texts: List[str], use_instruction: bool = True) -> List[str]:
        """Добавляет инструкцию перед текстами (только для query).
        
        Шаблон: f'Instruct: {task_description}\nQuery: {query}'
        
        ВАЖНО: Инструкция добавляется только к query (запросам), НЕ к документам.
        Для retrieval задач документы должны быть без инструкции.
        """
        if not use_instruction or not self.config.instruction:
            return texts
        
        task = self.config.instruction
        return [f"Instruct: {task}\nQuery: {text}" for text in texts]

    async def initialize(self):
        """Инициализация модели и токенизатора."""
        try:
            from transformers import AutoTokenizer, AutoModel
            
            # Определяем устройство
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Токенизатор
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            # Модель
            attn_impl = "flash_attention_2" if self._device == "cuda" else "eager"
            torch_dtype = torch.bfloat16 if self._device == "cuda" else torch.float32
            
            self.model = AutoModel.from_pretrained(
                self.config.model_name,
                attn_implementation=attn_impl,
                torch_dtype=torch_dtype,
                trust_remote_code=True
            )
            self.model.eval()
            self.model.to(self._device)
            
        except ImportError as e:
            raise ImportError(
                f"Ошибка импорта: {e}\n"
                "Установите: pip install transformers==4.51.0 sentence-transformers==5.1.1"
            )
        except Exception as e:
            raise RuntimeError(
                f"Не удалось загрузить модель {self.config.model_name}: {e}"
            )

    async def generate(self, texts: List[str], apply_instruction: bool = True) -> List[List[float]]:
        """Генерация эмбеддингов для списка текстов.
        
        Args:
            texts: Список текстов для эмбеддинга
            apply_instruction: Добавить инструкцию перед текстами (для query)
        
        Для retrieval: apply_instruction=True для запросов, False для документов.
        """
        
        if not self.model:
            await self.initialize()
        
        if not texts:
            return []
        
        max_length = min(self.config.max_length, 4096)  # Giga поддерживает max 4096
        
        # Применяем инструкцию если нужно
        processed_texts = self._apply_instruction(texts, apply_instruction)
        
        # Токенизация
        batch_dict = self.tokenizer(
            processed_texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        )
        batch_dict = batch_dict.to(self._device)
        
        # Получение эмбеддингов
        with torch.no_grad():
            embeddings = self.model(**batch_dict, return_embeddings=True)
        
        # Конвертация в float lists
        if isinstance(embeddings, torch.Tensor):
            embeddings = embeddings.float().cpu().numpy()
        
        return embeddings.tolist()
    
    async def generate_single(self, text: str, apply_instruction: bool = True) -> List[float]:
        """Генерация эмбеддинга для одного текста.
        
        Args:
            text: Текст для эмбеддинга
            apply_instruction: Добавить инструкцию перед текстом
        """
        embeddings = await self.generate([text], apply_instruction)
        return embeddings[0] if embeddings else []
    
    def get_dimension(self) -> int:
        """Получить размерность векторов."""
        return self.config.dimension
    
    async def shutdown(self):
        """Закрытие провайдера."""
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        if self._device == "cuda":
            torch.cuda.empty_cache()
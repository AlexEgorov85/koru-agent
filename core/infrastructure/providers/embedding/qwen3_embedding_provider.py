"""
Провайдер для Qwen3-Embedding-0.6B с поддержкой локальной загрузки.
"""
import os
from typing import List, Optional
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from core.infrastructure.providers.embedding.base_embedding_provider import IEmbeddingProvider
from core.config.vector_config import EmbeddingConfig


class Qwen3EmbeddingProvider(IEmbeddingProvider):
    """Провайдер для Qwen3-Embedding-0.6B с поддержкой локальной загрузки."""

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.tokenizer = None
        self.model = None
        self._device = None

    def _apply_instruction(self, texts: List[str], use_instruction: bool = True, instruction: Optional[str] = None) -> List[str]:
        """Добавляет инструкцию перед текстами (только для query)."""
        if not use_instruction:
            return texts
        # Приоритет: явная инструкция > конфиг
        instr = instruction or self.config.instruction
        if not instr:
            return texts
        return [f"Instruct: {instr}\nQuery: {text}" for text in texts]

    async def initialize(self):
        """Инициализация модели и токенизатора из локальной папки."""
        model_path = self.config.local_model_path or self.config.model_name
        
        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(f"Локальная модель не найдена: {model_path}")

        self._device = self.config.device if self.config.device else ("cuda" if torch.cuda.is_available() else "cpu")
        
        # Загрузка строго из локальной папки
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, 
            local_files_only=True, 
            trust_remote_code=True
        )
        self.model = AutoModel.from_pretrained(
            model_path, 
            local_files_only=True, 
            trust_remote_code=True
        ).to(self._device)
        self.model.eval()

    async def generate(self, texts: List[str], apply_instruction: bool = True, instruction: Optional[str] = None) -> List[List[float]]:
        """Генерация эмбеддингов для батча текстов."""
        if not self.model:
            await self.initialize()
        if not texts:
            return []

        processed_texts = self._apply_instruction(texts, apply_instruction, instruction)
        # Qwen3 поддерживает до 8192 токенов
        max_length = min(self.config.max_length, 8192)

        batch_dict = self.tokenizer(
            processed_texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        ).to(self._device)

        with torch.no_grad():
            # last_hidden_state: [batch_size, seq_len, hidden_dim]
            outputs = self.model(**batch_dict)
            
            # Mean Pooling с учётом attention_mask
            attention_mask = batch_dict['attention_mask']
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(outputs.last_hidden_state.float().size()).float()
            embeddings = torch.sum(outputs.last_hidden_state * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            
        # L2 Normalization (обязательно для косинусного сходства)
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        
        return embeddings.cpu().tolist()

    async def generate_single(self, text: str, apply_instruction: bool = True, instruction: Optional[str] = None) -> List[float]:
        """Генерация эмбеддинга для одного текста."""
        result = await self.generate([text], apply_instruction, instruction)
        return result[0] if result else []

    def get_dimension(self) -> int:
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

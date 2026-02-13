"""
Базовый класс для LLM провайдеров.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from core.models.llm_types import LLMRequest, LLMResponse


class BaseLLMProvider(ABC):
    """
    Абстрактный базовый класс для всех LLM провайдеров.
    """
    
    @abstractmethod
    async def execute(self, request: LLMRequest) -> LLMResponse:
        """
        Выполнить запрос к LLM.
        
        Args:
            request: Запрос к LLM
            
        Returns:
            Ответ от LLM
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить состояние провайдера.
        
        Returns:
            True если провайдер здоров
        """
        pass
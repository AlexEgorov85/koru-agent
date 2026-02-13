"""
Фабрика для создания LLM провайдеров.
"""
from typing import Dict, Type
from core.infrastructure.providers.llm.base import BaseLLMProvider
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
from core.infrastructure.providers.llm.mock_provider import MockProvider


class LLMProviderFactory:
    """
    Фабрика для создания LLM провайдеров.
    """

    PROVIDER_CLASSES = {
        'llama_cpp': LlamaCppProvider,
        'mock': MockProvider,
    }

    _providers: Dict[str, Type[BaseLLMProvider]] = PROVIDER_CLASSES
    
    @classmethod
    def create_provider(cls, provider_type: str, **kwargs) -> BaseLLMProvider:
        """
        Создать экземпляр провайдера.
        
        Args:
            provider_type: Тип провайдера
            **kwargs: Дополнительные аргументы для инициализации
            
        Returns:
            Экземпляр провайдера
        """
        if provider_type not in cls._providers:
            raise ValueError(f"Неизвестный тип провайдера: {provider_type}")
            
        provider_class = cls._providers[provider_type]
        return provider_class(**kwargs)
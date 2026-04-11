"""
Фабрика для создания LLM провайдеров.
"""
from typing import Dict, Type, Optional
import logging
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
from core.infrastructure.providers.llm.mock_provider import MockProvider
from core.infrastructure.providers.llm.openrouter_provider import OpenRouterProvider
from core.infrastructure.providers.llm.vllm_provider import VLLMProvider


class LLMProviderFactory:
    """
    Фабрика для создания LLM провайдеров.
    """

    PROVIDER_CLASSES = {
        'llama_cpp': LlamaCppProvider,
        'mock': MockProvider,
        'openrouter': OpenRouterProvider,
        'vllm': VLLMProvider,
    }

    @classmethod
    def create_provider(
        cls,
        provider_type: str,
        log_session=None,
        **kwargs
    ) -> BaseLLMProvider:
        """
        Создать экземпляр провайдера.

        Args:
            provider_type: Тип провайдера
            log_session: LoggingSession для привязки логгера к инфраструктурным логам
            **kwargs: Дополнительные аргументы для инициализации

        Returns:
            Экземпляр провайдера
        """
        if provider_type not in cls.PROVIDER_CLASSES:
            raise ValueError(f"Неизвестный тип провайдера: {provider_type}")

        provider_class = cls.PROVIDER_CLASSES[provider_type]
        provider = provider_class(**kwargs)

        # Привязываем логгер к инфраструктурному логгеру если передан log_session
        if log_session is not None and hasattr(log_session, 'infra_logger'):
            provider.log = log_session.infra_logger

        return provider
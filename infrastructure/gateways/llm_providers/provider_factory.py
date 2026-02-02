"""
ProviderFactory - фабрика создания провайдеров из конфигурации.
"""
from typing import Dict, Any, Type
from enum import Enum

from infrastructure.gateways.llm_providers.base_provider import BaseLLMProvider, LLMProviderType
from infrastructure.gateways.llm_providers.llama_cpp_provider import LlamaCppProvider


class ProviderFactory:
    """
    Фабрика для создания LLM-провайдеров из конфигурации.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (фабрика)
    - Ответственность: создание экземпляров провайдеров на основе конфигурации
    - Принципы: соблюдение открытости/закрытости (O в SOLID)
    """
    
    # Регистрация известных провайдеров
    _provider_registry: Dict[LLMProviderType, Type[BaseLLMProvider]] = {
        LLMProviderType.LOCAL_LLAMA: LlamaCppProvider,
    }
    
    @classmethod
    def register_provider(cls, provider_type: LLMProviderType, provider_class: Type[BaseLLMProvider]):
        """
        Регистрация нового типа провайдера.
        
        Args:
            provider_type: Тип провайдера
            provider_class: Класс провайдера
        """
        cls._provider_registry[provider_type] = provider_class
    
    @classmethod
    def create_provider(cls, provider_type: LLMProviderType, model_name: str, config: Dict[str, Any]) -> BaseLLMProvider:
        """
        Создание экземпляра провайдера.
        
        Args:
            provider_type: Тип провайдера
            model_name: Название модели
            config: Конфигурация провайдера
            
        Returns:
            BaseLLMProvider: Экземпляр провайдера
        """
        if provider_type not in cls._provider_registry:
            raise ValueError(f"Неизвестный тип провайдера: {provider_type}")
        
        provider_class = cls._provider_registry[provider_type]
        return provider_class(model_name=model_name, config=config)
    
    @classmethod
    def create_provider_from_config(cls, config: Dict[str, Any]) -> BaseLLMProvider:
        """
        Создание экземпляра провайдера из конфигурации.
        
        Args:
            config: Конфигурация провайдера (включает тип, название модели и параметры)
            
        Returns:
            BaseLLMProvider: Экземпляр провайдера
        """
        provider_type_str = config.get("provider_type")
        model_name = config.get("model_name", "")
        provider_config = config.get("config", {})
        
        if not provider_type_str:
            raise ValueError("Конфигурация должна содержать 'provider_type'")
        
        # Преобразуем строку в enum
        try:
            provider_type = LLMProviderType(provider_type_str)
        except ValueError:
            raise ValueError(f"Неизвестный тип провайдера: {provider_type_str}")
        
        return cls.create_provider(provider_type, model_name, provider_config)
    
    @classmethod
    def get_available_providers(cls) -> list:
        """
        Получение списка доступных типов провайдеров.
        
        Returns:
            list: Список доступных типов провайдеров
        """
        return list(cls._provider_registry.keys())


# Функция для удобного создания провайдера
def create_llm_provider(provider_type: LLMProviderType, model_name: str, config: Dict[str, Any]) -> BaseLLMProvider:
    """
    Функция для создания LLM-провайдера.
    
    Args:
        provider_type: Тип провайдера
        model_name: Название модели
        config: Конфигурация провайдера
        
    Returns:
        BaseLLMProvider: Экземпляр провайдера
    """
    return ProviderFactory.create_provider(provider_type, model_name, config)


def create_llm_provider_from_config(config: Dict[str, Any]) -> BaseLLMProvider:
    """
    Функция для создания LLM-провайдера из конфигурации.
    
    Args:
        config: Конфигурация провайдера
        
    Returns:
        BaseLLMProvider: Экземпляр провайдера
    """
    return ProviderFactory.create_provider_from_config(config)
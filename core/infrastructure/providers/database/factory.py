"""
Фабрика для создания DB провайдеров.
"""
from typing import Dict, Type
from core.infrastructure.providers.database.base_db import BaseDBProvider
from core.infrastructure.providers.database.postgres_provider import PostgresProvider


class DBProviderFactory:
    """
    Фабрика для создания DB провайдеров.
    """

    DB_PROVIDER_CLASSES = {
        'postgres': PostgresProvider,
    }

    _providers: Dict[str, Type[BaseDBProvider]] = DB_PROVIDER_CLASSES
    
    @classmethod
    def create_provider(cls, provider_type: str, **kwargs) -> BaseDBProvider:
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
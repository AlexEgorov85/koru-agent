"""
Фабрика для создания DB провайдеров.
"""
from typing import Dict, Type
from core.infrastructure.providers.database.base import BaseDBProvider
from core.infrastructure.providers.database.postgres_provider import PostgresProvider
from core.infrastructure.providers.database.mock_provider import SQLiteProvider


class DBProviderFactory:
    """
    Фабрика для создания DB провайдеров.
    """

    DB_PROVIDER_CLASSES = {
        'postgres': PostgresProvider,
        'sqlite': SQLiteProvider,
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
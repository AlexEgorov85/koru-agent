"""
Абстракции для системных сервисов (инверсия зависимостей)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Awaitable
from domain.models.system.config import SystemConfig


class ISystemInitializationService(ABC):
    """Интерфейс для сервиса инициализации системы"""

    @abstractmethod
    async def initialize_system(self, config: SystemConfig) -> bool:
        """
        Инициализировать систему с заданной конфигурацией
        
        Args:
            config: Системная конфигурация
            
        Returns:
            True если инициализация прошла успешно, иначе False
        """
        pass

    @abstractmethod
    async def initialize_components(self) -> Dict[str, Any]:
        """
        Инициализировать компоненты системы
        
        Returns:
            Словарь результатов инициализации компонентов
        """
        pass

    @abstractmethod
    async def validate_system_state(self) -> Dict[str, Any]:
        """
        Проверить состояние системы
        
        Returns:
            Словарь с результатами проверки
        """
        pass

    @abstractmethod
    async def shutdown_system(self) -> bool:
        """
        Завершить работу системы
        
        Returns:
            True если завершение прошло успешно, иначе False
        """
        pass
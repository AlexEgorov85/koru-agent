"""
Базовый класс системного контекста для обратной совместимости.

Этот класс служит интерфейсом для различных типов контекстов в системе.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseSystemContext(ABC):
    """
    Базовый класс для всех системных контекстов.
    
    Этот класс обеспечивает единый интерфейс для доступа к ресурсам системы,
    таким как провайдеры, сервисы, навыки и другие компоненты.
    """
    
    @abstractmethod
    def get_resource(self, name: str) -> Optional[Any]:
        """
        Получение ресурса по имени.
        
        Args:
            name: Имя ресурса
            
        Returns:
            Экземпляр ресурса или None если ресурс не найден
        """
        pass
    
    @abstractmethod
    def get_service(self, name: str) -> Optional[Any]:
        """
        Получение сервиса по имени.
        
        Args:
            name: Имя сервиса
            
        Returns:
            Экземпляр сервиса или None если сервис не найден
        """
        pass
    
    @abstractmethod
    def is_fully_initialized(self) -> bool:
        """
        Проверка, полностью ли инициализирована система.
        
        Returns:
            True если система полностью готова к работе
        """
        pass
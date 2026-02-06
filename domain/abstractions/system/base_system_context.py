from abc import ABC, abstractmethod
from typing import Any

from domain.abstractions.event_types import IEventPublisher

class IBaseSystemContext(ABC):
    """
    Интерфейс системного контекста для инверсии зависимостей.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для системного контекста
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    @abstractmethod
    def get_resource(self, resource_name: str) -> Any:
        """Получить ресурс по имени"""
        pass
    
    @abstractmethod
    def get_event_bus(self) -> IEventPublisher:
        """Получить шину событий"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Инициализировать контекст"""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Корректно завершить работу"""
        pass

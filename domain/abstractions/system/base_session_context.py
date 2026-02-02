from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseSessionContext(ABC):
    """
    Интерфейс контекста сессии для инверсии зависимостей.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для контекста сессии
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    @abstractmethod
    def get_session_data(self, key: str) -> Optional[Any]:
        """Получить данные сессии по ключу"""
        pass
    
    @abstractmethod
    def set_session_data(self, key: str, value: Any) -> None:
        """Установить данные сессии по ключу"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Инициализировать контекст сессии"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Очистить ресурсы контекста сессии"""
        pass
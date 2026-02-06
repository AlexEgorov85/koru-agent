from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from domain.models.system.config import SystemConfig


class IConfigManager(ABC):
    """Интерфейс менеджера конфигурации"""
    
    @abstractmethod
    def set_config(self, key: str, value: Any) -> None:
        """Установка параметра конфигурации"""
        pass
    
    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any:
        """Получение параметра конфигурации"""
        pass
    
    @abstractmethod
    def export_config(self) -> Dict[str, Any]:
        """Экспорт конфигурации в словарь"""
        pass
    
    @abstractmethod
    def reset_config(self) -> None:
        """Сброс конфигурации к значениям по умолчанию"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Валидация конфигурации"""
        pass
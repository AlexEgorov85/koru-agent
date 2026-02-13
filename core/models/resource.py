"""
Модели ресурсов для инфраструктурного контекста.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class ResourceType(Enum):
    """
    Типы ресурсов в системе.
    """
    LLM_PROVIDER = "llm_provider"
    DATABASE = "database"
    STORAGE = "storage"
    EVENT_BUS = "event_bus"
    CACHE = "cache"
    OTHER = "other"


@dataclass
class ResourceInfo:
    """
    Информация о зарегистрированном ресурсе.
    
    ATTRIBUTES:
    - name: имя ресурса
    - resource_type: тип ресурса
    - instance: экземпляр ресурса
    - created_at: время создания
    - is_default: является ли ресурс ресурсом по умолчанию
    - metadata: дополнительные метаданные
    """
    name: str
    resource_type: ResourceType
    instance: Any
    created_at: datetime = None
    is_default: bool = False
    metadata: dict = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def get_health_status(self) -> str:
        """
        Получение статуса здоровья ресурса.
        
        RETURNS:
        - статус здоровья ('healthy', 'degraded', 'unhealthy', 'unknown')
        """
        if self.instance is None:
            return 'unhealthy'
        
        # Проверяем наличие метода проверки здоровья
        if hasattr(self.instance, 'health_check'):
            try:
                result = self.instance.health_check()
                return result.get('status', 'unknown')
            except:
                return 'unhealthy'
        
        # По умолчанию считаем, что ресурс здоров, если он существует
        return 'healthy'


class ResourceHealth(Enum):
    """
    Статусы здоровья ресурса.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
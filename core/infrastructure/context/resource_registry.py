"""
Реестр ресурсов инфраструктуры.
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ResourceType(Enum):
    """Типы инфраструктурных ресурсов."""
    LLM_PROVIDER = "llm_provider"
    DATABASE = "database"
    TOOL = "tool"
    SERVICE = "service"


class ResourceHealth(Enum):
    """Состояния здоровья ресурса."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ResourceInfo:
    """Информация о зарегистрированном ресурсе."""
    name: str
    resource_type: ResourceType
    instance: Any
    is_default: bool = False
    health: ResourceHealth = ResourceHealth.UNKNOWN
    metadata: Dict[str, Any] = None


class ResourceRegistry:
    """Реестр инфраструктурных ресурсов."""
    
    def __init__(self):
        self._resources: Dict[str, ResourceInfo] = {}
        
    def register_resource(self, resource_info: ResourceInfo):
        """Регистрация ресурса."""
        self._resources[resource_info.name] = resource_info
        
    def get_resource(self, name: str) -> Optional[ResourceInfo]:
        """Получение информации о ресурсе."""
        return self._resources.get(name)
        
    def get_resources_by_type(self, resource_type: ResourceType) -> Dict[str, ResourceInfo]:
        """Получение ресурсов по типу."""
        return {name: info for name, info in self._resources.items() 
                if info.resource_type == resource_type}
                
    def get_default_resource(self, resource_type: ResourceType) -> Optional[ResourceInfo]:
        """Получение ресурса по умолчанию для типа."""
        for info in self._resources.values():
            if info.resource_type == resource_type and info.is_default:
                return info
        return None

    def get_all_names(self) -> list:
        """Получение всех имен ресурсов."""
        return list(self._resources.keys())

    def get_all_resources(self) -> list:
        """Получение всех ресурсов."""
        return list(self._resources.values())
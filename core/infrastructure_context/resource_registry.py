"""
Реестр ресурсов инфраструктуры.
"""
from typing import Dict, Optional, Any

from core.models.data.resource import ResourceInfo
from core.models.enums.common_enums import ResourceType


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
        
    def get_resources_by_type(self, resource_type: ResourceType) -> list:
        """Получение ресурсов по типу."""
        return [info for info in self._resources.values()
                if info.resource_type == resource_type]
                
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
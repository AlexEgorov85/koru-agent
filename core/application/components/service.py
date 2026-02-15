"""
Базовый класс для сервисов (Services) с кэшированием.
"""
from abc import abstractmethod
from typing import Dict, Any
from core.application.components.base import BaseComponent
from core.models.capability import Capability


class BaseService(BaseComponent):
    """
    Базовый класс для сервисов (Services).
    Сервисы могут иметь изолированные кэши и долгоживущее состояние.
    """
    
    def __init__(self, name: str, application_context, component_config, executor):
        super().__init__(name, application_context, component_config, executor)
        
    @abstractmethod
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any):
        """
        Абстрактный метод выполнения сервиса.
        """
        pass
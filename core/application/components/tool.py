"""
Базовый класс для инструментов (Tools) - stateless компоненты.
"""
from abc import abstractmethod
from typing import Dict, Any
from core.application.components.base import BaseComponent
from core.models.capability import Capability


class BaseTool(BaseComponent):
    """
    Базовый класс для инструментов (Tools).
    Инструменты являются stateless и используют провайдеры напрямую.
    """
    
    def __init__(self, name: str, application_context, component_config):
        super().__init__(name, application_context, component_config)
        
    @abstractmethod
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any):
        """
        Абстрактный метод выполнения инструмента.
        """
        pass
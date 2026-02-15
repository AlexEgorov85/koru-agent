"""
Базовый класс для навыков (Skills) с кэшированием промптов и контрактов.
"""
from abc import abstractmethod
from typing import Dict, Any
from core.application.components.base import BaseComponent
from core.application.context.application_context import ApplicationContext
from core.models.capability import Capability


class BaseSkill(BaseComponent):
    """
    Базовый класс для навыков (Skills).
    Навыки могут иметь кэшированные промпты и контракты, а также состояние.
    """
    
    def __init__(self, name: str, application_context: ApplicationContext, component_config):
        super().__init__(name, application_context, component_config)
        
    @abstractmethod
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any):
        """
        Абстрактный метод выполнения навыка.
        """
        pass
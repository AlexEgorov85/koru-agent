"""
Новый базовый класс для инструментов (Tools) с поддержкой изолированных кэшей.

АРХИТЕКТУРА:
- Инструменты НЕ хранят состояние между вызовами
- Все зависимости запрашиваются из инфраструктуры при выполнении
- Использует изолированные кэши, предзагруженные через ComponentConfig
"""
from abc import abstractmethod
from typing import Dict, Any, Optional
from core.components.base_component import BaseComponent
from core.models.capability import Capability
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig


class BaseTool(BaseComponent):
    """
    Базовый класс для инструментов (Tools).
    
    Особенности:
    - Инструменты НЕ хранят состояние между вызовами
    - Все зависимости запрашиваются из инфраструктуры при выполнении
    - Использует изолированные кэши, предзагруженные через ComponentConfig
    """
    
    def __init__(
        self, 
        name: str, 
        application_context: ApplicationContext, 
        component_config: Optional[ComponentConfig] = None,
        **kwargs
    ):
        # Важно: НЕ сохраняем зависимости как атрибуты!
        super().__init__(name, application_context, component_config)
        self.config = kwargs  # Только параметры конфигурации

    @abstractmethod
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any):
        """
        Абстрактный метод выполнения инструмента.
        
        При выполнении запрашиваем зависимости из инфраструктуры:
        """
        # ПРИМЕР для SQLTool:
        # db_provider = self.application_context.infrastructure_context.get_provider("default_db")
        # return await db_provider.execute_query(...)
        pass
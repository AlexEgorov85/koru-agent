from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.system_context.base_system_contex import BaseSystemContext
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent

class ToolInput(ABC):
    """Абстрактный класс для входных данных инструмента."""
    pass

class ToolOutput(ABC):
    """Абстрактный класс для выходных данных инструмента."""
    pass

class BaseTool(BaseComponent):
    """Базовый класс для инструментов с инверсией зависимостей."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Описание назначения инструмента."""
        pass

    def __init__(self, name: str, system_context: BaseSystemContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        # Вызов конструктора родительского класса
        super().__init__(name, system_context, component_config)
        self.config = kwargs

    @abstractmethod
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Выполнение инструмента с четким контрактом входа/выхода."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы."""
        pass
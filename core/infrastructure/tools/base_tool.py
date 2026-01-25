from abc import ABC, abstractmethod
from typing import Any

from core.system_context.base_system_contex import BaseSystemContext

class ToolInput(ABC):
    """Абстрактный класс для входных данных инструмента."""
    pass

class ToolOutput(ABC):
    """Абстрактный класс для выходных данных инструмента."""
    pass

class BaseTool(ABC):
    """Базовый класс для инструментов с инверсией зависимостей."""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Описание назначения инструмента."""
        pass

    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        self.name = name
        self.system_context = system_context
        self.config = kwargs
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        pass
        
    @abstractmethod
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Выполнение инструмента с четким контрактом входа/выхода."""
        pass
        
    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы."""
        pass
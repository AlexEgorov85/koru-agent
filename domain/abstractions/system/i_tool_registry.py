from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from domain.abstractions.tools.base_tool import BaseTool


class IToolRegistry(ABC):
    """Интерфейс реестра инструментов"""
    
    @abstractmethod
    def register_tool(self, tool: BaseTool) -> None:
        """Регистрация инструмента"""
        pass
    
    @abstractmethod
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Получение инструмента по имени"""
        pass
    
    @abstractmethod
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Получение всех инструментов"""
        pass
    
    @abstractmethod
    def filter_tools_by_tag(self, tag: str) -> Dict[str, BaseTool]:
        """Фильтрация инструментов по тегу"""
        pass
    
    @abstractmethod
    def update_tool(self, name: str, tool: BaseTool) -> None:
        """Обновление инструмента"""
        pass
    
    @abstractmethod
    def remove_tool(self, name: str) -> bool:
        """Удаление инструмента по имени"""
        pass
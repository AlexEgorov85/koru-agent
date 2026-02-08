from typing import Dict, List, Optional
from domain.abstractions.system.i_tool_registry import IToolRegistry
from domain.abstractions.tools.base_tool import BaseTool
from domain.models.system.tool_metadata import ToolMetadata


class ToolRegistry(IToolRegistry):
    """Реализация реестра инструментов"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register_tool(self, tool: BaseTool) -> None:
        """Регистрация инструмента с уникальным именем"""
        if tool.name in self._tools:
            raise ValueError(f"Инструмент с именем '{tool.name}' уже зарегистрирован")
        
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Получение инструмента по имени"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Получение всех инструментов"""
        return self._tools.copy()
    
    def filter_tools_by_tag(self, tag: str) -> Dict[str, BaseTool]:
        """Фильтрация инструментов по тегу"""
        # В этой простой реализации будем использовать метаданные инструмента
        # или проверять наличие атрибута tags в инструменте
        filtered_tools = {}
        
        for name, tool in self._tools.items():
            # Проверяем, есть ли у инструмента атрибут tags и содержит ли он указанный тег
            if hasattr(tool, 'tags') and tag in tool.tags:
                filtered_tools[name] = tool
            # Если инструмент имеет метаданные, проверяем их тоже
            elif hasattr(tool, '__metadata__') and hasattr(tool.__metadata__, 'tags') and tag in tool.__metadata__.tags:
                filtered_tools[name] = tool
        
        return filtered_tools
    
    def update_tool(self, name: str, tool: BaseTool) -> None:
        """Обновление инструмента"""
        if name not in self._tools:
            raise KeyError(f"Инструмент с именем '{name}' не найден")
        
        if tool.name != name:
            raise ValueError("Имя инструмента не соответствует имени, под которым он был зарегистрирован")
        
        self._tools[name] = tool
    
    def remove_tool(self, name: str) -> bool:
        """Удаление инструмента по имени"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
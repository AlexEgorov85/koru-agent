"""
Конфигурация тестов для системного контекста.
"""
from unittest.mock import AsyncMock
from typing import Dict, Any


class MockTool:
    """Мок-инструмент для тестирования"""
    
    def __init__(self, name: str = "mock_tool", description: str = "Mock tool for testing"):
        self.name = name
        self._description = description
        self._initialized = False
        self._shutdown = False
    
    @property
    def description(self) -> str:
        return self._description
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Возвращаем простой результат, так как ToolOutput не определен в текущем контексте
        return {"result": "mock_result"}
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def shutdown(self) -> None:
        self._shutdown = True


class MockSkill:
    """Мок-навык для тестирования"""
    
    def __init__(self, name: str, description: str = "Mock skill for testing"):
        self.name = name
        self._description = description
        self._initialized = False
        self._shutdown = False
    
    async def execute(self, capability, parameters: Dict[str, Any], context):
        return {"status": "success", "result": "mock_skill_result"}
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def shutdown(self) -> None:
        self._shutdown = True
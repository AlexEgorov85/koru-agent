"""
Снапшот-тесты, фиксирующие ТЕКУЩЕЕ поведение SystemContext.
Эти тесты НЕЛЬЗЯ менять после создания — они фиксируют контракт.
"""
import pytest
from typing import Any, Dict
from application.context.system.system_context import SystemContext
from domain.abstractions.tools.base_tool import BaseTool, ToolInput, ToolOutput
from domain.abstractions.skills.base_skill import BaseSkill
from pydantic import BaseModel


class MockToolInput(ToolInput):
    """Мок-входные данные для инструмента"""
    pass


class MockToolOutput(ToolOutput):
    """Мок-выходные данные для инструмента"""
    result: str


class MockTool(BaseTool):
    """Мок-инструмент для тестирования"""
    
    def __init__(self, name: str):
        self.name = name
    
    @property
    def description(self) -> str:
        return "Mock tool for testing"
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "mock_result"}


class MockSkill(BaseSkill):
    """Мок-навык для тестирования"""
    
    def __init__(self, name: str, required_tools: list = None):
        # Заглушка для системного контекста
        super().__init__()
        self.name = name
        self._required_tools = required_tools or []
    
    def get_capabilities(self) -> list:
        from domain.models.system.capability import Capability
        return [
            Capability(
                name=f"{self.name}_capability",
                description="Mock capability for testing",
                parameters_schema={},
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability, parameters: dict, context):
        return {"status": "success", "result": "mock_skill_result"}


def test_get_tool_returns_none_when_tool_does_not_exist():
    """Тестируем, что возвращает get_tool() при отсутствии инструмента"""
    system = SystemContext()
    result = system.get_tool("nonexistent_tool")
    
    assert result is None


def test_register_tool_raises_exception_on_duplicate():
    """Тестируем, что делает register_tool() при дубликате"""
    system = SystemContext()
    tool1 = MockTool(name="duplicate_tool")
    
    # Регистрируем первый инструмент
    system.register_tool(tool1)
    
    # Пытаемся зарегистрировать дубликат
    tool2 = MockTool(name="duplicate_tool")
    
    with pytest.raises(ValueError, match="уже зарегистрирован"):
        system.register_tool(tool2)


def test_get_skill_returns_none_when_skill_does_not_exist():
    """Тестируем, как ведёт себя get_skill() при отсутствии навыка"""
    system = SystemContext()
    result = system.get_skill("nonexistent_skill")
    
    assert result is None


def test_register_skill_raises_exception_on_duplicate():
    """Тестируем, что делает register_skill() при дубликате"""
    system = SystemContext()
    skill1 = MockSkill(name="duplicate_skill")
    
    # Регистрируем первый навык
    system.register_skill(skill1)
    
    # Пытаемся зарегистрировать дубликат
    skill2 = MockSkill(name="duplicate_skill")
    
    with pytest.raises(ValueError, match="уже зарегистрирован"):
        system.register_skill(skill2)


def test_system_context_has_only_registry_methods():
    """Тестируем, что SystemContext содержит только методы доступа к реестрам"""
    system = SystemContext()
    
    # Проверяем наличие методов реестров
    assert hasattr(system, 'register_tool')
    assert hasattr(system, 'get_tool')
    assert hasattr(system, 'get_all_tools')
    assert hasattr(system, 'filter_tools_by_tag')
    assert hasattr(system, 'update_tool')
    assert hasattr(system, 'remove_tool')
    
    assert hasattr(system, 'register_skill')
    assert hasattr(system, 'get_skill')
    assert hasattr(system, 'get_all_skills')
    assert hasattr(system, 'filter_skills_by_category')
    assert hasattr(system, 'get_skill_dependencies')
    assert hasattr(system, 'is_skill_ready')
    assert hasattr(system, 'remove_skill')
    
    assert hasattr(system, 'set_config')
    assert hasattr(system, 'get_config')
    assert hasattr(system, 'export_config')
    assert hasattr(system, 'reset_config')
    assert hasattr(system, 'validate')
    
    # Проверяем отсутствие методов жизненного цикла
    assert not hasattr(system, 'initialize_components')
    assert not hasattr(system, 'shutdown_components')
    assert not hasattr(system, 'start_system')
    assert not hasattr(system, 'stop_system')
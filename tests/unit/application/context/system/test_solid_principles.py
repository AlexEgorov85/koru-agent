"""
Тесты для проверки соответствия SOLID принципам и архитектурным ограничениям
"""
import pytest
from application.context.system.system_context import SystemContext
from application.context.system.tool_registry import ToolRegistry
from application.context.system.skill_registry import SkillRegistry
from application.context.system.config_manager import ConfigManager
from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.skills.base_skill import BaseSkill
from domain.abstractions.system.i_tool_registry import IToolRegistry
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.system.i_config_manager import IConfigManager
from typing import Dict, Any


class MockTool(BaseTool):
    """Мок-инструмент для тестирования"""
    
    def __init__(self, name: str = "mock_tool", description: str = "Mock tool for testing"):
        self.name = name
        self._description = description
        self.tags = []
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "mock_result"}


class MockSkill(BaseSkill):
    """Мок-навык для тестирования"""
    
    def __init__(self, name: str, description: str = "Mock skill for testing", 
                 required_tools: list = None):
        self.name = name
        self._description = description
        self.required_tools = required_tools or []
    
    async def execute(self, capability, parameters: Dict[str, Any], context):
        return {"status": "success", "result": "mock_skill_result"}


def test_tool_registry_implements_interface():
    """Проверка, что ToolRegistry реализует IToolRegistry"""
    registry = ToolRegistry()
    assert isinstance(registry, IToolRegistry)


def test_skill_registry_implements_interface():
    """Проверка, что SkillRegistry реализует ISkillRegistry"""
    registry = SkillRegistry()
    assert isinstance(registry, ISkillRegistry)


def test_config_manager_implements_interface():
    """Проверка, что ConfigManager реализует IConfigManager"""
    manager = ConfigManager()
    assert isinstance(manager, IConfigManager)


def test_system_context_composition():
    """Проверка композиции SystemContext из компонентов"""
    system = SystemContext()
    
    assert hasattr(system, 'tool_registry')
    assert hasattr(system, 'skill_registry')
    assert hasattr(system, 'config_manager')
    
    assert isinstance(system.tool_registry, IToolRegistry)
    assert isinstance(system.skill_registry, ISkillRegistry)
    assert isinstance(system.config_manager, IConfigManager)


def test_tool_registry_single_responsibility():
    """Проверка принципа единственной ответственности для ToolRegistry"""
    registry = ToolRegistry()
    tool = MockTool(name="test_tool")
    
    # Регистрация инструмента
    registry.register_tool(tool)
    
    # Получение инструмента
    retrieved_tool = registry.get_tool("test_tool")
    assert retrieved_tool is not None
    
    # Проверка, что ToolRegistry не занимается конфигурацией или навыками
    assert not hasattr(registry, 'set_config')
    assert not hasattr(registry, 'register_skill')


def test_skill_registry_single_responsibility():
    """Проверка принципа единственной ответственности для SkillRegistry"""
    registry = SkillRegistry()
    skill = MockSkill(name="test_skill")
    
    # Регистрация навыка
    registry.register_skill(skill)
    
    # Получение навыка
    retrieved_skill = registry.get_skill("test_skill")
    assert retrieved_skill is not None
    
    # Проверка, что SkillRegistry не занимается инструментами или конфигурацией
    assert not hasattr(registry, 'set_config')
    assert not hasattr(registry, 'register_tool')


def test_config_manager_single_responsibility():
    """Проверка принципа единственной ответственности для ConfigManager"""
    manager = ConfigManager()
    
    # Установка конфигурации
    manager.set_config("test_param", "test_value")
    
    # Получение конфигурации
    value = manager.get_config("test_param")
    assert value == "test_value"
    
    # Проверка, что ConfigManager не занимается инструментами или навыками
    assert not hasattr(manager, 'register_tool')
    assert not hasattr(manager, 'register_skill')


def test_system_context_immutable_after_validation():
    """Проверка иммутабельности конфигурации после валидации"""
    system = SystemContext()
    
    # Установка конфигурации до валидации
    system.set_config("test_param", "test_value")
    assert system.get_config("test_param") == "test_value"
    
    # Валидация системы
    system.validate()
    
    # Попытка изменить конфигурацию после валидации должна вызвать ошибку
    with pytest.raises(RuntimeError, match="Конфигурация была валидирована и теперь неизменяема"):
        system.set_config("another_param", "another_value")


def test_system_context_component_isolation():
    """Проверка изоляции компонентов в SystemContext"""
    system = SystemContext()
    
    # Регистрируем инструмент
    tool = MockTool(name="isolated_tool")
    system.register_tool(tool)
    
    # Регистрируем навык
    skill = MockSkill(name="isolated_skill")
    system.register_skill(skill)
    
    # Проверяем, что компоненты изолированы
    assert system.get_tool("isolated_tool") is not None
    assert system.get_skill("isolated_skill") is not None
    
    # Проверяем, что компоненты не пересекаются
    assert system.get_tool("isolated_skill") is None
    assert system.get_skill("isolated_tool") is None


def test_lazy_initialization_not_implemented_yet():
    """Тест для проверки ленивой инициализации (в текущей реализации все компоненты инициализируются сразу)"""
    # В текущей реализации компоненты инициализируются сразу при создании SystemContext
    system = SystemContext()
    
    # Проверяем, что компоненты созданы
    assert system.tool_registry is not None
    assert system.skill_registry is not None
    assert system.config_manager is not None
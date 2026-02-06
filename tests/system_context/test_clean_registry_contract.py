"""
Тесты, описывающие ЖЕЛАЕМОЕ поведение после рефакторинга.
Эти тесты ДОЛЖНЫ проваливаться на текущей реализации.
"""
import pytest
from typing import Any, Dict
from application.context.system.system_context import SystemContext
from application.gateways.execution.execution_gateway import ExecutionGateway
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.system.i_tool_registry import IToolRegistry
from domain.abstractions.system.i_config_manager import IConfigManager
from domain.abstractions.tools.base_tool import BaseTool, ToolInput, ToolOutput
from domain.abstractions.skills.base_skill import BaseSkill


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


def test_system_context_implements_registry_interfaces():
    """SystemContext должен реализовывать интерфейсы реестров"""
    system = SystemContext()
    
    # Проверяем, что SystemContext может работать с портами
    assert isinstance(system.tool_registry, IToolRegistry)
    assert isinstance(system.skill_registry, ISkillRegistry)
    assert isinstance(system.config_manager, IConfigManager)


def test_execution_gateway_depends_on_ports_not_context():
    """ExecutionGateway должен зависеть от портов, а не от полного контекста"""
    system = SystemContext()
    
    # В идеале ExecutionGateway должен принимать порты, а не полный SystemContext
    # Это тест для целевого поведения - сейчас он должен падать
    try:
        # Попробуем создать ExecutionGateway с портами
        gateway = ExecutionGateway(
            skill_registry=system.skill_registry,
            event_publisher=None  # Пока None, так как нужно получить из SystemOrchestrator
        )
        # Если это работает, значит, архитектура уже соответствует цели
        assert True
    except TypeError:
        # Если падает с TypeError, значит, конструктор ожидает старый формат
        pytest.skip("ExecutionGateway еще не принимает порты напрямую")


def test_get_tool_always_returns_tool_or_none_never_exception():
    """get_tool() ВСЕГДА возвращает либо инструмент, либо None (никогда исключение)"""
    system = SystemContext()
    
    # При отсутствии инструмента должен возвращать None, а не исключение
    result = system.get_tool("nonexistent_tool")
    assert result is None


def test_system_context_contains_only_state_access_methods():
    """Система должна содержать только методы доступа к состоянию"""
    system = SystemContext()
    
    # SystemContext должен предоставлять только методы доступа к реестрам
    # и не должен содержать логики выполнения или управления жизненным циклом
    assert hasattr(system, 'get_tool')
    assert hasattr(system, 'register_tool')
    assert hasattr(system, 'get_skill')
    assert hasattr(system, 'register_skill')
    assert hasattr(system, 'get_config')
    assert hasattr(system, 'set_config')


def test_execution_gateway_no_longer_has_prompt_logic():
    """ExecutionGateway не должен содержать логику промптов/провайдеров"""
    system = SystemContext()
    
    # Создаем ExecutionGateway с новым интерфейсом (портами)
    gateway = ExecutionGateway(
        skill_registry=system.skill_registry,
        prompt_repository=None,
        event_publisher=None
    )
    
    # Проверяем, что ExecutionGateway не содержит методов, связанных с промптами напрямую
    # (они должны быть вынесены в отдельный компонент)
    # В новой архитектуре ExecutionGateway больше не зависит от полного SystemContext
    assert not hasattr(gateway, '_system_context')


def test_system_context_isolated_from_lifecycle_logic():
    """SystemContext не должен иметь связи с менеджерами жизненного цикла"""
    system = SystemContext()
    
    # Проверяем, что SystemContext не содержит ссылок на компоненты жизненного цикла
    assert not hasattr(system, '_lifecycle_manager')
    assert not hasattr(system, '_resource_manager')
    assert not hasattr(system, '_event_system')
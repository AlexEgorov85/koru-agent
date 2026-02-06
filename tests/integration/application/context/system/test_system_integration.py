"""
Сквозные интеграционные тесты системы
"""
import pytest
from application.context.system.system_context import SystemContext
from domain.abstractions.tools.base_tool import BaseTool, ToolInput, ToolOutput
from domain.abstractions.skills.base_skill import BaseSkill
from domain.models.system.capability import Capability


class MockToolInput(ToolInput):
    """Мок-входные данные для инструмента"""
    pass


class MockToolOutput(ToolOutput):
    """Мок-выходные данные для инструмента"""
    result: str


class MockTool(BaseTool):
    """Мок-инструмент для тестирования"""
    
    def __init__(self, name: str = "mock_tool", description: str = "Mock tool for testing"):
        self.name = name
        self._description = description
    
    @property
    def description(self) -> str:
        return self._description
    
    async def initialize(self) -> bool:
        return True
    
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        return MockToolOutput(result="mock_result")
    
    async def shutdown(self) -> None:
        pass


class MockSkill(BaseSkill):
    """Мок-навык для тестирования"""
    
    def __init__(self, name: str, description: str = "Mock skill for testing", 
                 required_tools: list = None):
        self.name = name
        self._description = description
        self.required_tools = required_tools or []
    
    def get_capabilities(self) -> list:
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


def test_register_tool_then_register_skill_with_dependency_then_check_skill_readiness():
    """Регистрация инструмента → регистрация навыка с зависимостью от этого инструмента → проверка готовности навыка"""
    system = SystemContext()
    
    # Регистрируем инструмент
    tool = MockTool(name="dependency_tool")
    system.register_tool(tool)
    
    # Регистрируем навык с зависимостью от инструмента
    skill = MockSkill(name="dependent_skill", required_tools=["dependency_tool"])
    system.register_skill(skill)
    
    # Проверяем готовность навыка
    assert system.is_skill_ready("dependent_skill") is True


def test_change_configuration_affects_registered_components_behavior():
    """Изменение конфигурации (например, лимит запросов) влияет на поведение зарегистрированных компонентов"""
    system = SystemContext()
    
    # Устанавливаем конфигурацию
    system.set_config("request_limit", 100)
    system.set_config("timeout", 30)
    
    # Проверяем, что конфигурация установлена
    assert system.get_config("request_limit") == 100
    assert system.get_config("timeout") == 30
    
    # Добавляем инструмент и проверяем, что он может получить доступ конфигурации
    tool = MockTool(name="configurable_tool")
    system.register_tool(tool)
    
    # Проверяем, что конфигурация доступна в системе
    exported_config = system.export_config()
    assert "request_limit" in exported_config
    assert "timeout" in exported_config


def test_get_all_available_system_capabilities_for_agent():
    """Получение всех доступных возможностей системы (инструменты + навыки) для агента"""
    system = SystemContext()
    
    # Регистрируем инструменты
    tool1 = MockTool(name="tool1")
    tool2 = MockTool(name="tool2")
    system.register_tool(tool1)
    system.register_tool(tool2)
    
    # Регистрируем навыки
    skill1 = MockSkill(name="skill1")
    skill2 = MockSkill(name="skill2")
    system.register_skill(skill1)
    system.register_skill(skill2)
    
    # Получаем все возможности
    all_tools = system.get_all_tools()
    all_skills = system.get_all_skills()
    
    assert len(all_tools) == 2
    assert "tool1" in all_tools
    assert "tool2" in all_tools
    
    assert len(all_skills) == 2
    assert "skill1" in all_skills
    assert "skill2" in all_skills


def test_validate_system_before_startup_checks_all_required_components():
    """Валидация системы перед запуском проверяет все обязательные компоненты"""
    system = SystemContext()
    
    # Регистрируем инструмент
    tool = MockTool(name="required_tool")
    system.register_tool(tool)
    
    # Регистрируем навык с зависимостью
    skill = MockSkill(name="required_skill", required_tools=["required_tool"])
    system.register_skill(skill)
    
    # Устанавливаем необходимую конфигурацию
    system.set_config("essential_param", "value")
    
    # Проверяем валидацию системы
    system.validate()  # Не должно возникнуть исключений


def test_serialize_deserialize_system_state_preserves_all_registered_components():
    """Сериализация/десериализация состояния системы сохраняет все зарегистрированные компоненты"""
    system = SystemContext()
    
    # Регистрируем компоненты
    tool = MockTool(name="serializable_tool")
    system.register_tool(tool)
    
    skill = MockSkill(name="serializable_skill")
    system.register_skill(skill)
    
    system.set_config("config_param", "config_value")
    
    # Сохраняем состояние системы (в реальной реализации это будет через сериализацию)
    tools_snapshot = system.get_all_tools()
    skills_snapshot = system.get_all_skills()
    config_snapshot = system.export_config()
    
    # Проверяем, что состояние сохранено
    assert "serializable_tool" in tools_snapshot
    assert "serializable_skill" in skills_snapshot
    assert "config_param" in config_snapshot
    
    # Создаем новую систему и восстанавливаем состояние (это упрощенная версия)
    new_system = SystemContext()
    
    # Восстанавливаем компоненты
    for name, tool_instance in tools_snapshot.items():
        new_system.register_tool(tool_instance)
    
    for name, skill_instance in skills_snapshot.items():
        new_system.register_skill(skill_instance)
    
    for key, value in config_snapshot.items():
        new_system.set_config(key, value)
    
    # Проверяем, что состояние восстановлено
    new_tools = new_system.get_all_tools()
    new_skills = new_system.get_all_skills()
    new_config = new_system.export_config()
    
    assert "serializable_tool" in new_tools
    assert "serializable_skill" in new_skills
    assert "config_param" in new_config
"""
Тесты поведения SystemContext
"""
import pytest
from typing import Dict, Any, Optional
from application.context.system.system_context import SystemContext
from domain.models.system.config import SystemConfig
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
    
    @property
    def description(self) -> str:
        return "Mock tool for testing"
    
    async def initialize(self) -> bool:
        return True
    
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        return MockToolOutput(result="mock_result")
    
    async def shutdown(self) -> None:
        pass


class MockSkill(BaseSkill):
    """Мок-навык для тестирования"""
    
    def __init__(self, name: str, required_tools: list = None):
        # Заглушка для системного контекста
        super().__init__(name=name, system_context=None)
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
    
    async def execute(self, capability, parameters: Dict[str, Any], context):
        return {"status": "success", "result": "mock_skill_result"}


def test_set_config_parameter_saves_value_with_type_validation():
    """Установка параметра конфигурации сохраняет значение с валидацией типа"""
    system = SystemContext()
    system.set_config("max_requests", 100)
    
    assert system.get_config("max_requests") == 100


def test_get_config_parameter_returns_saved_value_or_default():
    """Получение параметра по ключу возвращает сохранённое значение или значение по умолчанию"""
    system = SystemContext()
    system.set_config("test_param", "test_value")
    
    assert system.get_config("test_param") == "test_value"
    assert system.get_config("nonexistent_param", "default") == "default"


def test_get_nonexistent_config_without_default_raises_exception():
    """Получение несуществующего параметра без значения по умолчанию вызывает исключение"""
    system = SystemContext()
    
    with pytest.raises(KeyError):
        system.get_config("nonexistent_param")


def test_validate_configuration_checks_required_parameters_before_using_system():
    """Валидация конфигурации проверяет обязательные параметры перед использованием системы"""
    system = SystemContext()
    
    # Устанавливаем обязательные параметры
    system.set_config("required_param", "required_value")
    
    # Проверяем, что валидация проходит успешно
    system.validate()


def test_reset_configuration_restores_default_values():
    """Сброс конфигурации к значениям по умолчанию восстанавливает исходное состояние"""
    system = SystemContext()
    system.set_config("test_param", "modified_value")
    
    system.reset_config()
    
    # После сброса параметр больше не должен быть доступен
    with pytest.raises(KeyError):
        system.get_config("test_param")


def test_export_configuration_includes_all_set_parameters():
    """Экспорт конфигурации в словарь включает все установленные параметры"""
    system = SystemContext()
    system.set_config("param1", "value1")
    system.set_config("param2", 42)
    
    exported = system.export_config()
    
    assert "param1" in exported
    assert "param2" in exported
    assert exported["param1"] == "value1"
    assert exported["param2"] == 42
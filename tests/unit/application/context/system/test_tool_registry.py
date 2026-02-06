"""
Тесты реестра инструментов
"""
from typing import Any, Dict
import pytest
from application.context.system.system_context import SystemContext
from domain.abstractions.tools.base_tool import BaseTool, ToolInput, ToolOutput


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
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "mock_result"}


class MockToolWithTag(MockTool):
    """Мок-инструмент с тегами для тестирования фильтрации"""
    
    def __init__(self, name: str = "mock_tool_with_tag", description: str = "Mock tool with tags", tags: list = None):
        super().__init__(name=name, description=description)
        self.tags = tags or []


def test_register_unique_named_tool_succeeds():
    """Регистрация инструмента с уникальным именем проходит успешно"""
    system = SystemContext()
    tool = MockTool(name="unique_tool")
    
    system.register_tool(tool)
    
    retrieved_tool = system.get_tool("unique_tool")
    assert retrieved_tool is not None
    assert retrieved_tool.name == "unique_tool"


def test_attempt_to_register_duplicate_named_tool_raises_exception():
    """Попытка регистрации инструмента с дублирующим именем вызывает исключение"""
    system = SystemContext()
    tool1 = MockTool(name="duplicate_tool")
    tool2 = MockTool(name="duplicate_tool")
    
    system.register_tool(tool1)
    
    with pytest.raises(ValueError):
        system.register_tool(tool2)


def test_get_tool_by_name_returns_registered_instance():
    """Получение инструмента по имени возвращает зарегистрированный экземпляр"""
    system = SystemContext()
    tool = MockTool(name="test_tool", description="A test tool")
    
    system.register_tool(tool)
    
    retrieved_tool = system.get_tool("test_tool")
    assert retrieved_tool is not None
    assert retrieved_tool is tool  # Проверяем, что это тот же экземпляр
    assert retrieved_tool.description == "A test tool"


def test_get_nonexistent_tool_returns_none():
    """Получение несуществующего инструмента возвращает None (не исключение)"""
    system = SystemContext()
    
    retrieved_tool = system.get_tool("nonexistent_tool")
    assert retrieved_tool is None


def test_get_all_tools_returns_dictionary_of_name_to_tool():
    """Получение всех инструментов возвращает словарь {имя: инструмент}"""
    system = SystemContext()
    tool1 = MockTool(name="tool1")
    tool2 = MockTool(name="tool2")
    
    system.register_tool(tool1)
    system.register_tool(tool2)
    
    all_tools = system.get_all_tools()
    assert len(all_tools) == 2
    assert "tool1" in all_tools
    assert "tool2" in all_tools
    assert all_tools["tool1"] is tool1
    assert all_tools["tool2"] is tool2


def test_filter_tools_by_tags_returns_matching_tools_only():
    """Фильтрация инструментов по тегам возвращает только подходящие инструменты"""
    system = SystemContext()
    tool_with_tag = MockToolWithTag(name="tool_with_tag", tags=["database"])
    tool_without_tag = MockTool(name="tool_without_tag")
    tool_with_different_tag = MockToolWithTag(name="tool_with_different_tag", tags=["api"])
    
    system.register_tool(tool_with_tag)
    system.register_tool(tool_without_tag)
    system.register_tool(tool_with_different_tag)
    
    filtered_tools = system.filter_tools_by_tag("database")
    assert len(filtered_tools) == 1
    assert "tool_with_tag" in filtered_tools


def test_update_tool_metadata_preserves_changes():
    """Обновление метаданных инструмента сохраняет изменения"""
    system = SystemContext()
    tool = MockTool(name="update_test_tool")
    
    system.register_tool(tool)
    
    # В новой архитектуре мы можем обновлять метаданные инструмента
    # через отдельный метод или перерегистрацию с новыми метаданными
    updated_tool = MockTool(name="update_test_tool", description="Updated description")
    system.update_tool("update_test_tool", updated_tool)
    
    retrieved_tool = system.get_tool("update_test_tool")
    assert retrieved_tool.description == "Updated description"


def test_remove_tool_by_name_removes_it_from_registry():
    """Удаление инструмента по имени удаляет его из реестра"""
    system = SystemContext()
    tool = MockTool(name="removable_tool")
    
    system.register_tool(tool)
    assert system.get_tool("removable_tool") is not None
    
    system.remove_tool("removable_tool")
    assert system.get_tool("removable_tool") is None
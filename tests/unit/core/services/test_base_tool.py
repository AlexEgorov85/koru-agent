"""
Тесты для базового класса инструмента (BaseTool).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.infrastructure.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.system_context.base_system_contex import BaseSystemContext


class ConcreteToolInput(ToolInput):
    """Конкретная реализация ToolInput для тестов."""
    pass


class ConcreteToolOutput(ToolOutput):
    """Конкретная реализация ToolOutput для тестов."""
    pass


class TestTool(BaseTool):
    """Тестовая реализация BaseTool."""
    
    @property
    def description(self) -> str:
        return "Тестовый инструмент для проверки базового класса"
    
    async def initialize(self) -> bool:
        return True
    
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        return ConcreteToolOutput()
    
    async def shutdown(self) -> None:
        pass


class TestBaseTool:
    """Тесты для BaseTool."""
    
    def test_initialization(self):
        """Тест инициализации инструмента."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        tool = TestTool("test_tool", mock_system_context, config_param="test_value")
        
        assert tool.name == "test_tool"
        assert tool.system_context == mock_system_context
        assert tool.config == {"config_param": "test_value"}
    
    def test_description_property(self):
        """Тест свойства description."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        tool = TestTool("test_tool", mock_system_context)
        
        assert tool.description == "Тестовый инструмент для проверки базового класса"
    
    @pytest.mark.asyncio
    async def test_initialize_method(self):
        """Тест метода initialize."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        tool = TestTool("test_tool", mock_system_context)
        
        result = await tool.initialize()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_execute_method(self):
        """Тест метода execute."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        tool = TestTool("test_tool", mock_system_context)
        input_data = ConcreteToolInput()
        
        result = await tool.execute(input_data)
        
        assert isinstance(result, ConcreteToolOutput)
    
    @pytest.mark.asyncio
    async def test_shutdown_method(self):
        """Тест метода shutdown."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        tool = TestTool("test_tool", mock_system_context)
        
        # Просто проверяем, что метод не вызывает исключений
        await tool.shutdown()


def test_tool_input_abstract():
    """Тест, что ToolInput является абстрактным классом."""
    with pytest.raises(TypeError):
        ToolInput()


def test_tool_output_abstract():
    """Тест, что ToolOutput является абстрактным классом."""
    with pytest.raises(TypeError):
        ToolOutput()
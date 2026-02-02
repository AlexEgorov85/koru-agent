"""Тесты для абстрактного класса BaseTool"""
import pytest
from abc import ABC, abstractmethod
from domain.abstractions.tools.base_tool import BaseTool
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus



class ConcreteTool(BaseTool):
    """Конкретная реализация BaseTool для целей тестирования"""
    
    async def execute(self, parameters, context=None):
        # Возвращаем фиктивный ExecutionResult
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="test result",
            observation_item_id="test_id",
            summary="test summary"
        )


class TestBaseTool:
    """Тесты для абстрактного класса BaseTool"""
    
    def test_base_tool_is_abstract_class(self):
        """Тест что BaseTool является абстрактным классом"""
        assert issubclass(BaseTool, ABC)
        assert hasattr(BaseTool, '__abstractmethods__')
        assert len(BaseTool.__abstractmethods__) > 0
    
    def test_base_tool_cannot_be_instantiated_directly(self):
        """Тест что BaseTool нельзя инстанцировать напрямую"""
        with pytest.raises(TypeError):
            BaseTool()
    
    def test_concrete_tool_can_be_instantiated(self):
        """Тест что конкретная реализация BaseTool может быть инстанцирована"""
        tool = ConcreteTool()
        assert tool is not None
        assert hasattr(tool, 'execute')
    
    def test_base_tool_has_expected_abstract_methods(self):
        """Тест что BaseTool имеет ожидаемые абстрактные методы"""
        expected_methods = ['execute']
        for method in expected_methods:
            assert hasattr(BaseTool, method)
            assert method in BaseTool.__abstractmethods__

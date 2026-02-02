"""Тесты для абстрактного класса BaseSkill"""
import pytest
from abc import ABC, abstractmethod
from domain.abstractions.skills.base_skill import BaseSkill
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus


class ConcreteSkill(BaseSkill):
    """Конкретная реализация BaseSkill для целей тестирования"""
    
    async def execute(self, capability, parameters, context=None):
        # Возвращаем фиктивный ExecutionResult
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="test result",
            observation_item_id="test_id",
            summary="test summary"
        )


class TestBaseSkill:
    """Тесты для абстрактного класса BaseSkill"""
    
    def test_base_skill_is_abstract_class(self):
        """Тест что BaseSkill является абстрактным классом"""
        assert issubclass(BaseSkill, ABC)
        assert hasattr(BaseSkill, '__abstractmethods__')
        assert len(BaseSkill.__abstractmethods__) > 0
    
    def test_base_skill_cannot_be_instantiated_directly(self):
        """Тест что BaseSkill нельзя инстанцировать напрямую"""
        with pytest.raises(TypeError):
            BaseSkill()
    
    def test_concrete_skill_can_be_instantiated(self):
        """Тест что конкретная реализация BaseSkill может быть инстанцирована"""
        skill = ConcreteSkill()
        assert skill is not None
        assert hasattr(skill, 'execute')
    
    def test_base_skill_has_expected_abstract_methods(self):
        """Тест что BaseSkill имеет ожидаемые абстрактные методы"""
        expected_methods = ['execute']
        for method in expected_methods:
            assert hasattr(BaseSkill, method)
            assert method in BaseSkill.__abstractmethods__

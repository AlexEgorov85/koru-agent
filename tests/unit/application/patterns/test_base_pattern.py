"""Тесты для базового паттерна"""
import pytest
from abc import ABC, abstractmethod
from application.orchestration.patterns.base import ComposablePattern


class ConcretePattern(ComposablePattern):
    """Конкретная реализация ComposablePattern для целей тестирования"""
    
    def execute(self, context):
        return "executed"


class TestBasePattern:
    """Тесты для базового паттерна"""
    
    def test_base_pattern_is_abstract_class(self):
        """Тест что ComposablePattern является абстрактным классом"""
        assert issubclass(ComposablePattern, ABC)
        assert hasattr(ComposablePattern, '__abstractmethods__')
        assert len(ComposablePattern.__abstractmethods__) > 0
    
    def test_base_pattern_cannot_be_instantiated_directly(self):
        """Тест что ComposablePattern нельзя инстанцировать напрямую"""
        with pytest.raises(TypeError):
            ComposablePattern()
    
    def test_concrete_pattern_can_be_instantiated(self):
        """Тест что конкретная реализация ComposablePattern может быть инстанцирована"""
        pattern = ConcretePattern()
        assert pattern is not None
        assert hasattr(pattern, 'execute')
    
    def test_base_pattern_has_expected_abstract_methods(self):
        """Тест что ComposablePattern имеет ожидаемые абстрактные методы"""
        expected_methods = ['execute']
        for method in expected_methods:
            assert hasattr(ComposablePattern, method)
            assert method in ComposablePattern.__abstractmethods__

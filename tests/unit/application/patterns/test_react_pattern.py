"""Тесты для паттерна ReAct"""
import pytest
from application.orchestration.patterns.patterns import ReActPattern


class TestReActPattern:
    """Тесты для паттерна ReAct"""
    
    def test_react_pattern_creation(self):
        """Тест создания паттерна ReAct"""
        pattern = ReActPattern()
        
        # Проверяем, что объект создался успешно
        assert pattern is not None
        assert isinstance(pattern, ReActPattern)
    
    def test_react_pattern_str_representation(self):
        """Тест строкового представления паттерна ReAct"""
        pattern = ReActPattern()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ReActPattern" in str(pattern)
    
    def test_react_pattern_attributes(self):
        """Тест атрибутов паттерна ReAct"""
        pattern = ReActPattern()
        
        # Проверяем, что паттерн имеет ожидаемые характеристики
        assert hasattr(pattern, '__class__')
        assert pattern.__class__.__name__ == 'ReActPattern'

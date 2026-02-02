"""Тесты для контекста сессии"""
import pytest
from application.context.session.session_context import SessionContext


class TestSessionContextApp:
    """Тесты для контекста сессии в приложении"""
    
    def test_session_context_creation(self):
        """Тест создания контекста сессии"""
        context = SessionContext()
        
        # Проверяем, что объект создался успешно
        assert context is not None
        assert hasattr(context, 'get_session_data')
        assert hasattr(context, 'set_session_data')
    
    def test_session_context_initial_state(self):
        """Тест начального состояния контекста сессии"""
        context = SessionContext()
        
        # Проверяем начальное состояние
        assert context.get_session_data('steps') == []
    
    def test_session_context_set_and_get_context(self):
        """Тест установки и получения контекста"""
        context = SessionContext()
        test_data = {"key": "value"}
        
        context.set_session_data("test_key", test_data)
        retrieved_data = context.get_session_data("test_key")
        
        assert retrieved_data == test_data
    
    def test_session_context_str_representation(self):
        """Тест строкового представления контекста сессии"""
        context = SessionContext()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "SessionContext" in str(context)
    
    def test_session_context_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        context = SessionContext()
        
        repr_str = repr(context)
        assert "SessionContext" in repr_str

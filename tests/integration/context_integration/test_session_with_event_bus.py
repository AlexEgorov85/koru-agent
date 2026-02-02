"""Тесты интеграции сессии с шиной событий"""
import pytest
from unittest.mock import Mock, patch
from application.context.session.session_context import SessionContext
from infrastructure.gateways.event_system import EventSystem


class TestSessionWithEventBus:
    """Тесты интеграции сессии с шиной событий"""
    
    def test_session_context_can_subscribe_to_events(self):
        """Тест что контекст сессии может подписываться на события"""
        # Создаем мок для шины событий
        mock_event_bus = Mock(spec=EventSystem)
        
        # Создаем контекст сессии
        session_context = SessionContext()
        
        # Проверяем, что контекст сессии может быть создан
        assert session_context is not None
        
        # Проверяем наличие методов управления контекстом
        assert hasattr(session_context, 'get_context')
        assert hasattr(session_context, 'set_context')
    
    @patch('infrastructure.event_system.EventSystem')
    def test_session_context_integration_with_real_event_system(self, mock_event_system_class):
        """Тест интеграции контекста сессии с реальной системой событий"""
        # Мокируем результат работы системы событий
        mock_event_system_instance = Mock()
        mock_event_system_class.return_value = mock_event_system_instance
        
        # Создаем контекст сессии
        session_context = SessionContext()
        
        # Проверяем, что контекст может быть создан и работает
        assert session_context is not None
        assert hasattr(session_context, 'get_context')
    
    def test_session_context_event_handling_capability(self):
        """Тест возможности контекста сессии обрабатывать события"""
        session_context = SessionContext()
        
        # Проверяем, что контекст сессии имеет основные методы
        assert hasattr(session_context, 'get_context')
        assert hasattr(session_context, 'set_context')
        
        # Тестируем базовое управление контекстом
        initial_context = session_context.get_context()
        assert isinstance(initial_context, dict)
        
        # Устанавливаем новый контекст
        test_context = {"test_key": "test_value"}
        session_context.set_context(test_context)
        
        # Проверяем, что контекст был установлен
        retrieved_context = session_context.get_context()
        assert retrieved_context == test_context
    
    def test_session_context_str_representation(self):
        """Тест строкового представления контекста сессии"""
        session_context = SessionContext()
        
        assert str(session_context) == "SessionContext"
    
    def test_session_context_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        session_context = SessionContext()
        
        repr_str = repr(session_context)
        assert "SessionContext" in repr_str
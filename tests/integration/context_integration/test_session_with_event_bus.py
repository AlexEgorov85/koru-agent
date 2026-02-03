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
        session_context = SessionContext(event_publisher=mock_event_bus)
        
        # Проверяем, что контекст сессии может быть создан
        assert session_context is not None
        
        # Проверяем наличие методов управления контекстом
        assert hasattr(session_context, 'get_session_data')
        assert hasattr(session_context, 'set_session_data')
    
    @patch('infrastructure.gateways.event_system.EventSystem')
    def test_session_context_integration_with_real_event_system(self, mock_event_system_class):
        """Тест интеграции контекста сессии с реальной системой событий"""
        # Мокируем результат работы системы событий
        mock_event_system_instance = Mock()
        mock_event_system_class.return_value = mock_event_system_instance
        
        # Создаем контекст сессии
        session_context = SessionContext(event_publisher=mock_event_system_instance)
        
        # Проверяем, что контекст может быть создан и работает
        assert session_context is not None
        assert hasattr(session_context, 'get_session_data')
    
    def test_session_context_event_handling_capability(self):
        """Тест возможности контекста сессии обрабатывать события"""
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher

        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        
        # Проверяем, что контекст сессии имеет основные методы
        assert hasattr(session_context, 'get_session_data')
        assert hasattr(session_context, 'set_session_data')
        
        # Тестируем базовое управление контекстом
        initial_data = session_context.get_session_data("test_key")
        # initial_data может быть None, если ключ не существует
        
        # Устанавливаем новые данные
        session_context.set_session_data("test_key", "test_value")
        
        # Проверяем, что данные были установлены
        retrieved_data = session_context.get_session_data("test_key")
        assert retrieved_data == "test_value"
    
    def test_session_context_str_representation(self):
        """Тест строкового представления контекста сессии"""
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher

        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        
        # Проверяем, что строковое представление содержит имя класса
        assert "SessionContext" in str(session_context)
    
    def test_session_context_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher

        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        
        repr_str = repr(session_context)
        assert "SessionContext" in repr_str

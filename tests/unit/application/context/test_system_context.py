"""Тесты для системного контекста"""
import pytest
from application.context.system.system_context import SystemContext


class TestSystemContext:
    """Тесты для системного контекста"""
    
    def test_system_context_creation(self):
        """Тест создания системного контекста"""
        from unittest.mock import Mock
        from config.models import SystemConfig
        from domain.abstractions.event_system import IEventPublisher

        # Создаем моки для зависимостей
        mock_config = SystemConfig()
        mock_event_publisher = Mock(spec=IEventPublisher)
        context = SystemContext(config=mock_config, event_publisher=mock_event_publisher)
        
        # Проверяем, что объект создался успешно
        assert context is not None
    
    def test_system_context_initial_state(self):
        """Тест начального состояния системного контекста"""
        from unittest.mock import Mock
        from config.models import SystemConfig
        from domain.abstractions.event_system import IEventPublisher

        # Создаем моки для зависимостей
        mock_config = SystemConfig()
        mock_event_publisher = Mock(spec=IEventPublisher)
        context = SystemContext(config=mock_config, event_publisher=mock_event_publisher)
        
        # Проверяем начальное состояние
        assert context is not None
    
    def test_system_context_str_representation(self):
        """Тест строкового представления системного контекста"""
        context = SystemContext()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "SystemContext" in str(context)
    
    def test_system_context_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        context = SystemContext()
        
        repr_str = repr(context)
        assert "SystemContext" in repr_str

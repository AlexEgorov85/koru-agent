"""
Интеграционные тесты для SessionContext - упрощенного контейнера данных сессии.

Принципы тестирования:
1. Тесты описывают поведение, а не реализацию
2. Минимизация моков - разрешены только TestLLMProvider и InMemoryDBProvider
3. Запрещено мокировать тестируемые компоненты (DataContext, StepContext, SessionContext)
4. Тесты служат спецификацией поведения системы
5. Проверяется взаимодействие между компонентами
"""

import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional

from application.context.session.session_context import SessionContext
from application.context.session.models import ContextItem, ContextItemType, ContextItemMetadata, AgentStep


def test_session_context_creation_with_basic_properties():
    """
    SessionContext создается с базовыми свойствами: session_id, user_id, goal, metadata
    """
    session_context = SessionContext(
        user_id="user123",
        goal="Тестовая цель сессии",
        metadata={"priority": "high", "project": "test_project"}
    )
    
    # Проверяем, что основные атрибуты установлены
    assert session_context.session_id is not None
    assert session_context.user_id == "user123"
    assert session_context.goal == "Тестовая цель сессии"
    assert session_context.metadata["priority"] == "high"
    assert session_context.metadata["project"] == "test_project"
    assert session_context.created_at is not None


def test_session_context_has_data_and_step_contexts():
    """
    SessionContext содержит data_context и step_context как части архитектуры
    """
    session_context = SessionContext()
    
    # Проверяем, что оба контекста инициализированы
    assert session_context.data_context is not None
    assert session_context.step_context is not None


def test_session_context_implements_required_interface():
    """
    SessionContext реализует все необходимые методы интерфейса
    """
    session_context = SessionContext()
    
    # Проверяем, что все абстрактные методы реализованы
    assert hasattr(session_context, 'get_session_data')
    assert hasattr(session_context, 'set_session_data')
    assert hasattr(session_context, 'initialize')
    assert hasattr(session_context, 'cleanup')
    
    # Тестируем работу методов интерфейса
    session_context.set_session_data('test_key', 'test_value')
    retrieved_value = session_context.get_session_data('test_key')
    assert retrieved_value == 'test_value'
    
    # Тестируем initialize
    init_result = session_context.initialize()
    assert init_result is True


def test_session_context_with_updates_creates_new_instance():
    """
    with_updates создает новый экземпляр SessionContext с обновленными полями
    """
    original_context = SessionContext(
        user_id="user123",
        goal="Оригинальная цель",
        metadata={"original": "value"}
    )
    
    # Создаем новый контекст с обновлениями
    updated_context = original_context.with_updates(
        goal="Новая цель",
        user_id="user456"
    )
    
    # Проверяем, что это новый объект
    assert updated_context is not original_context
    
    # Проверяем, что обновленные поля изменились
    assert updated_context.goal == "Новая цель"
    assert updated_context.user_id == "user456"
    
    # Проверяем, что необновленные поля остались прежними
    assert updated_context.session_id == original_context.session_id  # ID сессии не меняется
    assert updated_context.metadata["original"] == "value"


def test_session_context_cleanup_works():
    """
    cleanup метод корректно очищает ресурсы
    """
    session_context = SessionContext()
    
    # Проверяем, что cleanup не вызывает ошибок
    try:
        session_context.cleanup()
        cleanup_successful = True
    except Exception:
        cleanup_successful = False
    
    assert cleanup_successful is True


def test_session_context_data_access_methods():
    """
    Методы доступа к данным работают корректно
    """
    session_context = SessionContext(
        user_id="test_user",
        goal="Тест цели"
    )
    
    # Тестируем get_session_data
    assert session_context.get_session_data('user_id') == "test_user"
    assert session_context.get_session_data('goal') == "Тест цели"
    assert session_context.get_session_data('nonexistent') is None
    
    # Тестируем set_session_data
    session_context.set_session_data('new_field', 'new_value')
    assert session_context.get_session_data('new_field') == 'new_value'
    
    # Проверяем, что можно установить и получить сложные объекты
    complex_data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
    session_context.set_session_data('complex_data', complex_data)
    assert session_context.get_session_data('complex_data') == complex_data
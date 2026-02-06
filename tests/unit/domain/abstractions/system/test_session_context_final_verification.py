"""
Финальная проверка стабилизированного SessionContext
"""
from application.context.session.session_context import SessionContext


def test_session_context_is_simple_data_container():
    """Тест, что SessionContext стал простым контейнером данных"""
    # Создаем SessionContext
    session = SessionContext(
        user_id="user123",
        goal="Тестовая цель",
        metadata={"priority": "high"}
    )
    
    # Проверяем, что SessionContext не содержит логики выполнения
    # и состоит только из данных и простых методов доступа к ним
    
    # Проверяем основные атрибуты данных
    assert hasattr(session, 'session_id')
    assert hasattr(session, 'user_id')
    assert hasattr(session, 'goal')
    assert hasattr(session, 'created_at')
    assert hasattr(session, 'metadata')
    assert hasattr(session, 'data_context')
    assert hasattr(session, 'step_context')
    
    # Проверяем, что в SessionContext нет методов с логикой выполнения
    # которые были в старой версии
    forbidden_methods = [
        'adapt_to_domain', 'adapt_to_pattern', 'validate_context_size',
        'get_paginated_context', 'prioritize_context_data', 'mark_stale_data',
        'get_stale_items', 'check_missing_data', 'get_relevant_context',
        'get_progress', 'clear_context', 'record_action', 'record_observation',
        'record_plan', 'record_decision', 'record_error', 'record_metric',
        'record_system_event', 'set_domain_specific_data', 'get_domain_specific_data',
        'set_pattern_specific_data', 'get_pattern_specific_data', 'get_domain_context_summary'
    ]
    
    for method in forbidden_methods:
        assert not hasattr(session, method), f"Метод {method} не должен присутствовать в упрощенном SessionContext"
    
    # Проверяем, что остались только простые методы доступа к данным
    allowed_methods = [
        'get_session_data', 'set_session_data', 'get_goal', 'get_last_steps',
        'initialize', 'cleanup', 'with_updates'
    ]
    
    for method in allowed_methods:
        assert hasattr(session, method), f"Метод {method} должен присутствовать в SessionContext"
    
    print("✓ SessionContext стал простым контейнером данных")


def test_session_context_immutable_behavior():
    """Тест, что SessionContext поддерживает immutable-подобное поведение через with_updates"""
    original_session = SessionContext(
        user_id="user123",
        goal="Оригинальная цель",
        metadata={"original": True}
    )
    
    # Создаем новый сессионный контекст с обновлениями
    updated_session = original_session.with_updates(
        goal="Новая цель",
        user_id="user456"
    )
    
    # Проверяем, что это разные объекты
    assert updated_session is not original_session, "with_updates должен создавать новый объект"
    
    # Проверяем, что оригинальный объект не изменился
    assert original_session.user_id == "user123", "Оригинальный объект не должен измениться"
    assert original_session.goal == "Оригинальная цель", "Оригинальный объект не должен измениться"
    
    # Проверяем, что новый объект имеет обновленные значения
    assert updated_session.user_id == "user456", "Новый объект должен иметь обновленные значения"
    assert updated_session.goal == "Новая цель", "Новый объект должен иметь обновленные значения"
    
    # Проверяем, что session_id остался тем же (это идентификатор сессии, не должен меняться)
    assert updated_session.session_id == original_session.session_id, "ID сессии должен оставаться неизменным"
    
    print("✓ SessionContext поддерживает immutable-подобное поведение")


def test_session_context_two_part_architecture():
    """Тест, что SessionContext поддерживает архитектуру с двумя частями (public и private)"""
    session = SessionContext(
        user_id="user123",
        goal="Тест цели"
    )
    
    # Проверяем, что существуют оба контекста
    assert hasattr(session, 'data_context'), "Должен существовать data_context (private часть)"
    assert hasattr(session, 'step_context'), "Должен существовать step_context (public часть)"
    
    # Оба контекста должны быть инициализированы
    assert session.data_context is not None, "data_context должен быть инициализирован"
    assert session.step_context is not None, "step_context должен быть инициализирован"
    
    print("✓ SessionContext поддерживает архитектуру с двумя частями (public и private)")


def test_session_context_no_side_effects():
    """Тест, что SessionContext не имеет побочных эффектов"""
    session = SessionContext(
        user_id="user123",
        goal="Тест цели"
    )
    
    # Проверяем, что в SessionContext нет:
    # - шины событий
    # - внешних зависимостей
    # - сетевых вызовов
    # - файловых операций
    # - других побочных эффектов
    
    # Проверяем, что нет publisher'а событий
    assert not hasattr(session, '_event_publisher'), "SessionContext не должен содержать event publisher"
    
    # Проверяем, что нет менеджеров доменов или других сложных компонентов
    assert not hasattr(session, 'domain_manager'), "SessionContext не должен содержать domain manager"
    assert not hasattr(session, 'current_pattern'), "SessionContext не должен содержать current_pattern"
    assert not hasattr(session, 'current_domain'), "SessionContext не должен содержать current_domain"
    assert not hasattr(session, 'pattern_history'), "SessionContext не должен содержать pattern_history"
    
    print("✓ SessionContext не имеет побочных эффектов")


def run_all_tests():
    """Запуск всех тестов финальной проверки"""
    print("Запуск финальной проверки стабилизированного SessionContext...")
    print()
    
    test_session_context_is_simple_data_container()
    test_session_context_immutable_behavior()
    test_session_context_two_part_architecture()
    test_session_context_no_side_effects()
    
    print()
    print("🎉 Все тесты финальной проверки пройдены!")
    print()
    print("SessionContext теперь:")
    print("- Простой контейнер данных конкретной сессии")
    print("- Immutable-ish (с поддержкой with_updates для создания новых экземпляров)")
    print("- С двумя логическими частями: data_context (private) и step_context (public)")
    print("- Без логики выполнения, валидации или других побочных эффектов")
    print("- Совместимый с существующими компонентами системы")


if __name__ == "__main__":
    run_all_tests()
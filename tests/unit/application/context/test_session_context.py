#!/usr/bin/env python3
"""
Тестирование реализации SessionContext
"""
import asyncio
from application.context.session.session_context import SessionContext
from infrastructure.gateways.event_system import EventSystem
from infrastructure.adapters.event_publisher_adapter import EventPublisherAdapter
from domain.abstractions.event_system import EventType


class MockEventPublisher:
    """Заглушка для тестирования публикации событий"""
    def __init__(self):
        self.events = []
    
    async def publish(self, event_type: EventType, source: str, data: any):
        event = {
            'event_type': event_type,
            'source': source,
            'data': data
        }
        self.events.append(event)
        print(f"MockEventPublisher: {event_type.value} from {source} with {data}")
    
    def subscribe(self, event_type, handler):
        pass


async def test_session_context():
    """Тестирование всех функций SessionContext"""
    print("=== ТЕСТИРОВАНИЕ SESSIONCONTEXT ===")
    
    # Создание mock-публиковщика событий
    mock_publisher = MockEventPublisher()
    
    # Создание контекста с интеграцией шины событий
    session = SessionContext(event_publisher=mock_publisher)
    
    print("\n1. ТЕСТ: Инициализация")
    result = await session.initialize()
    assert result == True
    assert session._initialized == True
    print("[PASS] Initialization successful")
    
    print("\n2. TEST: Data management")
    session.set_session_data('test_key', 'test_value')
    assert session.get_session_data('test_key') == 'test_value'
    assert 'last_updated' in session._session_data
    print("[PASS] Data management works")
    
    print("\n3. TEST: Goal management and domain adaptation")
    session.set_goal('Проанализировать структуру проекта и найти все Python файлы')
    assert session.get_goal() == 'Проанализировать структуру проекта и найти все Python файлы'
    
    domain = session.get_session_data('detected_domain')
    assert domain == 'code_analysis', f'Expected domain \"code_analysis\", got: {domain}'
    print(f"[PASS] Domain adaptation works: {domain}")
    
    # Test another domain
    session.set_goal('Сгенерировать SQL запрос для выборки пользователей')
    domain2 = session.get_session_data('detected_domain')
    assert domain2 == 'sql_generation', f'Expected domain \"sql_generation\", got: {domain2}'
    print(f"[PASS] Adaptation to another domain works: {domain2}")
    
    print("\n4. TEST: Step management")
    session.record_step(
        step_number=1,
        capability_name='project_map.analyze_project',
        action_item_id='action_1',
        observation_item_ids=['obs_1'],
        summary='Анализ структуры проекта'
    )
    session.record_step(
        step_number=2,
        capability_name='code_navigation.find_references',
        action_item_id='action_2',
        observation_item_ids=['obs_2', 'obs_3'],
        summary='Поиск ссылок на функцию'
    )
    
    current_step = session.get_current_step_number()
    assert current_step == 2
    print(f"[PASS] Number of steps: {current_step}")
    
    last_steps = session.get_last_steps(1)
    assert len(last_steps) == 1
    assert last_steps[0]['capability_name'] == 'code_navigation.find_references'
    print("[PASS] Getting last steps works")
    
    all_steps = session.get_last_steps(10)
    assert len(all_steps) == 2
    assert all_steps[0]['step_number'] == 1
    assert all_steps[1]['step_number'] == 2
    print("[PASS] Getting all steps works")
    
    print("\n5. TEST: Goal history")
    metadata = session.get_session_data('metadata')
    assert 'goal_history' in metadata
    assert len(metadata['goal_history']) == 2
    print("[PASS] Goal history works")
    
    print("\n6. TEST: Event publishing")
    assert len(mock_publisher.events) > 0, "Events are not published"
    print(f"[PASS] Event publishing works: {len(mock_publisher.events)} events")
    
    print("\n7. TEST: Cleanup")
    await session.cleanup()
    assert session._initialized == False
    print("[PASS] Cleanup works")
    
    print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")


def test_domain_detection():
    """Тестирование определения домена"""
    print("\\n=== ТЕСТ ОПРЕДЕЛЕНИЯ ДОМЕНА ===")
    
    session = SessionContext()
    # Не вызываем initialize, так как это асинхронный метод
    
    # Тест различных доменов
    test_cases = [
        ('Напиши SQL запрос для выборки пользователей', 'sql_generation'),
        ('Протестируй функцию обработки данных', 'testing'),
        ('Создай документацию для модуля', 'documentation'),
        ('Проанализируй структуру проекта', 'code_analysis'),
        ('Выполни задачу', 'general')  # Домен по умолчанию
    ]
    
    for goal, expected_domain in test_cases:
        domain = session._detect_domain_from_goal(goal)
        assert domain == expected_domain, f'Для цели "{goal}" ожидался домен "{expected_domain}", получен "{domain}"'
        print(f'[PASS] Goal: "{goal}" -> domain: "{domain}"')
    
    print("=== ТЕСТ ОПРЕДЕЛЕНИЯ ДОМЕНА ПРОЙДЕН ===")


if __name__ == "__main__":
    # Сначала тест синхронной части
    test_domain_detection()
    
    # Потом асинхронный тест
    asyncio.run(test_session_context())
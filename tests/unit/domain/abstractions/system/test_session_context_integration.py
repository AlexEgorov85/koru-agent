"""
Тест интеграции компонентов упрощенного контекста сессии
"""
from application.context.session.session_context import SessionContext
from application.context.session.models import ContextItemType, ContextItemMetadata


def test_basic_workflow():
    """Тест базового рабочего процесса с упрощенным SessionContext"""
    # Создаем сессию
    session = SessionContext(
        user_id="user123",
        goal="Анализировать код Python и найти ошибки",
        metadata={"priority": "high", "project": "example_project"}
    )
    
    # Проверяем основные атрибуты
    assert session.session_id is not None
    assert session.user_id == "user123"
    assert session.goal == "Анализировать код Python и найти ошибки"
    assert session.metadata["priority"] == "high"
    assert session.metadata["project"] == "example_project"
    
    # Проверяем, что контексты инициализированы
    assert session.data_context is not None
    assert session.step_context is not None
    
    # Проверяем, что атрибуты доступны напрямую
    assert session.session_id == session.session_id
    assert session.user_id == session.user_id
    assert session.goal == session.goal
    
    # Проверяем методы доступа к данным
    retrieved_goal = session.get_session_data('goal')
    assert retrieved_goal == "Анализировать код Python и найти ошибки"
    
    # Проверяем создание нового контекста с обновлениями
    new_session = session.with_updates(goal="Новое задание", user_id="user456")
    assert new_session.goal == "Новое задание"
    assert new_session.user_id == "user456"
    assert new_session.session_id == session.session_id  # ID сессии не должен измениться
    assert new_session != session  # Это должен быть новый объект
    
    print("Все базовые тесты пройдены успешно!")


if __name__ == "__main__":
    test_basic_workflow()
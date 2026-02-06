"""
Тест совместимости нового SessionContext с ExecutionGateway
"""
from application.context.session.session_context import SessionContext
from application.gateways.execution.execution_gateway import ExecutionGateway
from domain.abstractions.system.base_system_context import IBaseSystemContext
from unittest.mock import MagicMock


def test_session_context_compatibility_with_execution_gateway():
    """Тест, что новый SessionContext совместим с ExecutionGateway"""
    # Создаем SessionContext
    session = SessionContext(
        user_id="test_user",
        goal="Тестовая цель",
        metadata={"test": "value"}
    )
    
    # Проверяем, что у SessionContext есть необходимые атрибуты и методы
    # которые ожидает ExecutionGateway
    assert hasattr(session, 'session_id')
    assert hasattr(session, 'get_goal')
    assert hasattr(session, 'get_last_steps')
    
    # Проверяем, что методы работают
    assert session.session_id is not None
    assert session.get_goal() == "Тестовая цель"
    assert isinstance(session.get_last_steps(3), list)
    
    # Проверяем, что SessionContext наследуется от BaseSessionContext
    from domain.abstractions.system.base_session_context import BaseSessionContext
    assert isinstance(session, BaseSessionContext)
    
    print("Тест совместимости пройден успешно!")


if __name__ == "__main__":
    test_session_context_compatibility_with_execution_gateway()
"""
Исполнитель действий агента для новой архитектуры
"""
from typing import Optional
from core.application.context.base_system_context import BaseSystemContext
from models.capability import Capability
from core.session_context.base_session_context import BaseSessionContext
from models.execution import ExecutionResult
from core.security.user_context import UserContext


class ActionExecutor:
    """Единственная ответственность — выполнение capability."""

    def __init__(self, system_context: BaseSystemContext):
        self.system = system_context

    async def execute_capability(
        self,
        capability: Capability,
        parameters: dict,
        session_context: BaseSessionContext,
        user_context: Optional['UserContext'] = None  # Добавляем контекст пользователя
    ) -> ExecutionResult:
        """Выполняет capability с заданными параметрами и контекстом."""
        # Получаем текущий номер шага из сессии
        step_number = getattr(session_context, 'current_step', 0) + 1

        return await self.system.execution_gateway.execute_capability(
            capability=capability,
            action_payload=parameters,
            session=session_context,
            step_number=step_number,
            user_context=user_context  # Передаем контекст пользователя
        )
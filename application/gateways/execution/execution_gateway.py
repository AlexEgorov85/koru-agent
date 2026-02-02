from typing import Dict, Any
from domain.abstractions.system.base_system_context import IBaseSystemContext
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.models.capability import Capability
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus


class ExecutionGateway:
    """
    Шлюз выполнения capability.
    
    Отвечает за:
    1. Поиск навыка по capability
    2. Выполнение capability через навык
    3. Базовую обработку исключений
    """
    
    def __init__(self, system_context: IBaseSystemContext):
        self._system_context = system_context

    @staticmethod
    def _create_failed_result(error: str, summary: str) -> ExecutionResult:
        """Создание результата с ошибкой."""
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id=None,
            summary=summary,
            error=error
        )

    @staticmethod
    def _create_success_result(result: Any, summary: str) -> ExecutionResult:
        """Создание успешного результата."""
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result=result,
            observation_item_id=None,  # ID будет установлен в сессии
            summary=summary,
            error=None
        )

    async def execute_capability(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        session: BaseSessionContext,
        step_number: int = 0
    ) -> ExecutionResult:
        """
        Выполнение capability через соответствующий навык.
        
        Args:
            capability: Объект capability для выполнения
            parameters: Параметры для выполнения
            session: Контекст сессии
            step_number: Номер шага (для отслеживания)
            
        Returns:
            ExecutionResult с результатом выполнения
        """
        # 1. Получение навыка для capability
        skill = self._system_context.get_resource(capability.skill_name)
        if not skill:
            return self._create_failed_result(
                error=f"Skill for capability '{capability.name}' not found",
                summary=f"Cannot execute capability '{capability.name}'"
            )
        
        # 2. Выполнение через навык
        try:
            result = await skill.execute(parameters, session)
            return self._create_success_result(
                result=result,
                summary=f"Capability '{capability.name}' executed successfully"
            )
        except Exception as e:
            return self._create_failed_result(
                error=str(e),
                summary=f"Error executing capability '{capability.name}': {str(e)}"
            )

"""
Исполнитель действий агента для новой архитектуры
"""
from typing import Optional
from core.application.context.base_system_context import BaseSystemContext
from core.models.data.capability import Capability
from core.session_context.base_session_context import BaseSessionContext
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
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
        user_context: Optional['UserContext'] = None,  # Добавляем контекст пользователя
        capability_name: Optional[str] = None  # Имя capability для валидации
    ) -> ExecutionResult:
        """Выполняет capability с заданными параметрами и контекстом."""
        # Получаем текущий номер шага из сессии
        step_number = getattr(session_context, 'current_step', 0) + 1

        # В новой архитектуре вызываем capability напрямую через компонент
        # capability — это экземпляр BaseComponent (skill/tool/service)
        if hasattr(capability, 'execute'):
            # Создаём ExecutionContext из session_context
            from core.application.agent.components.action_executor import ExecutionContext
            execution_context = ExecutionContext(
                session_context=session_context,
                user_context=user_context
            )
            
            # Создаём объект Capability с правильным именем для валидации в компоненте
            from core.models.data.capability import Capability as CapabilityModel
            cap_obj = CapabilityModel(
                name=capability_name or getattr(capability, 'name', 'unknown'),
                description=f"Capability {capability_name}",
                skill_name=getattr(capability, 'name', 'unknown'),
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={}
            )

            # Вызываем метод execute компонента с правильными параметрами
            result = await capability.execute(
                capability=cap_obj,  # Передаём объект Capability с правильным именем
                parameters=parameters,
                execution_context=execution_context
            )

            # Обрабатываем результат — может быть ExecutionResult или dict
            if isinstance(result, ExecutionResult):
                return ExecutionResult(
                    status=result.status if isinstance(result.status, ExecutionStatus) else ExecutionStatus(result.status if isinstance(result.status, str) else str(result.status)),
                    data=result.data,
                    error=result.error,  # ✅ ИСПРАВЛЕНО: Передаём ошибку
                    metadata={
                        'capability': capability_name or getattr(capability, 'name', 'unknown'),
                        'step': step_number
                    },
                    side_effect=result.side_effect if hasattr(result, 'side_effect') else False
                )
            else:
                # Если результат — dict, считаем это успешным выполнением
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data=result,
                    metadata={
                        'capability': capability_name or getattr(capability, 'name', 'unknown'),
                        'step': step_number
                    }
                )
        else:
            # Fallback: пытаемся вызвать через execution_gateway если есть
            if hasattr(self.system, 'execution_gateway'):
                return await self.system.execution_gateway.execute_capability(
                    capability=capability,
                    action_payload=parameters,
                    session=session_context,
                    step_number=step_number,
                    user_context=user_context
                )
            else:
                # Если ничего не работает, возвращаем ошибку
                # Логирование через EventBusLogger если доступен system_context
                if hasattr(self.system, 'infrastructure_context') and hasattr(self.system.infrastructure_context, 'event_bus_logger'):
                    await self.system.infrastructure_context.event_bus_logger.error(
                        f"Capability {capability_name or getattr(capability, 'name', 'N/A')} не имеет метода execute и execution_gateway недоступен"
                    )
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    data={'error': f'Cannot execute capability {capability_name or getattr(capability, "name", "N/A")}'},
                    metadata={'capability': capability_name or getattr(capability, 'name', 'N/A'), 'step': step_number}
                )
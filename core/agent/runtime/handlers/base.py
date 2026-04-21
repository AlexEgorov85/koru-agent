"""
Базовые протоколы для конвейера выполнения шагов.
"""
from typing import Protocol, runtime_checkable, Optional

from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult


@runtime_checkable
class IStepHandler(Protocol):
    """
    Протокол обработчика шага в конвейере выполнения.
    
    Каждый хендлер отвечает за одну фазу выполнения шага:
    - Принятие решения (DecisionHandler)
    - Проверка политики (PolicyCheckHandler)
    - Выполнение действия (ActionHandler)
    """
    
    async def execute(self, context: SessionContext) -> Optional[ExecutionResult]:
        """
        Выполнить обработку шага.
        
        Args:
            context: Контекст сессии для чтения/записи состояния
            
        Returns:
            ExecutionResult если шаг завершён (успех или ошибка),
            None если обработка должна продолжиться следующими хендлерами
        """
        ...

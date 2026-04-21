"""
Конвейер выполнения шагов агента.
"""
from typing import List, Optional

from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult
from core.agent.runtime.handlers.base import IStepHandler


class ExecutionPipeline:
    """
    Конвейер для выполнения одного шага агента.
    
    Состоит из цепочки обработчиков (handlers), которые выполняются
    последовательно. Если хендлер возвращает ExecutionResult, 
    конвейер завершается и возвращает этот результат.
    
    Типичная цепочка:
    1. DecisionHandler — Pattern.decide()
    2. PolicyCheckHandler — проверка политики
    3. ActionHandler — выполнение действия
    """
    
    def __init__(self, handlers: List[IStepHandler]):
        self.handlers = handlers
    
    async def run(self, context: SessionContext) -> Optional[ExecutionResult]:
        """
        Выполнить конвейер обработчиков.
        
        Args:
            context: Контекст сессии
            
        Returns:
            ExecutionResult если один из хендлеров завершил шаг,
            None если все хендлеры прошли без результата
        """
        for handler in self.handlers:
            result = await handler.execute(context)
            if result is not None:
                # Хендлер завершил шаг (FINISH/FAIL или другое завершение)
                return result
        
        # Все хендлеры прошли без явного завершения
        return None

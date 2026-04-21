"""
Хендлер принятия решения через Pattern.
"""
from typing import Optional, TYPE_CHECKING

from core.agent.runtime.handlers.base import IStepHandler
from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult
from core.agent.behaviors.base import DecisionType

if TYPE_CHECKING:
    from core.agent.behaviors.react.pattern import ReActPattern


class DecisionHandler(IStepHandler):
    """
    Хендлер для вызова Pattern.decide() и обработки результата.
    
    Возвращает ExecutionResult если решение FINISH или FAIL,
    иначе возвращает None для продолжения конвейера.
    """
    
    def __init__(self, pattern: "ReActPattern", available_capabilities: list):
        self.pattern = pattern
        self.available_capabilities = available_capabilities
    
    async def execute(self, context: SessionContext) -> Optional[ExecutionResult]:
        """
        Вызвать Pattern.decide() и обработать решение.
        
        Returns:
            ExecutionResult если FINISH/FAIL, иначе None
        """
        decision = await self.pattern.decide(
            session_context=context,
            available_capabilities=self.available_capabilities,
        )
        
        # Сохраняем решение в контексте для использования следующими хендлерами
        context.step_context._current_decision = decision
        
        # FINISH — завершаем успешно
        if decision.type == DecisionType.FINISH:
            final_answer = decision.reasoning or ""
            if decision.result and decision.result.data:
                final_answer = str(decision.result.data)
            
            # Сохраняем диалог
            context.commit_turn(
                user_query=context.goal or "",
                assistant_response=final_answer,
                tools_used=[],
            )
            
            return decision.result or ExecutionResult.success(data=decision.reasoning)
        
        # FAIL — завершаем с ошибкой
        if decision.type == DecisionType.FAIL:
            error_msg = decision.error or "Неизвестная ошибка"
            
            # Сохраняем диалог
            context.commit_turn(
                user_query=context.goal or "",
                assistant_response=f"Ошибка выполнения: {error_msg}",
                tools_used=[],
            )
            
            return ExecutionResult.failure(error_msg)
        
        # ACT или SWITCH_STRATEGY — продолжаем конвейер
        return None
    
    @property
    def current_decision(self) -> Optional["Decision"]:
        """Получить текущее решение из контекста."""
        from core.agent.behaviors.base import Decision
        return getattr(self.context.step_context, "_current_decision", None)

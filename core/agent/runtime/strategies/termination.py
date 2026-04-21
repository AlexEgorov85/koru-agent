"""
Стратегии завершения цикла выполнения агента.
"""
from typing import Protocol, runtime_checkable

from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult
from core.agent.components.safe_executor import SafeExecutor


@runtime_checkable
class ITerminationStrategy(Protocol):
    """
    Протокол стратегии завершения цикла выполнения.
    
    Отвечает за генерацию финального ответа при:
    - Достижении max_steps
    - Раннем завершении по другим причинам
    
    Изолирована от pattern, policy и других компонентов.
    """
    
    async def handle_end_of_cycle(
        self,
        context: SessionContext,
        executor: SafeExecutor
    ) -> ExecutionResult:
        """
        Обработать завершение цикла выполнения.
        
        Args:
            context: Контекст сессии с накопленным состоянием
            executor: Безопасный исполнитель для генерации финального ответа
            
        Returns:
            ExecutionResult с финальным ответом или ошибкой
        """
        ...


class DefaultTerminationStrategy:
    """
    Стратегия завершения по умолчанию.
    
    Генерирует fallback-ответ через final_answer.generate если есть
    выполненные шаги, иначе возвращает ошибку.
    """
    
    async def handle_end_of_cycle(
        self,
        context: SessionContext,
        executor: SafeExecutor
    ) -> ExecutionResult:
        """
        Обработать завершение цикла выполнения.
        
        Если были выполнены шаги (>0), пытается сгенерировать финальный
        ответ через final_answer.generate. Иначе возвращает ошибку.
        """
        from core.infrastructure.logging.event_types import LogEventType
        import logging
        
        log = logging.getLogger(__name__)
        
        # Проверяем количество выполненных шагов
        if context.step_context.count() > 0:
            # Были выполнены шаги - пытаемся сгенерировать финальный ответ
            log.info(
                f"📝 Генерация финального ответа после {context.step_context.count()} шагов...",
                extra={"event_type": LogEventType.AGENT_STOP}
            )
            
            try:
                # Создаём контекст для выполнения
                from core.agent.components.action_executor import ExecutionContext
                
                exec_context = ExecutionContext(
                    session_context=context,
                    session_id=context.session_id,
                    agent_id=context.agent_id if hasattr(context, 'agent_id') else "unknown"
                )
                
                # Пытаемся сгенерировать финальный ответ
                result = await executor.execute(
                    capability_name="final_answer.generate",
                    parameters={
                        "goal": context.goal if hasattr(context, 'goal') else "",
                        "history_summary": context.get_history_summary() if hasattr(context, 'get_history_summary') else ""
                    },
                    context=exec_context
                )
                
                if result.status.value == "completed" and result.data:
                    log.info(
                        "✅ Финальный ответ сгенерирован успешно",
                        extra={"event_type": LogEventType.AGENT_STOP}
                    )
                    return result
                    
            except Exception as e:
                log.error(
                    f"❌ Ошибка при генерации финального ответа: {e}",
                    extra={"event_type": LogEventType.ERROR},
                    exc_info=True
                )
        
        # Нет шагов или ошибка генерации - возвращаем failure
        step_count = context.step_context.count() if hasattr(context.step_context, 'count') else 0
        error_msg = f"Max steps exceeded after {step_count} steps" if step_count > 0 else "No steps executed"
        
        log.warning(
            f"⚠️ Завершение без финального ответа: {error_msg}",
            extra={"event_type": LogEventType.AGENT_STOP}
        )
        
        return ExecutionResult.failure(error_msg)

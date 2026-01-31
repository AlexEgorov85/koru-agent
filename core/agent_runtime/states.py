"""Состояния выполнения агента."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.agent_runtime.execution_context import ExecutionContext
    from core.agent_runtime.model import StrategyDecision


class AgentStateInterface(ABC):
    """
    AgentStateInterface - интерфейс состояния агента.
    
    НАЗНАЧЕНИЕ:
    - Определяет общий интерфейс для всех возможных состояний агента
    - Позволяет реализовать паттерн "Состояние" для управления поведением агента
    - Обеспечивает возможность изменения поведения агента в зависимости от его текущего состояния
    
    ВОЗМОЖНОСТИ:
    - Обеспечивает единый метод выполнения для всех состояний
    - Позволяет реализовать различные режимы работы агента
    - Обеспечивает возможность переключения между состояниями
    - Обеспечивает инкапсуляцию логики, зависящей от состояния агента
    
    ПРИМЕРЫ РАБОТЫ:
    # Реализация конкретного состояния
    class ActiveState(AgentStateInterface):
        async def execute(self, context: ExecutionContext) -> StrategyDecision:
            # Логика выполнения для активного состояния
            decision = await context.strategy.next_step(context)
            return decision
    
    # Использование в агенте
    state = ActiveState()
    decision = await state.execute(context)
    """
    
    @abstractmethod
    async def execute(self, context: 'ExecutionContext') -> 'StrategyDecision':
        """Выполнить состояние."""
        pass


class ExecutionState(AgentStateInterface):
    """
    ExecutionState - состояние выполнения шага агента.
    
    НАЗНАЧЕНИЕ:
    - Выполняет основной цикл принятия решений и выполнения действий
    - Обрабатывает решения, принимаемые стратегией
    - Обновляет состояние агента в зависимости от результата выполнения
    
    ВОЗМОЖНОСТИ:
    - Вызывает метод стратегии для получения решения
    - Обрабатывает терминальные решения (остановка агента)
    - Обновляет флаг завершения работы агента
    - Возвращает принятое решение для дальнейшей обработки
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание состояния выполнения
    execution_state = ExecutionState()
    
    # Выполнение шага
    decision = await execution_state.execute(context)
    
    # Обработка решения
    if decision.action.is_terminal():
        context.state.finished = True
    """
    
    async def execute(self, context: 'ExecutionContext') -> 'StrategyDecision':
        """Выполнить основную логику шага."""
        # Получаем решение от паттерна мышления через контекст
        decision = await context.strategy.next_step(context)
        # Обновляем состояние агента
        if decision.action.is_terminal():
            context.state.finished = True
        
        return decision

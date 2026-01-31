"""Контекст выполнения для разделения ответственности."""
from dataclasses import dataclass
from typing import Any, Dict, TYPE_CHECKING
from core.agent_runtime.state import AgentState
from core.agent_runtime.progress import ProgressScorer
from core.agent_runtime.executor import ActionExecutor
from core.agent_runtime.policy import AgentPolicy
from core.system_context.base_system_contex import BaseSystemContext
from core.session_context.base_session_context import BaseSessionContext

if TYPE_CHECKING:
    from core.agent_runtime.thinking_patterns.base import AgentStrategyInterface
    from models.agent_state import AgentState


@dataclass
class ExecutionContext:
    """
    ExecutionContext - контекст выполнения агента.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает единый интерфейс доступа ко всем компонентам, необходимым для выполнения агента
    - Снижает связанность между компонентами, позволяя передавать только один объект
    - Предоставляет стратегиям доступ ко всем необходимым ресурсам
    
    ВОЗМОЖНОСТИ:
    - Хранит ссылки на все ключевые компоненты агента
    - Обеспечивает доступ к системному контексту
    - Обеспечивает доступ к сессионному контексту
    - Обеспечивает доступ к состоянию агента
    - Обеспечивает доступ к политике агента
    - Обеспечивает доступ к шкале прогресса
    - Обеспечивает доступ к исполнителю действий
    - Обеспечивает доступ к текущей стратегии
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание контекста выполнения
    context = ExecutionContext(
        system=system_context,
        session=session_context,
        state=agent_state,
        policy=agent_policy,
        progress=progress_scorer,
        executor=action_executor,
        strategy=current_strategy
    )
    
    # Использование в стратегии
    async def next_step(self, context: ExecutionContext) -> StrategyDecision:
        # Доступ к сессии
        session = context.session
        # Доступ к системе
        system = context.system
        # Доступ к состоянию
        state = context.state
        # Доступ к исполнителю
        executor = context.executor
        # Доступ к стратегии
        strategy = context.strategy
        
        # Логика стратегии
        # ...
        
        return decision
    """
    system: BaseSystemContext
    session: BaseSessionContext
    state: AgentState
    policy: AgentPolicy
    progress: ProgressScorer
    executor: ActionExecutor
    strategy: 'AgentStrategyInterface' = None

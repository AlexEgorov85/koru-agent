"""
Runtime — простой цикл выполнения агента.

АРХИТЕКТУРА (Этап 10):
- ТОЛЬКО цикл: Pattern.decide() → Executor.execute()
- БЕЗ decision logic (Pattern решает)
- БЕЗ loop detection (Pattern детектирует)
- БЕЗ no-progress checks (Pattern детектирует)
"""
import uuid
from typing import Optional

from core.application_context.application_context import ApplicationContext
from core.models.data.execution import ExecutionResult
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.safe_executor import SafeExecutor
from core.agent.components.failure_memory import FailureMemory
from core.agent.components.policy import RetryPolicy
from core.agent.behaviors.base import DecisionType
from core.infrastructure.event_bus.unified_event_bus import EventType


class AgentRuntime:
    """
    Простой цикл выполнения агента.
    
    ТОЛЬКО orchestration:
    1. Pattern.decide()
    2. Executor.execute()
    3. Запись в context
    """

    def __init__(
        self,
        application_context: ApplicationContext,
        goal: str,
        max_steps: int = 10,
        user_context=None,
        correlation_id: Optional[str] = None  # Для обратной совместимости
    ):
        self.application_context = application_context
        self.goal = goal
        self.max_steps = max_steps
        self.user_context = user_context
        self.correlation_id = correlation_id or str(uuid.uuid4())

        # Компоненты
        self.executor = ActionExecutor(application_context)
        self.failure_memory = FailureMemory()
        self.policy = RetryPolicy()
        
        self.safe_executor = SafeExecutor(
            executor=self.executor,
            failure_memory=self.failure_memory,
            max_retries=self.policy.max_retries,
            base_delay=self.policy.base_delay,
            max_delay=self.policy.max_delay
        )

        # Session context
        from core.session_context.session_context import SessionContext
        self.session_context = SessionContext(session_id=str(uuid.uuid4()))
        self.session_context.set_goal(goal)

        # Event bus logger
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация логгера."""
        event_bus = getattr(self.application_context.infrastructure_context, 'event_bus', None)
        if event_bus:
            from core.infrastructure.logging import EventBusLogger
            self.event_bus_logger = EventBusLogger(
                event_bus=event_bus,
                session_id="system",
                agent_id="system",
                component=self.__class__.__name__
            )

    async def run(self, goal: str = None, max_steps: Optional[int] = None) -> ExecutionResult:
        """Запуск цикла выполнения."""
        if goal:
            self.goal = goal
        if max_steps:
            self.max_steps = max_steps
        
        return await self._run_async()

    async def _run_async(self) -> ExecutionResult:
        """
        Простой цикл:
        1. Pattern.decide()
        2. Executor.execute()
        3. Запись в context
        """
        # Инициализация Pattern
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig
        
        # Создаём простой ComponentConfig для react_pattern
        component_config = ComponentConfig(
            name="react_pattern",
            variant_id="default"
        )
        
        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=component_config,
            application_context=self.application_context,
            executor=self.executor
        )
        if hasattr(pattern, 'initialize'):
            await pattern.initialize()

        # Начало сессии
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Запуск агента: {self.goal[:100]}...")
        
        self.session_context.record_action({
            "step": 0, "action": "initialization", "goal": self.goal
        }, step_number=0)

        # Публикация события
        event_bus = self.application_context.infrastructure_context.event_bus
        await event_bus._publish_internal(
            EventType.SESSION_STARTED,
            {"session_id": self.session_context.session_id, "goal": self.goal}
        )

        # Получаем доступные capability
        available_caps = await self._get_available_capabilities()

        # Цикл выполнения
        for step in range(self.max_steps):
            # Pattern решает
            decision = await pattern.decide(
                session_context=self.session_context,
                available_capabilities=available_caps
            )

            # Pattern решил FINISH?
            if decision.type == DecisionType.FINISH:
                return decision.result or ExecutionResult.success(data=decision.reasoning)

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                return ExecutionResult.failure(decision.error or "Unknown error")

            # Pattern решил ACT?
            if decision.type == DecisionType.ACT:
                result = await self.safe_executor.execute(
                    capability_name=decision.action,
                    parameters=decision.parameters or {},
                    context=ExecutionContext(session_context=self.session_context)
                )
                
                # Запись шага
                self.session_context.register_step(
                    step_number=step,
                    capability_name=decision.action or "unknown",
                    skill_name=(decision.action or "unknown").split('.')[0],
                    action_item_id='',
                    observation_item_ids=[],
                    summary=decision.reasoning,
                    status=result.status
                )

            # Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                pattern = self._load_pattern(decision.next_pattern)

        # Max steps exceeded
        return ExecutionResult.failure(f"Max steps ({self.max_steps}) exceeded")

    async def _get_available_capabilities(self):
        """Получить доступные capability."""
        if hasattr(self.application_context, 'get_all_skills'):
            return self.application_context.get_all_skills()
        elif hasattr(self.application_context, 'get_all_capabilities'):
            all_caps = await self.application_context.get_all_capabilities()
            return [
                cap for cap in all_caps
                if hasattr(cap, 'skill_name') and not cap.name.startswith('planning.')
            ]
        return []

    def _load_pattern(self, pattern_name: str):
        """Загрузить другой паттерн."""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig
        
        # Создаём простой ComponentConfig
        component_config = ComponentConfig(
            name=pattern_name or "react_pattern",
            variant_id="default"
        )
        
        return ReActPattern(
            component_name=pattern_name or "react_pattern",
            component_config=component_config,
            application_context=self.application_context,
            executor=self.executor
        )

    async def stop(self):
        """Остановка (для совместимости)."""
        pass

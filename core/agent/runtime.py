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
from core.models.data.execution import ExecutionResult, ExecutionStatus
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
        correlation_id: Optional[str] = None,
        agent_id: Optional[str] = "agent_001"
    ):
        self.application_context = application_context
        self.goal = goal
        self.max_steps = max_steps
        self.user_context = user_context
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.agent_id = agent_id

        # Компоненты
        self.executor = ActionExecutor(application_context)
        self.failure_memory = FailureMemory()
        self.policy = RetryPolicy()
        
        self.safe_executor = SafeExecutor(
            executor=self.executor,
            failure_memory=self.failure_memory,
            max_retries=self.policy.max_retries,
            base_delay=self.policy.retry_base_delay,
            max_delay=self.policy.retry_max_delay
        )

        self._pattern = None

        # Session context
        from core.session_context.session_context import SessionContext
        self.session_context = SessionContext(session_id=str(uuid.uuid4()), agent_id=self.agent_id)
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
                session_id=self.session_context.session_id,
                agent_id=self.agent_id,
                component=self.__class__.__name__
            )

    async def run(self, goal: str = None, max_steps: Optional[int] = None) -> ExecutionResult:
        """Запуск цикла выполнения."""
        if goal:
            self.goal = goal
        if max_steps:
            self.max_steps = max_steps
        
        return await self._run_async()

    async def _get_pattern(self):
        """
        Получение кэшированного Pattern.
        
        Pattern является READONLY — содержит только промпты и контракты,
        загруженные один раз при инициализации. Данные сессии (шаги, observations)
        хранятся в session_context и передаются как параметр в decide().
        """
        if self._pattern is None:
            await self._init_pattern()
        return self._pattern

    async def _init_pattern(self):
        """
        Инициализация Pattern (вызывается один раз за сессию).
        
        Промпты и контракты загружаются из хранилища и НЕ модифицируются.
        """
        if self._pattern is not None:
            return
            
        event_bus = self.application_context.infrastructure_context.event_bus
        await event_bus.publish(EventType.DEBUG, {"message": "🏭 Создание Pattern через ComponentFactory..."}, session_id=self.session_context.session_id, agent_id=self.agent_id)
        
        from core.agent.components.component_factory import ComponentFactory
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig
        
        behavior_configs = getattr(self.application_context.config, 'behavior_configs', {})
        
        component_config = behavior_configs.get('react_pattern')
        if not component_config:
            await event_bus.publish(EventType.WARNING, {"message": "⚠️ react_pattern не найден в behavior_configs, создаём новый"}, session_id=self.session_context.session_id, agent_id=self.agent_id)
            component_config = ComponentConfig(name="react_pattern", variant_id="default")
        else:
            await event_bus.publish(EventType.INFO, {"message": "✅ Получен component_config из application_context"}, session_id=self.session_context.session_id, agent_id=self.agent_id)
        
        factory = ComponentFactory(
            infrastructure_context=self.application_context.infrastructure_context
        )
        
        self._pattern = await factory.create_and_initialize(
            component_class=ReActPattern,
            name="react_pattern",
            application_context=self.application_context,
            component_config=component_config,
            executor=self.executor
        )
        
        if str(self._pattern._state) == "ComponentState.CREATED":
            await self._pattern.initialize()

    async def _run_async(self) -> ExecutionResult:
        """
        Простой цикл:
        1. Pattern.decide()
        2. Executor.execute()
        3. Запись в context
        """
        # Получаем кэшированный Pattern
        event_bus = self.application_context.infrastructure_context.event_bus
        pattern = await self._get_pattern()

        # Начало сессии
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Запуск агента: {self.goal[:100]}...")
        
        self.session_context.record_action({
            "step": 0, "action": "initialization", "goal": self.goal
        }, step_number=0)

        # Публикация события
        event_bus = self.application_context.infrastructure_context.event_bus
        await event_bus.publish(
            EventType.SESSION_STARTED,
            {"session_id": self.session_context.session_id, "agent_id": self.agent_id, "goal": self.goal},
            session_id=self.session_context.session_id,
            agent_id=self.agent_id
        )

        # Получаем доступные capability
        available_caps = await self._get_available_capabilities()
        await event_bus.publish(EventType.INFO, {"message": f"📦 Доступно capability: {len(available_caps)}"}, session_id=self.session_context.session_id, agent_id=self.agent_id)

        # Цикл выполнения
        executed_steps = 0
        for step in range(self.max_steps):
            await event_bus.publish(EventType.INFO, {
                "message": f"{'='*60}\n📍 ШАГ {step + 1}/{self.max_steps}\n{'='*60}"
            }, session_id=self.session_context.session_id, agent_id=self.agent_id)
            
            # Pattern решает
            await event_bus.publish(EventType.INFO, {"message": "🧠 Pattern.decide()..."}, session_id=self.session_context.session_id, agent_id=self.agent_id)
            decision = await pattern.decide(
                session_context=self.session_context,
                available_capabilities=available_caps
            )
            await event_bus.publish(EventType.INFO, {
                "message": f"✅ Pattern вернул: type={decision.type.value}" +
                          (f", action={decision.action}" if decision.action else "") +
                          (f"\n   reasoning: {decision.reasoning[:150]}..." if decision.reasoning else "")
            }, session_id=self.session_context.session_id, agent_id=self.agent_id)

            # Pattern решил FINISH?
            if decision.type == DecisionType.FINISH:
                return decision.result or ExecutionResult.success(data=decision.reasoning)

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                return ExecutionResult.failure(decision.error or "Unknown error")

            # Pattern решил ACT?
            if decision.type == DecisionType.ACT:
                await event_bus.publish(EventType.INFO, {"message": f"⚙️ Executor.execute({decision.action})..."}, session_id=self.session_context.session_id, agent_id=self.agent_id)
                result = await self.safe_executor.execute(
                    capability_name=decision.action,
                    parameters=decision.parameters or {},
                    context=ExecutionContext(
                        session_context=self.session_context,
                        session_id=self.session_context.session_id,
                        agent_id=self.agent_id
                    )
                )

                # Сохранение данных результата в data_context
                observation_item_ids = []
                items_count_before = self.session_context.data_context.count() if hasattr(self.session_context, 'data_context') else -1
                if result.data is not None:
                    from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata
                    observation_item = ContextItem(
                        item_id='',
                        session_id=self.session_context.session_id,
                        item_type=ContextItemType.OBSERVATION,
                        content=result.data,
                        quick_content=str(result.data)[:500] if result.data else None,
                        metadata=ContextItemMetadata(
                            source=decision.action,
                            step_number=executed_steps + 1,
                            capability_name=decision.action
                        )
                    )
                    observation_item_id = self.session_context.data_context.add_item(observation_item)
                    observation_item_ids = [observation_item_id]
                    items_count_after = self.session_context.data_context.count()
                    await event_bus.publish(EventType.INFO, {
                        "message": f"📝 Сохранено observation: item_id={observation_item_id}, items_before={items_count_before}, items_after={items_count_after}"
                    }, session_id=self.session_context.session_id, agent_id=self.agent_id)

                # Запись шага только после выполнения ACT
                executed_steps += 1
                self.session_context.register_step(
                    step_number=executed_steps,
                    capability_name=decision.action or "unknown",
                    skill_name=(decision.action or "unknown").split('.')[0],
                    action_item_id='',
                    observation_item_ids=observation_item_ids,
                    summary=decision.reasoning,
                    status=result.status
                )
                await event_bus.publish(EventType.INFO, {
                    "message": f"✅ Executor завершил: status={result.status.value}" +
                              (f"\n   ❌ Error: {result.error[:100]}..." if result.error else "")
                }, session_id=self.session_context.session_id, agent_id=self.agent_id)

                # Если это был final_answer.generate и результат успешный - завершаем
                if decision.action == "final_answer.generate" and result.status == ExecutionStatus.COMPLETED and result.data:
                    await event_bus.publish(EventType.INFO, {"message": "✅ Финальный ответ сгенерирован, завершаем цикл"}, session_id=self.session_context.session_id, agent_id=self.agent_id)
                    return result

            # Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                await event_bus.publish(EventType.INFO, {"message": f"🔄 SWITCH STRATEGY: {decision.next_pattern}"}, session_id=self.session_context.session_id, agent_id=self.agent_id)
                pattern = self._load_pattern(decision.next_pattern)
            
            # Pattern решил FINISH/FAIL?
            if decision.type == DecisionType.FINISH:
                await event_bus.publish(EventType.INFO, {"message": f"✅ FINISH: {decision.reasoning[:100] if decision.reasoning else 'Done'}..."}, session_id=self.session_context.session_id, agent_id=self.agent_id)
            if decision.type == DecisionType.FAIL:
                await event_bus.publish(EventType.ERROR_OCCURRED, {"message": f"❌ FAIL: {decision.error or 'Unknown error'}"}, session_id=self.session_context.session_id, agent_id=self.agent_id)

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

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
from core.models.enums.common_enums import ExecutionStatus


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
            base_delay=self.policy.retry_base_delay,
            max_delay=self.policy.retry_max_delay
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
        # Создаём Pattern через ComponentFactory (загружает ресурсы автоматически)
        event_bus = self.application_context.infrastructure_context.event_bus
        await event_bus.publish(EventType.DEBUG, {"message": "🏭 Создание Pattern через ComponentFactory..."})
        
        from core.agent.components.component_factory import ComponentFactory
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig
        
        # Получаем component_config из application_context.config
        behavior_configs = getattr(self.application_context.config, 'behavior_configs', {})
        await event_bus.publish(EventType.DEBUG, {"message": f"🔍 behavior_configs: {list(behavior_configs.keys())}"})
        
        component_config = behavior_configs.get('react_pattern')
        if not component_config:
            await event_bus.publish(EventType.WARNING, {"message": "⚠️ react_pattern не найден в behavior_configs, создаём новый"})
            component_config = ComponentConfig(name="react_pattern", variant_id="default")
        else:
            await event_bus.publish(EventType.INFO, {"message": "✅ Получен component_config из application_context"})
            await event_bus.publish(EventType.DEBUG, {"message": f"   prompt_versions: {getattr(component_config, 'prompt_versions', {})}"})
        
        factory = ComponentFactory(
            infrastructure_context=self.application_context.infrastructure_context
        )
        
        pattern = await factory.create_and_initialize(
            component_class=ReActPattern,
            name="react_pattern",
            application_context=self.application_context,
            component_config=component_config,
            executor=self.executor
        )
        await event_bus.publish(EventType.INFO, {"message": f"✅ Pattern создан (state={pattern._state})"})
        await event_bus.publish(EventType.DEBUG, {"message": f"🔍 pattern.prompts: {len(pattern.prompts)}"})
        await event_bus.publish(EventType.DEBUG, {"message": f"🔍 pattern.input_contracts: {len(pattern.input_contracts)}"})
        await event_bus.publish(EventType.DEBUG, {"message": f"🔍 pattern.output_contracts: {len(pattern.output_contracts)}"})
        
        # Pattern создан но state=CREATED - ресурсы ещё не скопированы
        # Нужно вызвать initialize() чтобы BaseComponent._preload_resources() скопировал ресурсы
        if str(pattern._state) == "ComponentState.CREATED":
            await event_bus.publish(EventType.INFO, {"message": "🔄 Pattern ещё не инициализирован, вызываем initialize()..."})
            init_success = await pattern.initialize()
            await event_bus.publish(EventType.INFO, {"message": f"✅ Pattern.initialize() вернул: {init_success}"})
            await event_bus.publish(EventType.DEBUG, {"message": f"🔍 pattern.prompts после init: {len(pattern.prompts)}"})
            await event_bus.publish(EventType.DEBUG, {"message": f"🔍 pattern.input_contracts после init: {len(pattern.input_contracts)}"})
            await event_bus.publish(EventType.DEBUG, {"message": f"🔍 pattern.output_contracts после init: {len(pattern.output_contracts)}"})
            # Debug: проверяем что в промптах
            for key, prompt in pattern.prompts.items():
                content = getattr(prompt, 'content', None)
                await event_bus.publish(EventType.DEBUG, {"message": f"   📄 Prompt '{key}': content len={len(content) if content else 'None'}"})

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
        print(f"📦 Доступно capability: {len(available_caps)}")

        # Цикл выполнения
        executed_steps = 0
        for step in range(self.max_steps):
            print(f"\n{'='*60}")
            print(f"📍 ШАГ {step + 1}/{self.max_steps}")
            print(f"{'='*60}")
            
            # Pattern решает
            print(f"🧠 Pattern.decide()...")
            decision = await pattern.decide(
                session_context=self.session_context,
                available_capabilities=available_caps
            )
            print(f"✅ Pattern вернул: type={decision.type.value}")
            if decision.action:
                print(f"   action: {decision.action}")
            if decision.reasoning:
                print(f"   reasoning: {decision.reasoning[:150]}...")

            # Pattern решил FINISH?
            if decision.type == DecisionType.FINISH:
                return decision.result or ExecutionResult.success(data=decision.reasoning)

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                return ExecutionResult.failure(decision.error or "Unknown error")

            # Pattern решил ACT?
            if decision.type == DecisionType.ACT:
                print(f"⚙️ Executor.execute({decision.action})...")
                result = await self.safe_executor.execute(
                    capability_name=decision.action,
                    parameters=decision.parameters or {},
                    context=ExecutionContext(session_context=self.session_context)
                )

                # Запись шага только после выполнения ACT
                executed_steps += 1
                self.session_context.register_step(
                    step_number=executed_steps,
                    capability_name=decision.action or "unknown",
                    skill_name=(decision.action or "unknown").split('.')[0],
                    action_item_id='',
                    observation_item_ids=[],
                    summary=decision.reasoning,
                    status=result.status
                )
                print(f"✅ Executor завершил: status={result.status.value}")
                if result.error:
                    print(f"   ❌ Error: {result.error[:100] if result.error else 'N/A'}...")

            # Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                print(f"🔄 SWITCH STRATEGY: {decision.next_pattern}")
                pattern = self._load_pattern(decision.next_pattern)
            
            # Pattern решил FINISH/FAIL?
            if decision.type == DecisionType.FINISH:
                print(f"✅ FINISH: {decision.reasoning[:100] if decision.reasoning else 'Done'}...")
            if decision.type == DecisionType.FAIL:
                print(f"❌ FAIL: {decision.error or 'Unknown error'}")

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

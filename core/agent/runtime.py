"""
Runtime — простой цикл выполнения агента.

АРХИТЕКТУРА (Этап 10):
- ТОЛЬКО цикл: Pattern.decide() → Executor.execute()
- БЕЗ decision logic (Pattern решает)
- БЕЗ loop detection (Pattern детектирует)
- БЕЗ no-progress checks (Pattern детектирует)
"""
import uuid
from typing import Any, Optional

from core.application_context.application_context import ApplicationContext
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.component_status import ComponentStatus
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.safe_executor import SafeExecutor
from core.agent.components.failure_memory import FailureMemory
from core.agent.components.policy import RetryPolicy
from core.agent.behaviors.base import DecisionType


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
        agent_id: Optional[str] = "agent_001",
        dialogue_history=None,
        agent_config: Optional[Any] = None
    ):
        self.application_context = application_context
        self.goal = goal
        self.max_steps = max_steps
        self.user_context = user_context
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.agent_id = agent_id
        self.agent_config = agent_config

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

        # Session context — всегда новый, но с копией истории диалога
        from core.session_context.session_context import SessionContext
        self.session_context = SessionContext(session_id=str(uuid.uuid4()), agent_id=self.agent_id)
        self.session_context.set_goal(goal)
        
        # Сохраняем ссылку на глобальную историю для обратной записи
        self._shared_dialogue_history = dialogue_history
        
        # Копируем историю диалога если передана
        if dialogue_history is not None:
            self.session_context.copy_dialogue_from(dialogue_history)

        # Логгер агента (1 сессия = 1 файл)
        log_session = application_context.infrastructure_context.log_session
        self.log = log_session.create_agent_logger(agent_id)
        self.log.info(f"Агент {agent_id} запущен, цель: {goal[:50]}...", extra={"event_type": LogEventType.AGENT_START})

    def _sync_dialogue_history_back(self):
        """
        Копирует новые сообщения из локальной истории в глобальную.
        
        Вызывается после commit_turn() для сохранения диалога между запросами.
        """
        if self._shared_dialogue_history is None:
            return
        
        local_history = self.session_context.dialogue_history
        shared_history = self._shared_dialogue_history
        
        # Копируем только те сообщения, которых ещё нет в глобальной истории
        # (по количеству сообщений)
        local_count = len(local_history.messages)
        shared_count = len(shared_history.messages)
        
        if local_count > shared_count:
            # Новые сообщения появились — копируем их
            new_messages = local_history.messages[shared_count:]
            for msg in new_messages:
                from core.session_context.dialogue_context import DialogueMessage
                shared_history.messages.append(
                    DialogueMessage(role=msg.role, content=msg.content, tools_used=list(msg.tools_used))
                )
            # Обрезаем если превышен лимит
            shared_history._trim()

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

        if self._pattern._state == ComponentStatus.CREATED:
            await self._pattern.initialize()

    async def _run_async(self) -> ExecutionResult:
        """
        Простой цикл:
        1. Pattern.decide()
        2. Executor.execute()
        3. Запись в context
        """
        # Получаем кэшированный Pattern
        pattern = await self._get_pattern()

        # Начало сессии
        self.log.info(f"Запуск агента: {self.goal}...", extra={"event_type": LogEventType.AGENT_START})

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
        self.log.info(f"📦 Доступно capability: {len(available_caps)}", extra={"event_type": LogEventType.SYSTEM_INIT})

        # Цикл выполнения
        executed_steps = 0
        for step in range(self.max_steps):
            self.log.info(
                f"📍 ШАГ {step + 1}/{self.max_steps}",
                extra={"event_type": LogEventType.STEP_STARTED}
            )
            self.log.info(
                "🤔 Анализирую запрос и выбираю следующее действие...",
                extra={"event_type": LogEventType.AGENT_THINKING}
            )

            # Pattern решает
            self.log.info("🧠 Pattern.decide()...", extra={"event_type": LogEventType.AGENT_DECISION})
            decision = await pattern.decide(
                session_context=self.session_context,
                available_capabilities=available_caps
            )
            decision_msg = (
                f"✅ Pattern вернул: type={decision.type.value}"
                + (f", action={decision.action}" if decision.action else "")
                + (f", reasoning: {decision.reasoning}" if decision.reasoning else "")
            )
            self.log.info(decision_msg, extra={"event_type": LogEventType.AGENT_DECISION})

            self.log.info(
                f"🎯 Выбрано действие: {decision.action}",
                extra={"event_type": LogEventType.AGENT_DECISION}
            )
            
            # Pattern решил FINISH?
            if decision.type == DecisionType.FINISH:
                self.log.info(
                    f"Завершение: {decision.reasoning if decision.reasoning else 'готов'}",
                    extra={"event_type": LogEventType.AGENT_STOP}
                )
                # Сохраняем диалог в историю
                final_answer = decision.reasoning or ""
                if decision.result and decision.result.data:
                    final_answer = str(decision.result.data)
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=final_answer,
                    tools_used=[]
                )
                self._sync_dialogue_history_back()
                return decision.result or ExecutionResult.success(data=decision.reasoning)

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                self.log.error(
                    f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    extra={"event_type": LogEventType.AGENT_STOP}
                )
                # Сохраняем диалог даже при ошибке
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    tools_used=[]
                )
                self._sync_dialogue_history_back()
                return ExecutionResult.failure(decision.error or "Unknown error")

            # Pattern решил ACT?
            if decision.type == DecisionType.ACT:
                self.log.info(
                    f"⚙️ Запускаю {decision.action} с параметрами: {decision.parameters or {}}",
                    extra={"event_type": LogEventType.TOOL_CALL}
                )
                self.log.info(
                    f"⚙️ Executor.execute({decision.action})...",
                    extra={"event_type": LogEventType.TOOL_CALL}
                )

                # Публикуем детали выбран capability
                await event_bus.publish(
                    EventType.CAPABILITY_SELECTED,
                    {
                        "capability": decision.action,
                        "pattern": decision.type.value,
                        "reasoning": decision.reasoning or "",
                        "step": step + 1
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id
                )

                # Логируем для UI (через LogEventType — читается из файла)
                self.log.info(
                    f"🎯 Capability: {decision.action} | {decision.reasoning or ''}",
                    extra={"event_type": LogEventType.AGENT_DECISION}
                )

                try:
                    result = await self.safe_executor.execute(
                        capability_name=decision.action,
                        parameters=decision.parameters or {},
                        context=ExecutionContext(
                            session_context=self.session_context,
                            session_id=self.session_context.session_id,
                            agent_id=self.agent_id
                        )
                    )

                    # Логирование результата
                    if result.status == ExecutionStatus.FAILED:
                        self.log.error(
                            f"❌ Действие {decision.action} завершилось с ошибкой: {result.error or 'неизвестная'}",
                            extra={"event_type": LogEventType.TOOL_ERROR}
                        )
                    else:
                        self.log.info(
                            f"✅ Действие {decision.action} выполнено",
                            extra={"event_type": LogEventType.TOOL_RESULT}
                        )
                except Exception as e:
                    # SafeExecutor не должен выбрасывать, но на всякий случай
                    self.log.error(
                        f"❌ Исключение при выполнении {decision.action}: {e}",
                        extra={"event_type": LogEventType.TOOL_ERROR},
                        exc_info=True
                    )
                    result = ExecutionResult.failure(str(e))

                # Публикуем детали выполненного действия
                await event_bus.publish(
                    EventType.ACTION_PERFORMED,
                    {
                        "action": decision.action,
                        "parameters": decision.parameters or {},
                        "status": result.status.value,
                        "error": result.error,
                        "step": step + 1
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id
                )

                # Логируем для UI (через LogEventType — читается из файла)
                if result.status == ExecutionStatus.FAILED:
                    self.log.info(
                        f"❌ {decision.action} → FAILED: {result.error or 'неизвестная'}",
                        extra={"event_type": LogEventType.TOOL_ERROR}
                    )
                else:
                    self.log.info(
                        f"✅ {decision.action} → {result.status.value}",
                        extra={"event_type": LogEventType.TOOL_RESULT}
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
                        quick_content=str(result.data) if result.data else None,
                        metadata=ContextItemMetadata(
                            source=decision.action,
                            step_number=executed_steps + 1,
                            capability_name=decision.action
                        )
                    )
                    observation_item_id = self.session_context.data_context.add_item(observation_item)
                    observation_item_ids = [observation_item_id]
                    items_count_after = self.session_context.data_context.count()
                    self.log.info(
                        f"📝 Сохранено observation: item_id={observation_item_id}, items: {items_count_before}→{items_count_after}",
                        extra={"event_type": LogEventType.STEP_COMPLETED}
                    )

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
                              (f"\n   ❌ Error: {result.error}" if result.error else "")
                }, session_id=self.session_context.session_id, agent_id=self.agent_id)

                # Если это был final_answer.generate и результат успешный - завершаем
                if decision.action == "final_answer.generate" and result.status == ExecutionStatus.COMPLETED and result.data:
                    final_answer_data = str(result.data)
                    await event_bus.publish(EventType.AGENT_THINKING, {
                        "message": "✅ Финальный ответ сгенерирован",
                        "step": step + 1
                    }, session_id=self.session_context.session_id, agent_id=self.agent_id)
                    await event_bus.publish(EventType.SESSION_ANSWER, {
                        "answer": final_answer_data,
                        "goal": self.goal
                    }, session_id=self.session_context.session_id, agent_id=self.agent_id)
                    await event_bus.publish(EventType.INFO, {"message": "✅ Финальный ответ сгенерирован, завершаем цикл"}, session_id=self.session_context.session_id, agent_id=self.agent_id)
                    # Сохраняем диалог в историю
                    self.session_context.commit_turn(
                        user_query=self.goal,
                        assistant_response=final_answer_data,
                        tools_used=[]
                    )
                    self._sync_dialogue_history_back()
                    return result

            # Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                await event_bus.publish(EventType.INFO, {"message": f"🔄 SWITCH STRATEGY: {decision.next_pattern}"}, session_id=self.session_context.session_id, agent_id=self.agent_id)
                pattern = self._load_pattern(decision.next_pattern)
            
            # Pattern решил FINISH/FAIL?
            if decision.type == DecisionType.FINISH:
                await event_bus.publish(EventType.INFO, {"message": f"✅ FINISH: {decision.reasoning if decision.reasoning else 'Done'}..."}, session_id=self.session_context.session_id, agent_id=self.agent_id)
            if decision.type == DecisionType.FAIL:
                await event_bus.publish(EventType.ERROR_OCCURRED, {"message": f"❌ FAIL: {decision.error or 'Unknown error'}"}, session_id=self.session_context.session_id, agent_id=self.agent_id)

        # Max steps exceeded — сохраняем диалог
        self.session_context.commit_turn(
            user_query=self.goal,
            assistant_response=f"Превышено максимальное количество шагов ({self.max_steps})",
            tools_used=[]
        )
        self._sync_dialogue_history_back()
        return ExecutionResult.failure(f"Max steps ({self.max_steps}) exceeded")

    async def _get_available_capabilities(self):
        """Получить доступные capability с учётом фильтрации."""
        if hasattr(self.application_context, 'get_all_skills'):
            all_caps = self.application_context.get_all_skills()
        elif hasattr(self.application_context, 'get_all_capabilities'):
            filter_config = self._get_capability_filter_config()
            all_caps = await self.application_context.get_all_capabilities(
                include_hidden=filter_config.get("include_hidden", False),
                component_types=filter_config.get("component_types", ["skill"])
            )
        else:
            return []
        
        # Фильтрация по флагу visiable в самом capability
        return [
            cap for cap in all_caps
            if getattr(cap, 'visiable', True)
        ]
    
    def _get_capability_filter_config(self) -> dict:
        """Получить конфигурацию фильтрации capability из AgentConfig."""
        if hasattr(self, 'agent_config') and self.agent_config:
            cap_filter = getattr(self.agent_config, 'capability_filter', None)
            if cap_filter:
                return cap_filter
        
        return {}

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

"""
Runtime — цикл выполнения агента с Observer и Metrics.

АРХИТЕКТУРА (Этап 10 + v2.0):
- Pattern.decide() → Policy.check() → Executor.execute() → Observer.analyze() → Metrics.update()
- Reflection validation в Pattern
- Policy проверки на повторы и empty_loop
- Observer LLM-анализ результатов
- AgentMetrics для отслеживания качества
"""

import uuid
from typing import Any, Dict, Optional

from core.agent.components.sql_recovery import SQLRecoveryAnalyzer
from core.application_context.application_context import ApplicationContext
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.component_status import ComponentStatus
from core.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.safe_executor import SafeExecutor
from core.errors.failure_memory import FailureMemory
from core.agent.components.observation_signal import ObservationSignalService
from core.agent.components.policy import RetryPolicy, AgentPolicy
from core.agent.components.agent_metrics import AgentMetrics
from core.agent.behaviors.base import Decision, DecisionType
from core.utils.observation_formatter import (
    format_observation,
    smart_format_observation,
)
from core.components.skills.utils.observation_policy import ObservationPolicy
from core.agent.components.observer import Observer
from core.agent.components.step_executor import StepExecutor
from core.config.agent_config import AgentConfig


class AgentRuntime:
    """
    Простой цикл выполнения агента.

    ТОЛЬКО orchestration:
    1. Pattern.decide()
    2. Executor.execute()
    3. Запись в context
    4. Observer.analyze() → Metrics.update()
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
        agent_config: Optional[Any] = None,
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
        self.policy = AgentPolicy()  # ← Обновлённая политика с проверками
        self.metrics = AgentMetrics()  # ← Метрики агента
        self.observer = Observer(application_context)  # ← Observer для анализа результатов
        
        # Fallback strategy (импортируем здесь чтобы избежать circular import)
        from core.agent.behaviors.services import FallbackStrategyService
        self.fallback_strategy = FallbackStrategyService()

        self.safe_executor = SafeExecutor(
            executor=self.executor,
            failure_memory=self.failure_memory,
            max_retries=self.policy.max_retries,
            base_delay=self.policy.retry_base_delay,
            max_delay=self.policy.retry_max_delay,
        )
        
        # Выделенный сервис observation-сигналов (SRP: runtime только оркестрирует).
        self.observation_signal_service = ObservationSignalService()

        self._pattern = None

        # Session context — всегда новый, но с копией истории диалога
        from core.session_context.session_context import SessionContext

        self.session_context = SessionContext(
            session_id=str(uuid.uuid4()), agent_id=self.agent_id
        )
        self.session_context.set_goal(goal)

        # Инициализируем step_executor с правильным session_id (после создания session_context)
        event_bus = self.application_context.infrastructure_context.event_bus
        log_session = self.application_context.infrastructure_context.log_session
        self.step_executor = StepExecutor(
            safe_executor=self.safe_executor,
            event_bus=event_bus,
            session_id=self.session_context.session_id,
            agent_id=self.agent_id,
            log_session=log_session
        )

        # Сохраняем ссылку на глобальную историю для обратной записи
        self._shared_dialogue_history = dialogue_history

        # Копируем историю диалога если передана
        if dialogue_history is not None:
            self.session_context.copy_dialogue_from(dialogue_history)

        # Логгер агента (1 сессия = 1 файл)
        log_session = application_context.infrastructure_context.log_session
        self.log = log_session.create_agent_logger(agent_id)
        self.log.info(
            f"Агент {agent_id} запущен, цель: {goal[:50]}...",
            extra={"event_type": LogEventType.AGENT_START},
        )

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
                    DialogueMessage(
                        role=msg.role,
                        content=msg.content,
                        tools_used=list(msg.tools_used),
                    )
                )
            # Обрезаем если превышен лимит
            shared_history._trim()

    async def run(
        self, goal: str = None, max_steps: Optional[int] = None
    ) -> ExecutionResult:
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
        await event_bus.publish(
            EventType.DEBUG,
            {"message": "🏭 Создание Pattern через ComponentFactory..."},
            session_id=self.session_context.session_id,
            agent_id=self.agent_id,
        )

        from core.components.component_factory import ComponentFactory
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        behavior_configs = getattr(
            self.application_context.config, "behavior_configs", {}
        )

        component_config = behavior_configs.get("react_pattern")
        if not component_config:
            await event_bus.publish(
                EventType.WARNING,
                {
                    "message": "⚠️ react_pattern не найден в behavior_configs, создаём новый"
                },
                session_id=self.session_context.session_id,
                agent_id=self.agent_id,
            )
            component_config = ComponentConfig(
                name="react_pattern", variant_id="default"
            )
        else:
            await event_bus.publish(
                EventType.INFO,
                {"message": "✅ Получен component_config из application_context"},
                session_id=self.session_context.session_id,
                agent_id=self.agent_id,
            )

        factory = ComponentFactory(
            infrastructure_context=self.application_context.infrastructure_context
        )

        self._pattern = await factory.create_and_initialize(
            component_class=ReActPattern,
            name="react_pattern",
            application_context=self.application_context,
            component_config=component_config,
            executor=self.executor,
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
        self.log.info(
            f"Запуск агента: {self.goal}...",
            extra={"event_type": LogEventType.AGENT_START},
        )

        self.session_context.record_action(
            {"step": 0, "action": "initialization", "goal": self.goal}, step_number=0
        )

        # Публикация события
        event_bus = self.application_context.infrastructure_context.event_bus
        await event_bus.publish(
            EventType.SESSION_STARTED,
            {
                "session_id": self.session_context.session_id,
                "agent_id": self.agent_id,
                "goal": self.goal,
            },
            session_id=self.session_context.session_id,
            agent_id=self.agent_id,
        )

        # Получаем доступные capability
        available_caps = await self._get_available_capabilities()
        self.log.info(
            f"📦 Доступно capability: {len(available_caps)}",
            extra={"event_type": LogEventType.SYSTEM_INIT},
        )

        # Цикл выполнения
        executed_steps = 0
        for step in range(self.max_steps):
            agent_state = self.session_context.agent_state
            if (
                agent_state.consecutive_repeated_actions >= 3
                or agent_state.consecutive_empty_results >= 3
            ):
                stop_reason = (
                    f"repeated_actions={agent_state.consecutive_repeated_actions}, "
                    f"empty_results={agent_state.consecutive_empty_results}"
                )
                agent_state.errors.append(f"STOP:{stop_reason}")
                await event_bus.publish(
                    EventType.SESSION_FAILED,
                    {"reason": stop_reason, "step": step + 1},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=f"Остановлено по policy: {stop_reason}",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                return ExecutionResult.failure(f"Stopped by policy: {stop_reason}")

            self.log.info(
                f"📍 ШАГ {step + 1}/{self.max_steps}",
                extra={"event_type": LogEventType.STEP_STARTED},
            )
            
            # Проверка условий остановки по метрикам
            should_stop, stop_reason = self.metrics.should_stop()
            if should_stop:
                self.log.warning(
                    f"🛑 Остановка: {stop_reason}",
                    extra={"event_type": LogEventType.AGENT_STOP}
                )
                await event_bus.publish(
                    EventType.DEBUG,
                    {"event": "AGENT_STOP_METRICS", "reason": stop_reason, "metrics": self.metrics.to_dict()},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id
                )
                return ExecutionResult.failure(f"Stopped: {stop_reason}")
            
            self.log.info(
                "🤔 Анализирую запрос и выбираю следующее действие...",
                extra={"event_type": LogEventType.AGENT_THINKING},
            )

            # Pattern решает
            self.log.info(
                "🧠 Pattern.decide()...",
                extra={"event_type": LogEventType.AGENT_DECISION},
            )
            decision = await pattern.decide(
                session_context=self.session_context,
                available_capabilities=available_caps,
            )
            decision_msg = (
                f"✅ Pattern вернул: type={decision.type.value}"
                + (f", action={decision.action}" if decision.action else "")
                + (f", reasoning: {decision.reasoning}" if decision.reasoning else "")
            )
            self.log.info(
                decision_msg, extra={"event_type": LogEventType.AGENT_DECISION}
            )

            # Pattern решил FINISH?
            if decision.type == DecisionType.FINISH:
                self.log.info(
                    f"Завершение: {decision.reasoning if decision.reasoning else 'готов'}. "
                    f"Запускаю final_answer.generate...",
                    extra={"event_type": LogEventType.AGENT_STOP},
                )
                try:
                    # Проверяем есть ли конфигурация для final_answer.generate
                    step_config = None
                    if self.agent_config and hasattr(self.agent_config, 'steps'):
                        for sid, cfg in self.agent_config.steps.items():
                            if cfg.capability == "final_answer.generate":
                                step_config = cfg
                                break
                    
                    if step_config:
                        final_result = await self.step_executor.execute_with_config(
                            step_config=step_config,
                            parameters={
                                "format_type": "structured",
                                "include_steps": True,
                                "include_evidence": True,
                                "max_sources": 20
                            },
                            context=ExecutionContext(
                                session_context=self.session_context,
                                session_id=self.session_context.session_id,
                                agent_id=self.agent_id,
                            ),
                            step_id=f"step_{sid}_finish"
                        )
                    else:
                        final_result = await self.safe_executor.execute(
                            capability_name="final_answer.generate",
                            parameters={
                                "format_type": "structured",
                                "include_steps": True,
                                "include_evidence": True,
                                "max_sources": 20
                            },
                            context=ExecutionContext(
                                session_context=self.session_context,
                                session_id=self.session_context.session_id,
                                agent_id=self.agent_id,
                            ),
                        )

                    if final_result.status == ExecutionStatus.COMPLETED:
                        final_answer = ""
                        if hasattr(final_result.data, 'get'):
                            final_answer = final_result.data.get("final_answer", "")
                        elif hasattr(final_result.data, 'final_answer'):
                            final_answer = final_result.data.final_answer
                        else:
                            final_answer = str(final_result.data)
                        self.session_context.commit_turn(
                            user_query=self.goal,
                            assistant_response=final_answer,
                            tools_used=["final_answer.generate"],
                        )
                        self._sync_dialogue_history_back()
                        return final_result
                except Exception as e:
                    self.log.error(f"Ошибка генерации финального ответа: {e}")

                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=decision.reasoning or "Завершено",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                return decision.result or ExecutionResult.success(
                    data=decision.reasoning
                )

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                self.log.error(
                    f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    extra={"event_type": LogEventType.AGENT_STOP},
                )
                # Сохраняем диалог даже при ошибке
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                return ExecutionResult.failure(decision.error or "Unknown error")

            # Pattern решил ACT?
            if decision.type == DecisionType.ACT:
                policy_allowed, policy_reason = self.policy.check_step(
                    decision.action or "",
                    decision.parameters or {},
                    self.session_context.agent_state,
                )
                if not policy_allowed:
                    policy_msg = f"POLICY_BLOCKED: {policy_reason}. Действие отклонено. Смени инструмент или параметры."
                    self.session_context.agent_state.errors.append(policy_msg)
                    # Добавляем заблокированное действие в step_context чтобы оно попало в историю
                    self.session_context.register_step(
                        step_number=step + 1,
                        capability_name=decision.action or "unknown",
                        skill_name="",
                        action_item_id=None,
                        observation_item_ids=[],
                        summary=f"Action blocked by policy: {policy_reason}",
                        status=ExecutionStatus.FAILED,
                        parameters=decision.parameters or {},
                    )
                    # Также добавляем в agent_state.history чтобы оно учитывалось при проверке повторов
                    self.session_context.agent_state.add_step(
                        action_name=decision.action or "unknown",
                        status="blocked",
                        parameters=decision.parameters or {},
                        observation={"status": "blocked", "reason": policy_reason},
                    )
                    self.session_context.record_action(
                        action_data={
                            "action": decision.action,
                            "parameters": decision.parameters,
                            "status": "blocked",
                            "reason": policy_reason,
                        },
                        step_number=step + 1,
                    )
                    await event_bus.publish(
                        EventType.ERROR_OCCURRED,
                        {
                            "reason": policy_reason,
                            "action": decision.action,
                            "step": step + 1,
                        },
                        session_id=self.session_context.session_id,
                        agent_id=self.agent_id,
                    )
                    self.log.warning(
                        f"⛔ Policy заблокировал действие {decision.action}: {policy_reason}",
                        extra={"event_type": LogEventType.WARNING},
                    )
                    executed_steps += 1
                    continue

                self.log.info(
                    f"⚙️ Запускаю {decision.action} с параметрами: {decision.parameters or {}}",
                    extra={"event_type": LogEventType.TOOL_CALL},
                )
                self.log.info(
                    f"⚙️ Executor.execute({decision.action})...",
                    extra={"event_type": LogEventType.TOOL_CALL},
                )

                # Публикуем детали выбран capability
                await event_bus.publish(
                    EventType.CAPABILITY_SELECTED,
                    {
                        "capability": decision.action,
                        "pattern": decision.type.value,
                        "reasoning": decision.reasoning or "",
                        "step": step + 1,
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )

                # Логируем для UI (через LogEventType — читается из файла)
                self.log.info(
                    f"🎯 Capability: {decision.action} | {decision.reasoning or ''}",
                    extra={"event_type": LogEventType.AGENT_DECISION},
                )

                try:
                    # Используем StepExecutor если есть конфигурация шага
                    step_config = None
                    if self.agent_config and hasattr(self.agent_config, 'steps'):
                        # Ищем шаг по capability name
                        for sid, cfg in self.agent_config.steps.items():
                            if cfg.capability == decision.action:
                                step_config = cfg
                                break
                    
                    if step_config:
                        # Выполняем через StepExecutor с конфигурацией
                        result = await self.step_executor.execute_with_config(
                            step_config=step_config,
                            parameters=decision.parameters or {},
                            context=ExecutionContext(
                                session_context=self.session_context,
                                session_id=self.session_context.session_id,
                                agent_id=self.agent_id,
                            ),
                            step_id=f"step_{sid}_{step + 1}"
                        )
                    else:
                        # Выполняем напрямую через SafeExecutor (без конфигурации шага)
                        result = await self.safe_executor.execute(
                            capability_name=decision.action,
                            parameters=decision.parameters or {},
                            context=ExecutionContext(
                                session_context=self.session_context,
                                session_id=self.session_context.session_id,
                                agent_id=self.agent_id,
                            ),
                        )

                    # Логирование результата
                    if result.status == ExecutionStatus.FAILED:
                        self.log.error(
                            f"❌ Действие {decision.action} завершилось с ошибкой: {result.error or 'неизвестная'}",
                            extra={"event_type": LogEventType.TOOL_ERROR},
                        )
                    else:
                        self.log.info(
                            f"✅ Действие {decision.action} выполнено",
                            extra={"event_type": LogEventType.TOOL_RESULT},
                        )
                except Exception as e:
                    # SafeExecutor не должен выбрасывать, но на всякий случай
                    self.log.error(
                        f"❌ Исключение при выполнении {decision.action}: {e}",
                        extra={"event_type": LogEventType.TOOL_ERROR},
                        exc_info=True,
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
                        "step": step + 1,
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )

                # Логируем для UI (через LogEventType — читается из файла)
                if result.status == ExecutionStatus.FAILED:
                    self.log.info(
                        f"❌ {decision.action} → FAILED: {result.error or 'неизвестная'}",
                        extra={"event_type": LogEventType.TOOL_ERROR},
                    )
                else:
                    self.log.info(
                        f"✅ {decision.action} → {result.status.value}",
                        extra={"event_type": LogEventType.TOOL_RESULT},
                    )

                # Сохранение данных результата в data_context
                observation_item_ids = []
                items_count_before = (
                    self.session_context.data_context.count()
                    if hasattr(self.session_context, "data_context")
                    else -1
                )

                if result.status == ExecutionStatus.FAILED:
                    # При ошибке создаём observation с деталями ошибки для истории шагов
                    from core.session_context.model import (
                        ContextItem,
                        ContextItemType,
                        ContextItemMetadata,
                    )

                    error_details = {
                        "error": result.error or "Неизвестная ошибка",
                        "status": "FAILED",
                        "capability": decision.action,
                        "parameters": decision.parameters or {},
                    }

                    # Добавляем stack trace если есть
                    if hasattr(result, "traceback") and result.traceback:
                        error_details["traceback"] = result.traceback[
                            :2000
                        ]  # Ограничиваем размер

                    observation_item = ContextItem(
                        item_id="",
                        session_id=self.session_context.session_id,
                        item_type=ContextItemType.ERROR_LOG,
                        content=error_details,
                        quick_content=f"❌ {result.error or 'Неизвестная ошибка'}"[
                            :200
                        ],
                        metadata=ContextItemMetadata(
                            source=decision.action,
                            step_number=executed_steps + 1,
                            capability_name=decision.action,
                            additional_data={
                                "is_error": True,
                                "error_type": (
                                    type(result.error).__name__
                                    if result.error
                                    else "Unknown"
                                ),
                            },
                        ),
                    )
                    observation_item_id = self.session_context.data_context.add_item(
                        observation_item
                    )
                    observation_item_ids = [observation_item_id]
                    items_count_after = self.session_context.data_context.count()
                    self.log.info(
                        f"📝 Сохранена ошибка: item_id={observation_item_id}, items: {items_count_before}→{items_count_after}",
                        extra={"event_type": LogEventType.STEP_COMPLETED},
                    )
                elif result.data in (None, {}, [], ""):
                    self.log.info(
                        f"⚠️ {decision.action} → ПУСТОЙ РЕЗУЛЬТАТ",
                        extra={"event_type": LogEventType.TOOL_RESULT},
                    )
                    self._record_empty_result(decision.action, decision.parameters)
                    await self._run_sql_diagnostic(decision, result)
                elif result.data is not None:
                    from core.session_context.model import (
                        ContextItem,
                        ContextItemType,
                        ContextItemMetadata,
                    )

                    additional_metadata = {}
                    parameters = decision.parameters or {}

                    # Проверяем, нужно ли использовать smart_format или полный формат
                    # data_analysis уже сохраняет результат в observation - используем полный формат
                    is_data_analysis = (
                        decision.action and "data_analysis" in decision.action
                    )

                    if is_data_analysis:
                        # Для data_analysis - используем полный формат (данные уже структурированы)
                        quick_content = format_observation(
                            result_data=result.data,
                            capability_name=decision.action,
                            parameters=decision.parameters,
                        )
                    else:
                        # Для остальных - smart_format с усечением
                        quick_content = smart_format_observation(
                            result_data=result.data,
                            capability_name=decision.action,
                            parameters=decision.parameters,
                        )

                    observation_item = ContextItem(
                        item_id="",
                        session_id=self.session_context.session_id,
                        item_type=ContextItemType.OBSERVATION,
                        content=result.data,
                        quick_content=quick_content,
                        metadata=ContextItemMetadata(
                            source=decision.action,
                            step_number=executed_steps + 1,
                            capability_name=decision.action,
                            additional_data=(
                                additional_metadata if additional_metadata else None
                            ),
                        ),
                    )
                    observation_item_id = self.session_context.data_context.add_item(
                        observation_item
                    )
                    observation_item_ids = [observation_item_id]
                    items_count_after = self.session_context.data_context.count()
                    self.log.debug(
                        f"📝 Сохранено observation: item_id={observation_item_id}, items: {items_count_before}→{items_count_after}",
                        extra={"event_type": LogEventType.STEP_COMPLETED},
                    )
                    # Логируем наблюдение в формате промта (INFO)
                    if quick_content:
                        self.log.info(
                            f"[OBSERVATION] step={executed_steps + 1} | capability={decision.action}\n{quick_content}",
                            extra={"event_type": LogEventType.STEP_COMPLETED},
                        )

                # Запись шага только после выполнения ACT
                executed_steps += 1
                
                # ============================================
                # OBSERVER + METRICS (новый этап v2.0)
                # ============================================
                
                # Observer анализирует результат
                self.log.info(
                    f"👁️ Observer.analyze({decision.action})...",
                    extra={"event_type": LogEventType.INFO}
                )
                
                observation = await self.observer.analyze(
                    action_name=decision.action,
                    parameters=decision.parameters or {},
                    result=result.data if hasattr(result, 'data') else result,
                    error=result.error if result.status == ExecutionStatus.FAILED else None,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    step_number=executed_steps
                )
                
                # Публикуем событие OBSERVATION
                await event_bus.publish(
                    EventType.DEBUG,
                    {"event": "OBSERVATION", "status": observation.get("status"), "quality": observation.get("data_quality")},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id
                )
                
                # Обновляем метрики на основе наблюдения
                status = observation.get("status", "unknown")
                self.metrics.add_step(
                    action_name=decision.action,
                    status=status,
                    error=observation.get("errors", [None])[0] if observation.get("errors") else None
                )
                self.metrics.update_observation(observation)
                
                # Логируем результат наблюдения
                self.log.info(
                    f"📊 Observation: status={status}, quality={observation.get('data_quality', {})}",
                    extra={"event_type": LogEventType.INFO}
                )
                
                # Проверяем рекомендации Observer для следующего шага
                if observation.get("requires_additional_action") and status in ["empty", "error"]:
                    self.log.warning(
                        f"⚠️ Observer рекомендует сменить стратегию: {observation.get('next_step_suggestion', '')}",
                        extra={"event_type": LogEventType.INFO}
                    )

                # Данные хранятся ТОЛЬКО в data_context (observation_item_ids)
                # AgentStep содержит только ССЫЛКИ на данные, не копии!
                self.session_context.register_step(
                    step_number=executed_steps,
                    capability_name=decision.action or "unknown",
                    skill_name=(decision.action or "unknown").split(".")[0],
                    action_item_id="",
                    observation_item_ids=observation_item_ids,
                    summary=decision.reasoning,
                    status=result.status,
                    parameters=decision.parameters or {},
                )

                if (
                    not hasattr(self, "observation_signal_service")
                    or self.observation_signal_service is None
                ):
                    self.observation_signal_service = ObservationSignalService()

                observation_signal = self.observation_signal_service.build_signal(
                    result=result,
                    action_name=decision.action,
                    parameters=decision.parameters or {},
                )
                self.session_context.agent_state.add_step(
                    action_name=decision.action or "unknown",
                    status=result.status.value,
                    parameters=decision.parameters or {},
                    observation=observation_signal,
                )
                self.session_context.agent_state.register_observation(
                    observation_signal
                )

                await event_bus.publish(
                    EventType.SESSION_STEP,
                    {
                        "step": executed_steps,
                        "action": decision.action,
                        "status": result.status.value,
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )
                await event_bus.publish(
                    EventType.TOOL_RESULT,
                    {
                        "step": executed_steps,
                        "action": decision.action,
                        "observation": observation_signal,
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )

                await event_bus.publish(
                    EventType.INFO,
                    {
                        "message": f"✅ Executor завершил: status={result.status.value}"
                        + (f"\n   ❌ Error: {result.error}" if result.error else "")
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )

            # Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                await event_bus.publish(
                    EventType.INFO,
                    {"message": f"🔄 SWITCH STRATEGY: {decision.next_pattern}"},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )
                pattern = self._load_pattern(decision.next_pattern)

            # Pattern решил FINISH/FAIL?
            if decision.type == DecisionType.FINISH:
                await event_bus.publish(
                    EventType.INFO,
                    {
                        "message": f"✅ FINISH: {decision.reasoning if decision.reasoning else 'Done'}..."
                    },
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )
            if decision.type == DecisionType.FAIL:
                await event_bus.publish(
                    EventType.ERROR_OCCURRED,
                    {"message": f"❌ FAIL: {decision.error or 'Unknown error'}"},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )

        # ─────────────────────────────────────────────────────────────
        # ЦИКЛ ЗАВЕРШЁН: Попытка сформировать ответ по имеющимся данным
        # ─────────────────────────────────────────────────────────────
        if executed_steps > 0:
            self.log.warning(
                f"Лимит шагов ({self.max_steps}) исчерпан. "
                f"Пытаюсь сгенерировать итоговый ответ на основе {executed_steps} шагов..."
            )
            try:
                # Проверяем есть ли конфигурация для final_answer.generate
                step_config = None
                if self.agent_config and hasattr(self.agent_config, 'steps'):
                    for sid, cfg in self.agent_config.steps.items():
                        if cfg.capability == "final_answer.generate":
                            step_config = cfg
                            break
                
                if step_config:
                    final_result = await self.step_executor.execute_with_config(
                        step_config=step_config,
                        parameters={
                            "format_type": "structured",
                            "include_steps": True,
                            "include_evidence": True,
                            "max_sources": 20
                        },
                        context=ExecutionContext(
                            session_context=self.session_context,
                            session_id=self.session_context.session_id,
                            agent_id=self.agent_id
                        ),
                        step_id=f"step_{sid}_final"
                    )
                else:
                    final_result = await self.safe_executor.execute(
                        capability_name="final_answer.generate",
                        parameters={
                            "format_type": "structured",
                            "include_steps": True,
                            "include_evidence": True,
                            "max_sources": 20
                        },
                        context=ExecutionContext(
                            session_context=self.session_context,
                            session_id=self.session_context.session_id,
                            agent_id=self.agent_id
                        )
                    )

                if final_result.status == ExecutionStatus.COMPLETED:
                    final_answer = ""
                    if hasattr(final_result.data, 'get'):
                        final_answer = final_result.data.get("final_answer", "")
                    elif hasattr(final_result.data, 'final_answer'):
                        final_answer = final_result.data.final_answer
                    else:
                        final_answer = str(final_result.data)
                    self.session_context.commit_turn(
                        user_query=self.goal,
                        assistant_response=final_answer,
                        tools_used=["final_answer.generate"]
                    )
                    self._sync_dialogue_history_back()
                    return final_result

            except Exception as e:
                self.log.error(f"Не удалось сгенерировать fallback-ответ: {e}")

        # ─────────────────────────────────────────────────────────────
        # FALLBACK: Если шагов не было или финальная генерация упала
        # ─────────────────────────────────────────────────────────────
        fallback_msg = f"Не удалось достичь цели за {self.max_steps} шагов."
        if executed_steps == 0:
            fallback_msg += " Действия не выполнялись."
        else:
            fallback_msg += f" Собрано данных за {executed_steps} шагов, но синтез ответа не удался."

        self.session_context.commit_turn(
            user_query=self.goal,
            assistant_response=fallback_msg,
            tools_used=[]
        )
        self._sync_dialogue_history_back()
        return ExecutionResult.failure(fallback_msg)

    def _build_observation_signal(
        self,
        result: ExecutionResult,
        action_name: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> dict:
        """Построить observation-сигнал для state из результата выполнения."""
        if result.status == ExecutionStatus.FAILED:
            return {
                "status": "error",
                "quality": "low",
                "issues": [result.error or "unknown_error"],
                "insight": result.error or "Ошибка выполнения действия",
                "next_step_hint": "Измени стратегию и выбери альтернативное действие",
            }

        if result.data in (None, {}, [], ""):
            hint = "Уточни параметры или выбери другой инструмент"
            issues = ["empty_result"]

            # Для unit-тестов, где Runtime создаётся через __new__,
            # инициализируем анализатор лениво.
            if (
                not hasattr(self, "sql_recovery_analyzer")
                or self.sql_recovery_analyzer is None
            ):
                self.sql_recovery_analyzer = SQLRecoveryAnalyzer()

            if self.sql_recovery_analyzer.is_sql_action(action_name):
                sql_analysis = self.sql_recovery_analyzer.analyze_empty_result(
                    parameters
                )
                issues.extend(sql_analysis.get("issues", []))
                hint = sql_analysis.get("next_step_hint", hint)

            return {
                "status": "empty",
                "quality": "useless",
                "issues": issues,
                "insight": "Действие завершилось без полезных данных",
                "next_step_hint": hint,
            }

        return {
            "status": "success",
            "quality": "high",
            "issues": [],
            "insight": "Получен полезный результат",
            "next_step_hint": "Продолжай по текущему плану",
        }

    async def _get_available_capabilities(self):
        """Получить доступные capability с учётом фильтрации."""
        if hasattr(self.application_context, "get_all_skills"):
            all_caps = self.application_context.get_all_skills()
        elif hasattr(self.application_context, "get_all_capabilities"):
            filter_config = self._get_capability_filter_config()
            all_caps = await self.application_context.get_all_capabilities(
                include_hidden=filter_config.get("include_hidden", False),
                component_types=filter_config.get("component_types", ["skill"]),
            )
        else:
            return []

        # Фильтрация по флагу visiable в самом capability
        return [cap for cap in all_caps if getattr(cap, "visiable", True)]

    def _get_capability_filter_config(self) -> dict:
        """Получить конфигурацию фильтрации capability из AgentConfig."""
        if hasattr(self, "agent_config") and self.agent_config:
            cap_filter = getattr(self.agent_config, "capability_filter", None)
            if cap_filter:
                return cap_filter

        return {}

    def _load_pattern(self, pattern_name: str):
        """Загрузить другой паттерн."""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        # Создаём простой ComponentConfig
        component_config = ComponentConfig(
            name=pattern_name or "react_pattern", variant_id="default"
        )

        return ReActPattern(
            component_name=pattern_name or "react_pattern",
            component_config=component_config,
            application_context=self.application_context,
            executor=self.executor,
        )

    def _record_empty_result(self, action_name: str, parameters: Dict[str, Any]) -> None:
        """
        Записать пустой результат в лог для активации режима исследования данных.

        Вызывается при пустом SQL-результате для активации _build_exploration_rules.
        """
        import re
        tables = []
        filters = {}

        sql = parameters.get("sql") or parameters.get("query") or ""
        if sql:
            match = re.search(r"\bfrom\s+([a-zA-Z0-9_\.]+)", sql, re.IGNORECASE)
            if match:
                tables.append(match.group(1))

            where_match = re.search(
                r"\bwhere\b(.*?)(\bgroup\s+by\b|\border\s+by\b|\blimit\b|$)",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            if where_match:
                where_clause = where_match.group(1)
                cond_pattern = re.compile(
                    r"([a-zA-Z_][a-zA-Z0-9_\.]*)\s*(=|!=|<>|>|<|>=|<=|like|ilike)\s*"
                    r"('(?:[^']|''|\\')*'|\d+(?:\.\d+)?|\b\d{4}-\d{2}-\d{2}\b)",
                    re.IGNORECASE,
                )
                for cond_match in cond_pattern.finditer(where_clause):
                    col = cond_match.group(1).split(".")[-1]
                    op = cond_match.group(2)
                    val = cond_match.group(3)
                    filters[col] = f"{op} {val}"
        elif parameters:
            for key, value in parameters.items():
                if key not in ("max_results", "max_rows", "query", "hints"):
                    filters[key] = value

        self.session_context.record_empty_result(
            tool=action_name,
            tables=tables,
            filters=filters if filters else None,
        )
        self.log.info(
            f"📊 Записан пустой результат: {action_name}, tables={tables}, filters={list(filters.keys())}",
            extra={"event_type": LogEventType.INFO},
        )

    async def _run_sql_diagnostic(
        self, decision: "Decision", result: "ExecutionResult"
    ) -> None:
        """
        Запускает SQLDiagnosticService после пустого результата.

        Выполняет диагностические запросы и инжектирует подсказки в agent_state.
        """
        import json

        sql_query = decision.parameters.get("sql") or decision.parameters.get("query") or ""
        if not sql_query or "sql" not in decision.action.lower():
            return

        try:
            if not hasattr(self, "_sql_diagnostic"):
                from core.agent.components.sql_diagnostic import SQLDiagnosticService

                self._sql_diagnostic = SQLDiagnosticService(self.executor)

            diag_result = await self._sql_diagnostic.analyze_empty_result(
                sql_query=sql_query,
                original_params=decision.parameters or {},
            )

            hints_text = "; ".join(diag_result.get("hints", []))
            self.session_context.agent_state.errors.append(
                f"SQL_DIAGNOSTIC: {hints_text}"
            )

            if diag_result.get("corrected_params"):
                self.session_context.agent_state.last_corrected_params = diag_result[
                    "corrected_params"
                ]
                corrected_list = ", ".join(
                    f"{k}={v}" for k, v in diag_result["corrected_params"].items()
                )
                self.log.info(
                    f"🔍 Диагностика нашла исправления: {corrected_list}",
                    extra={"event_type": LogEventType.INFO},
                )

            self.log.info(
                f"🔍 SQL диагностика: {hints_text}",
                extra={"event_type": LogEventType.INFO},
            )

        except Exception as e:
            self.log.warning(f"Ошибка SQL диагностики: {e}")

    async def stop(self):
        """Остановка (для совместимости)."""
        pass

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
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ComponentType
from core.models.enums.component_status import ComponentStatus
from core.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.safe_executor import SafeExecutor
from core.errors.failure_memory import FailureMemory

from core.agent.components.policy import RetryPolicy, AgentPolicy, PolicyViolationError
from core.agent.components.agent_metrics import AgentMetrics
from core.agent.behaviors.base import Decision, DecisionType
from core.utils.observation_formatter import (
    format_observation,
    smart_format_observation,
)
from core.agent.components.observer import Observer
from core.config.agent_config import AgentConfig
from core.agent.phases.decision_phase import DecisionPhase
from core.agent.phases.policy_check_phase import PolicyCheckPhase
from core.agent.phases.execution_phase import ExecutionPhase
from core.agent.phases.observation_phase import ObservationPhase
from core.agent.phases.context_update_phase import ContextUpdatePhase
from core.agent.phases.final_answer_phase import FinalAnswerPhase
from core.agent.phases.error_recovery_phase import ErrorRecoveryPhase
from core.agent.phases.validation_phase import ValidationPhase
from core.agent.agent_factory import AgentFactory


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

        log_session = application_context.infrastructure_context.log_session
        self.log = log_session.create_agent_logger(agent_id)
        self.narrative_log = log_session.get_agent_narrative_logger(agent_id)
        
        event_bus = application_context.infrastructure_context.event_bus
        
        # Используем фабрику для создания всех компонентов
        components = AgentFactory.create_components(
            application_context=application_context,
            agent_config=agent_config,
            log=self.log,
            event_bus=event_bus,
        )
        
        # Присваиваем компоненты
        self.executor = components.executor
        self.failure_memory = components.failure_memory
        self.policy = components.policy
        self.metrics = components.metrics
        self.observer = components.observer
        self.fallback_strategy = components.fallback_strategy
        self.safe_executor = components.safe_executor
        self.decision_phase = components.decision_phase
        self.policy_check_phase = components.policy_check_phase
        self.execution_phase = components.execution_phase
        self.observation_phase = components.observation_phase
        self.context_update_phase = components.context_update_phase
        self.final_answer_phase = components.final_answer_phase
        self.error_recovery_phase = components.error_recovery_phase
        self.validation_phase = components.validation_phase

        self._pattern = None

        # Session context — всегда новый, но с копией истории диалога
        from core.session_context.session_context import SessionContext

        self.session_context = SessionContext(
            session_id=str(uuid.uuid4()), agent_id=self.agent_id
        )
        self.session_context.set_goal(goal)

        # Сохраняем ссылку на глобальную историю для обратной записи
        self._shared_dialogue_history = dialogue_history

        # Копируем историю диалога если передана
        if dialogue_history is not None:
            self.session_context.copy_dialogue_from(dialogue_history)

        self.log.info(
            f"Агент {agent_id} запущен, цель: {goal[:50]}...",
            extra={"event_type": EventType.AGENT_START},
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

    async def _attempt_final_answer(
        self,
        executed_steps: int,
        stop_reason: Optional[str] = None,
    ) -> 'ExecutionResult':
        """
        Попытка сформировать финальный ответ в любой ситуации.
        
        Вызывается при нормальном завершении, по ошибке, по лимиту шагов или empty results.
        Генерирует ответ на основе собранных данных через FinalAnswerPhase.
        
        ARGS:
            executed_steps: Количество выполненных шагов
            stop_reason: Причина остановки (для логирования)
        
        RETURNS:
            ExecutionResult с финальным ответом или ошибкой
        """
        if stop_reason:
            self.log.warning(
                f"🏁 Попытка сформировать финальный ответ: {stop_reason}",
                extra={"event_type": EventType.AGENT_STOP}
            )
        else:
            self.log.info(
                "🏁 Формирование финального ответа...",
                extra={"event_type": EventType.AGENT_STOP}
            )
        
        # Если есть выполненные шаги — пробуем сгенерировать ответ
        if executed_steps > 0:
            try:
                final_result = await self.final_answer_phase.generate_fallback_answer(
                    session_context=self.session_context,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    goal=self.goal,
                    executed_steps=executed_steps,
                    sync_dialogue_callback=self._sync_dialogue_history_back,
                )
                if final_result:
                    if self.narrative_log:
                        answer_text = str(final_result.data)[:150] + "..." if final_result.data and len(str(final_result.data)) > 150 else str(final_result.data)
                        self.narrative_log.info(f"Финальный ответ сформирован: {answer_text}")
                    return final_result
            except Exception as e:
                self.log.error(f"Ошибка генерации fallback-ответа: {e}", exc_info=True)
        
        # Fallback: если шагов не было или генерация не удалась
        fallback_msg = stop_reason or f"Не удалось достичь цели за {self.max_steps} шагов."
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
        
        if self.narrative_log:
            self.narrative_log.info(f"Агент завершён (fallback): {fallback_msg}")
        
        return ExecutionResult.failure(fallback_msg)

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
        Используем уже инициализированный паттерн из ApplicationContext.
        """
        if self._pattern is not None:
            return

        components = self.application_context.components
        
        pattern = components.get(ComponentType.BEHAVIOR, "react_pattern")
        if pattern:
            self._pattern = pattern
            self.log.info(
                f"Pattern react_pattern взят из registry (уже инициализирован)",
                extra={"event_type": EventType.SYSTEM_INIT}
            )
            return

        event_bus = self.application_context.infrastructure_context.event_bus
        await event_bus.publish(
            EventType.WARNING,
            {"message": "⚠️ react_pattern не найден в registry, создаём новый"},
            session_id=self.session_context.session_id,
            agent_id=self.agent_id,
        )

        from core.components.component_factory import ComponentFactory
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        behavior_configs = getattr(
            self.application_context.config, "behavior_configs", {}
        )
        component_config = behavior_configs.get("react_pattern", ComponentConfig(
            name="react_pattern", variant_id="default"
        ))

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
            extra={"event_type": EventType.AGENT_START},
        )

        # Высокоуровневый лог
        if self.narrative_log:
            self.narrative_log.info(
                f"Запущен агент с целью: {self.goal}"
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
            extra={"event_type": EventType.SYSTEM_INIT},
        )

        # Цикл выполнения
        executed_steps = 0
        for step in range(self.max_steps):
            agent_state = self.session_context.agent_state

            # Высокоуровневый лог: начало шага
            if self.narrative_log:
                self.narrative_log.info(
                    f"Шаг {step + 1}/{self.max_steps}: начало..."
                )
            
            # Проверка условий остановки через Policy (Fail-Fast) - ДЕЛЕГИРОВАНО STEP
            should_stop, stop_reason = self.policy_check_phase.check_loop_conditions(
                session_context=self.session_context,
                metrics=self.metrics,
                step_number=step,
                agent_config=self.agent_config,
            )
            if should_stop:
                self.log.warning(
                    f"🛑 Остановка: {stop_reason}",
                    extra={"event_type": EventType.AGENT_STOP}
                )
                await event_bus.publish(
                    EventType.DEBUG,
                    {"event": "AGENT_STOP_METRICS", "reason": stop_reason, "metrics": self.metrics.to_dict()},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id
                )
                # ВСЕГДА пытаемся сформировать финальный ответ
                return await self._attempt_final_answer(
                    executed_steps=executed_steps,
                    stop_reason=stop_reason or f"Stopped: {stop_reason}"
                )
            
            # Pattern решает - ДЕЛЕГИРОВАНО STEP
            decision = await self.decision_phase.execute(
                pattern=pattern,
                session_context=self.session_context,
                available_capabilities=available_caps,
                step_number=step + 1,
            )

            # Высокоуровневый лог: принято решение
            if self.narrative_log:
                if decision.type == DecisionType.ACT:
                    params_str = ", ".join(
                        f"{k}={v}" for k, v in (decision.parameters or {}).items()
                    )
                    self.narrative_log.info(
                        f"Принято решение: {decision.action}({params_str}) — {decision.reasoning}"
                    )
                elif decision.type == DecisionType.FINISH:
                    self.narrative_log.info(
                        f"Принято решение: завершить — {decision.reasoning}"
                    )
                elif decision.type == DecisionType.FAIL:
                    self.narrative_log.info(
                        f"Принято решение: ошибка — {decision.error}"
                    )

            # Pattern решил FINISH? - ДЕЛЕГИРОВАНО STEP
            if decision.type == DecisionType.FINISH:
                final_result = await self.final_answer_phase.generate_final_answer(
                    session_context=self.session_context,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    goal=self.goal,
                    decision_reasoning=decision.reasoning,
                    sync_dialogue_callback=self._sync_dialogue_history_back,
                )

                # Высокоуровневый лог: финальный ответ
                if self.narrative_log:
                    self.narrative_log.info("Генерация финального ответа...")

                if final_result:
                    # Высокоуровневый лог: финальный ответ получен
                    if self.narrative_log:
                        answer_text = str(final_result.data)[:150] + "..." if final_result.data and len(str(final_result.data)) > 150 else str(final_result.data)
                        self.narrative_log.info(f"Финальный ответ: {answer_text}")
                    return final_result
                
                # Fallback если генерация не удалась
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=decision.reasoning or "Завершено",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                result = decision.data or ExecutionResult.success(
                    data=decision.reasoning
                )
                if self.narrative_log:
                    self.narrative_log.info("Агент завершён успешно")
                return result

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                self.log.error(
                    f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    extra={"event_type": EventType.AGENT_STOP},
                )
                # ВСЕГДА пытаемся сформировать финальный ответ
                return await self._attempt_final_answer(
                    executed_steps=executed_steps,
                    stop_reason=decision.error or "Unknown error"
                )

            # Pattern решил ACT? - ДЕЛЕГИРОВАНО STEP
            if decision.type == DecisionType.ACT:
                # Policy проверка через evaluate() с Fail-Fast - ДЕЛЕГИРОВАНО STEP
                try:
                    self.policy_check_phase.validate_action(
                        action_name=decision.action or "",
                        metrics=self.metrics,
                        session_context=self.session_context,
                        parameters=decision.parameters or {},
                    )
                except PolicyViolationError as e:
                    policy_msg = self.policy_check_phase.handle_violation(
                        error=e,
                        decision_action=decision.action,
                        step_number=step + 1,
                        session_context=self.session_context,
                    )
                    
                    await event_bus.publish(
                        EventType.ERROR_OCCURRED,
                        {
                            "reason": policy_msg,
                            "action": decision.action,
                            "step": step + 1,
                        },
                        session_id=self.session_context.session_id,
                        agent_id=self.agent_id,
                    )
                    executed_steps += 1
                    continue

                # Валидация инструмента и параметров через ValidationPhase
                action_name = decision.action or ""
                
                if available_caps:
                    is_valid, validation_result = self.validation_phase.validate_action(
                        action_name=action_name,
                        parameters=decision.parameters or {},
                        available_capabilities=available_caps,
                    )
                    
                    if not is_valid and validation_result:
                        # Валидация не прошла — блокируем и отправляем ошибку LLM
                        error_msg = validation_result.data.get("message", "Ошибка валидации") if validation_result.data else "Ошибка валидации"
                        
                        self.log.warning(
                            f"⚠️ {error_msg}",
                            extra={"event_type": EventType.WARNING},
                        )
                        
                        # Регистрируем ошибку в состоянии
                        self.session_context.agent_state.add_step(
                            action_name=action_name,
                            status="validation_failed",
                            parameters=decision.parameters or {},
                            observation={"status": "error", "message": error_msg}
                        )
                        
                        # Создаём результат ошибки
                        result = ExecutionResult(
                            status=ExecutionStatus.FAILED,
                            error=ValueError(error_msg),
                            data=validation_result.data,
                        )
                        
                        # observation_phase — чтобы LLM увидел ошибку
                        observation = await self.observation_phase.analyze(
                            result=result,
                            decision_action=action_name,
                            decision_parameters=decision.parameters or {},
                            session_context=self.session_context,
                            step_number=step + 1,
                        )
                        
                        # Сохраняем ошибку в контекст
                        await self.context_update_phase.save_and_register(
                            result=result,
                            observation=observation,
                            decision_action=action_name,
                            decision_parameters=decision.parameters or {},
                            session_context=self.session_context,
                            executed_steps=executed_steps,
                            decision_reasoning=f"Ошибка: {error_msg}",
                            error_recovery_handler=self.error_recovery_phase,
                        )
                        
                        executed_steps += 1
                        continue

                # Выполнение действия - ДЕЛЕГИРОВАНО STEP
                result = await self.execution_phase.execute(
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    session_context=self.session_context,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    step_number=step + 1,
                )

                # Высокоуровневый лог: выполнение завершено
                if self.narrative_log:
                    status_str = "успех" if result.status.value == "completed" else result.status.value
                    self.narrative_log.info(
                        f"Результат: {decision.action} — {status_str}"
                    )

                # ============================================
                # OBSERVATION PHASE (единая точка истинности) - СНАЧАЛА
                # ============================================
                
                observation = await self.observation_phase.analyze(
                    result=result,
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    session_context=self.session_context,
                    step_number=executed_steps + 1,
                )

                # Высокоуровневый лог: наблюдение
                if self.narrative_log and observation:
                    obs_text = observation.insight[:200] + "..." if len(observation.insight) > 200 else observation.insight
                    self.narrative_log.info(
                        f"Наблюдение: {obs_text}"
                    )

                # Сохранение данных результата и регистрация шага - ПОТОМ
                observation_item_ids = await self.context_update_phase.save_and_register(
                    result=result,
                    observation=observation,
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    session_context=self.session_context,
                    executed_steps=executed_steps,
                    decision_reasoning=decision.reasoning,
                    error_recovery_handler=self.error_recovery_phase,
                )

                # Публикация событий
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
                        "observation": self.session_context.agent_state.last_observation,
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

                executed_steps += 1

            # Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                await event_bus.publish(
                    EventType.INFO,
                    {"message": f"🔄 SWITCH STRATEGY: {decision.next_pattern}"},
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                )
                # Switch pattern by re-initializing
                self._pattern = None
                pattern = await self._get_pattern()

        # ─────────────────────────────────────────────────────────────
        # ЦИКЛ ЗАВЕРШЁН: ВСЕГДА пытаемся сформировать финальный ответ
        # ─────────────────────────────────────────────────────────────
        return await self._attempt_final_answer(
            executed_steps=executed_steps,
            stop_reason=f"Лимит шагов ({self.max_steps}) исчерпан"
        )

    async def _get_available_capabilities(self):
        """Получить доступные capability с учётом фильтрации."""
        if hasattr(self.application_context, "get_all_skills"):
            all_caps = self.application_context.get_all_skills()
        elif hasattr(self.application_context, "get_all_capabilities"):
            # Simple filter config - no special filtering needed
            all_caps = await self.application_context.get_all_capabilities(
                include_hidden=False,
                component_types=["skill"],
            )
        else:
            return []

        # Фильтрация по флагу visiable в самом capability
        return [cap for cap in all_caps if getattr(cap, "visiable", True)]

    async def stop(self):
        """Остановка (для совместимости)."""
        pass

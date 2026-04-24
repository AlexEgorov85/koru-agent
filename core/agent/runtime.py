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
from core.models.enums.component_status import ComponentStatus
from core.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.safe_executor import SafeExecutor
from core.errors.failure_memory import FailureMemory
from core.agent.components.observation_signal import ObservationSignalService
from core.agent.components.policy import RetryPolicy, AgentPolicy, PolicyViolationError
from core.agent.components.agent_metrics import AgentMetrics
from core.agent.behaviors.base import Decision, DecisionType
from core.utils.observation_formatter import (
    format_observation,
    smart_format_observation,
)
from core.components.skills.utils.observation_policy import ObservationPolicy
from core.agent.components.observer import Observer
from core.config.agent_config import AgentConfig
from core.agent.phases.decision_phase import DecisionPhase
from core.agent.phases.policy_check_phase import PolicyCheckPhase
from core.agent.phases.execution_phase import ExecutionPhase
from core.agent.phases.observer_phase import ObserverPhase
from core.agent.phases.context_update_phase import ContextUpdatePhase
from core.agent.phases.final_answer_phase import FinalAnswerPhase
from core.agent.phases.error_recovery_phase import ErrorRecoveryPhase


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
        
        # Step orchestrators для делегирования ответственности (Фаза 2)
        event_bus = application_context.infrastructure_context.event_bus
        
        self.decision_phase = DecisionPhase(
            log=self.log,
            event_bus=event_bus,
        )
        
        self.policy_check_phase = PolicyCheckPhase(
            policy=self.policy,
            log=self.log,
            event_bus=event_bus,
        )
        
        self.execution_phase = ExecutionPhase(
            safe_executor=self.safe_executor,
            log=self.log,
            event_bus=event_bus,
            agent_config=agent_config,
        )
        
        self.observer_phase = ObserverPhase(
            observer=self.observer,
            metrics=self.metrics,
            policy=self.policy,
            log=self.log,
            event_bus=event_bus,
        )
        
        # SQL diagnostic service для error recovery
        sql_diagnostic = None
        try:
            from core.agent.components.sql_diagnostic import SQLDiagnosticService
            sql_diagnostic = SQLDiagnosticService(application_context)
        except Exception:
            pass  # Optional component
        
        self.error_recovery_phase = ErrorRecoveryPhase(
            sql_diagnostic_service=sql_diagnostic,
            log=self.log,
        )
        
        self.context_update_phase = ContextUpdatePhase(
            log=self.log,
            event_bus=event_bus,
            error_recovery_handler=self.error_recovery_phase,
        )
        
        self.final_answer_phase = FinalAnswerPhase(
            safe_executor=self.safe_executor,
            agent_config=agent_config,
            log=self.log,
            event_bus=event_bus,
        )

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

        # Логгер агента (1 сессия = 1 файл)
        log_session = application_context.infrastructure_context.log_session
        self.log = log_session.create_agent_logger(agent_id)
        
        # Передаём логгер в error_recovery_phase
        self.error_recovery_phase.log = self.log
        
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
            extra={"event_type": EventType.AGENT_START},
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
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=f"Остановлено: {stop_reason}",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                return ExecutionResult.failure(f"Stopped: {stop_reason}")
            
            # Pattern решает - ДЕЛЕГИРОВАНО STEP
            decision = await self.decision_phase.execute(
                pattern=pattern,
                session_context=self.session_context,
                available_capabilities=available_caps,
                step_number=step + 1,
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
                
                if final_result:
                    return final_result
                
                # Fallback если генерация не удалась
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=decision.reasoning or "Завершено",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                return decision.data or ExecutionResult.success(
                    data=decision.reasoning
                )

            # Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                self.log.error(
                    f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    extra={"event_type": EventType.AGENT_STOP},
                )
                # Сохраняем диалог даже при ошибке
                self.session_context.commit_turn(
                    user_query=self.goal,
                    assistant_response=f"Ошибка выполнения: {decision.error or 'Неизвестная ошибка'}",
                    tools_used=[],
                )
                self._sync_dialogue_history_back()
                return ExecutionResult.failure(decision.error or "Unknown error")

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

                # Выполнение действия - ДЕЛЕГИРОВАНО STEP
                result = await self.execution_phase.execute(
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    session_context=self.session_context,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    step_number=step + 1,
                )

                # Сохранение данных результата и регистрация шага - ДЕЛЕГИРОВАНО STEP
                observation_item_ids = await self.context_update_phase.save_and_register(
                    result=result,
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    session_context=self.session_context,
                    executed_steps=executed_steps,
                    decision_reasoning=decision.reasoning,
                    error_recovery_handler=self.error_recovery_phase,
                )

                # ============================================
                # OBSERVER + METRICS (Фаза 1) - ДЕЛЕГИРОВАНО STEP
                # ============================================
                
                observation = await self.observer_phase.analyze(
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    result_data=result.data if hasattr(result, 'data') else result,
                    error_msg=result.error if result.status == ExecutionStatus.FAILED else None,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    step_number=executed_steps + 1,
                )

                # Запись шага в agent_state - ДЕЛЕГИРОВАНО STEP
                self.context_update_phase.update_agent_state(
                    session_context=self.session_context,
                    executed_steps=executed_steps,
                    decision_action=decision.action,
                    decision_parameters=decision.parameters or {},
                    result_status=result.status,
                    observation_signal=self.observation_signal_service.build_signal(
                        result=result,
                        action_name=decision.action,
                        parameters=decision.parameters or {},
                    ),
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
            
            # Делегируем обработку FinalAnswerHandler (Фаза 2)
            try:
                final_result = await self.final_answer_handler.generate_fallback_answer(
                    session_context=self.session_context,
                    session_id=self.session_context.session_id,
                    agent_id=self.agent_id,
                    goal=self.goal,
                    executed_steps=executed_steps,
                    sync_dialogue_callback=self._sync_dialogue_history_back,
                )
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

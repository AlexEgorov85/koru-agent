"""
Runtime — цикл выполнения агента с Observer и Metrics.

АРХИТЕКТУРА (Этап 10 + v2.0):
- Pattern.decide() → Policy.check() → Executor.execute() → Observer.analyze() → Metrics.update()
- Reflection validation в Pattern
- Policy проверки на повторы и empty_loop
- Observer LLM-анализ результатов
- AgentMetrics для отслеживания качества

РЕФАКТОРИНГ:
- Step Execution Pipeline (handlers)
- Pluggable Termination Strategy
- Observation Recording Strategy
"""

import uuid
from typing import Any, Optional, List

from core.application_context.application_context import ApplicationContext
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.component_status import ComponentStatus
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.agent.components.safe_executor import SafeExecutor
from core.agent.components.failure_memory import FailureMemory
from core.agent.components.observation_signal import ObservationSignalService
from core.agent.components.policy import RetryPolicy, AgentPolicy
from core.agent.components.agent_metrics import AgentMetrics
from core.agent.behaviors.base import DecisionType
from core.agent.observation_formatter import (
    format_observation,
    smart_format_observation,
)
from core.components.skills.utils.observation_policy import ObservationPolicy
from core.agent.components.observer import Observer

# Новые импорты для рефакторинга
from core.agent.runtime.pipeline import ExecutionPipeline
from core.agent.runtime.handlers.decision import DecisionHandler
from core.agent.runtime.handlers.policy import PolicyCheckHandler
from core.agent.runtime.handlers.action import ActionHandler
from core.agent.runtime.strategies.termination import (
    ITerminationStrategy,
    DefaultTerminationStrategy,
)
from core.agent.runtime.recorders.observation import (
    IObservationRecorder,
    DefaultObservationRecorder,
)


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
        termination_strategy: Optional[ITerminationStrategy] = None,
        observation_recorder: Optional[IObservationRecorder] = None,
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

        # Инициализация стратегий (рефакторинг)
        self.termination_strategy = termination_strategy or DefaultTerminationStrategy()
        
        # Инициализация рекордера наблюдений (рефакторинг)
        self.observation_recorder = observation_recorder or DefaultObservationRecorder(
            observer=self.observer,
            metrics=self.metrics,
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

        from core.agent.components.component_factory import ComponentFactory
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
        Цикл выполнения с использованием конвейера обработчиков.
        
        Архитектура:
        1. ExecutionPipeline выполняет цепочку handlers
        2. TerminationStrategy обрабатывает завершение цикла
        3. ObservationRecorder записывает результаты
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

        # Инициализируем конвейер обработчиков
        step_pipeline = ExecutionPipeline([
            DecisionHandler(pattern=pattern, available_capabilities=available_caps),
            PolicyCheckHandler(policy=self.policy),
            ActionHandler(
                safe_executor=self.safe_executor,
                event_bus=event_bus,
                session_id=self.session_context.session_id,
                agent_id=self.agent_id,
                log=self.log,
            ),
        ])

        # Цикл выполнения
        executed_steps = 0
        for step in range(self.max_steps):
            agent_state = self.session_context.agent_state
            
            # Проверка условий остановки по state
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

            # Выполняем конвейер обработчиков
            result = await step_pipeline.run(self.session_context)
            
            # Если конвейер вернул результат (FINISH/FAIL), завершаем цикл
            if result is not None:
                self._sync_dialogue_history_back()
                return result
            
            # Получаем решение из контекста для пост-обработки
            decision = getattr(self.session_context.step_context, "_current_decision", None)
            
            # Если решение есть и это ACT, записываем наблюдение
            if decision and decision.type == DecisionType.ACT:
                # Получаем результат из контекста выполнения
                exec_result = getattr(self.session_context.step_context, "_last_execution_result", None)
                
                if exec_result:
                    # Записываем наблюдение через рекордер
                    await self.observation_recorder.record(
                        result=exec_result,
                        decision=decision,
                        context=self.session_context,
                    )
                    
                    executed_steps += 1
                    
                    # Публикуем дополнительные события
                    await event_bus.publish(
                        EventType.INFO,
                        {
                            "message": f"✅ Executor завершил: status={exec_result.status.value}"
                            + (f"\n   ❌ Error: {exec_result.error}" if exec_result.error else "")
                        },
                        session_id=self.session_context.session_id,
                        agent_id=self.agent_id,
                    )

        # Max steps exceeded — используем стратегию завершения
        return await self.termination_strategy.handle_end_of_cycle(
            self.session_context,
            self.safe_executor,
        )

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
                from core.agent.components.sql_recovery import SQLRecoveryAnalyzer
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

    async def stop(self):
        """Остановка (для совместимости)."""
        pass

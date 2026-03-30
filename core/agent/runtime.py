"""
Основной класс выполнения агента - runtime цикл рассуждений для новой архитектуры.

СОДЕРЖИТ:
- Цикл рассуждений (reasoning loop)
- Управление стратегией выполнения
- Обработку действий и результатов
- Интеграцию с инфраструктурными сервисами
"""
import asyncio
import time
import logging
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
from typing import Any, Dict, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

from core.agent.components.action_executor import ActionExecutor
from core.agent.components.behavior_manager import BehaviorManager
from core.agent.components.failure_memory import FailureMemory
from core.agent.components.policy import AgentPolicy
from core.agent.components.progress import ProgressScorer
from core.agent.components.safe_executor import SafeExecutor
from core.agent.components.state import AgentState
from core.application_context.application_context import ApplicationContext
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus, ErrorCategory, RetryDecision
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.types.retry_policy import ExecutionErrorInfo

from core.agent.behaviors.base import BehaviorDecisionType, BehaviorDecision
from core.models.errors import AgentStuckError, InfrastructureError

# Определяем ProgressMetrics локально
from dataclasses import dataclass, field
from typing import Dict, Optional

from core.security.user_context import UserContext


@dataclass
class ProgressMetrics:
    """Класс для отслеживания метрик прогресса"""
    step: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    no_progress_steps: int = 0
    strategy_switches: int = 0
    plan_corrections: int = 0
    strategy_effectiveness: Dict[str, float] = field(default_factory=dict)
    last_strategy_switch_step: Optional[int] = None
    strategy_confidence: float = 1.0

    def update_strategy_effectiveness(self, strategy_name: str, success: bool):
        """Обновление метрик эффективности стратегии"""
        if strategy_name not in self.strategy_effectiveness:
            self.strategy_effectiveness[strategy_name] = 0.5

        # Экспоненциальное сглаживание
        alpha = 0.3
        current = self.strategy_effectiveness[strategy_name]
        self.strategy_effectiveness[strategy_name] = (
            alpha * (1.0 if success else 0.0) + (1 - alpha) * current
        )

    def get_state_metrics(self) -> Dict[str, Any]:
        """Получить словарь с текущими метриками состояния"""
        return {
            "step": self.step,
            "error_count": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "no_progress_steps": self.no_progress_steps,
            "strategy_switches": self.strategy_switches,
            "plan_corrections": self.plan_corrections,
            "strategy_effectiveness": self.strategy_effectiveness.copy(),
            "last_strategy_switch_step": self.last_strategy_switch_step,
            "strategy_confidence": self.strategy_confidence
        }


class AgentRuntime:
    """Основной класс выполнения агента - runtime цикл рассуждений."""

    def __init__(
        self,
        application_context: ApplicationContext,
        goal: str,
        policy: AgentPolicy = None,
        max_steps: int = 10,
        correlation_id: Optional[str] = None,
        user_context: Optional['UserContext'] = None
    ):
        """
        Инициализация runtime агента.

        ПАРАМЕТРЫ:
        - application_context: Прикладной контекст агента
        - goal: Цель выполнения агента
        - policy: Политика поведения агента
        - max_steps: Максимальное количество шагов
        - correlation_id: ID корреляции для трассировки
        - user_context: Контекст пользователя
        """
        self.application_context = application_context
        self.goal = goal
        self._running = False
        self._current_step = 0
        self._max_steps = max_steps
        self._result: Optional[ExecutionResult] = None
        self._final_answer_result: Optional[ExecutionResult] = None  # ← Результат final_answer.generate
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.user_context = user_context

        # === ПРОВЕРКА ГОТОВНОСТИ CONTEXT ===
        if not hasattr(application_context, 'is_ready') or not application_context.is_ready:
            raise RuntimeError(
                f"ApplicationContext not initialized (state={getattr(application_context, '_state', 'unknown')}). "
                f"Call await application_context.initialize() first."
            )
        
        if not hasattr(application_context.infrastructure_context, 'is_ready') or not application_context.infrastructure_context.is_ready:
            raise RuntimeError(
                "InfrastructureContext not initialized. "
                "Call await infrastructure_context.initialize() first."
            )
        # ===================================

        # Инициализация компонентов
        self.policy = policy or AgentPolicy()  # ← Единая политика агента
        self.state = AgentState()
        self.progress = ProgressScorer()

        # В новой архитектуре ApplicationContext сам является системным контекстом
        # так как наследуется от BaseSystemContext
        self.executor = ActionExecutor(application_context)
        
        # ← НОВОЕ: SafeExecutor с обработкой ошибок и FailureMemory
        self.failure_memory = FailureMemory(max_age_minutes=30)
        self.safe_executor = SafeExecutor(
            executor=self.executor,
            failure_memory=self.failure_memory,
            max_retries=self.policy.max_retries,
            base_delay=self.policy.base_delay,
            max_delay=self.policy.max_delay
        )

        # Инициализация менеджера поведения с executor и failure_memory
        self.behavior_manager = BehaviorManager(
            application_context=application_context,
            executor=self.executor,  # ← Передаём executor
            failure_memory=self.failure_memory  # ← НОВОЕ: Передаём failure_memory
        )
        self.progress_metrics = ProgressMetrics()

        # Создаем session_context как атрибут агента (не в application_context!)
        from core.session_context.session_context import SessionContext
        self.session_context = SessionContext(session_id=str(uuid.uuid4()))
        self.session_context.set_goal(goal)
        print(f"[DEBUG] Agent created with NEW session_context: {self.session_context.session_id}, goal: {goal[:50]}")

        # Настройка логирования через EventBus (стандартное logging НЕ используется)
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # Отладка: проверяем что доступно
        has_app_ctx = hasattr(self, 'application_context') and self.application_context
        has_infra = has_app_ctx and hasattr(self.application_context, 'infrastructure_context')
        has_event_bus = has_infra and getattr(self.application_context.infrastructure_context, 'event_bus', None)

        if has_app_ctx and has_infra and has_event_bus:
            self.event_bus_logger = EventBusLogger(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                event_bus=self.application_context.infrastructure_context.event_bus,
                session_id="system",
                agent_id="system",
                component=self.__class__.__name__
            )
        # else: event_bus_logger останется None

    async def run(self, goal: str = None, max_steps: Optional[int] = None) -> ExecutionResult:
        """
        Запуск выполнения агента через async цикл (_run_async).

        ПАРАМЕТРЫ:
        - goal: Цель агента (опционально)
        - max_steps: Максимальное количество шагов (опционально)

        ВОЗВРАЩАЕТ:
        - ExecutionResult: Результат выполнения
        """
        return await self._run_async(goal, max_steps)

    async def _execute_single_step_internal(self, decision, available_caps) -> Any:
        """
        Выполнение одного шага рассуждений с переданным decision.

        Используется в run() для избежания дублирования вызова generate_next_decision.
        """
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        logger.debug(f"\n🔵 [_execute_single_step_internal] НАЧАЛО: step={self._current_step}, decision.action={decision.action.value}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        logger.debug(f"🔵 [_execute_single_step_internal] decision.capability_name={getattr(decision, 'capability_name', 'N/A')}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.debug(f"Выполнение шага {self._current_step + 1}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.debug(f"RUNTIME: Получено {len(available_caps)} доступных capability: {[c.name for c in available_caps]}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info(f"=== DECISION ПОЛУЧЕН ===")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info(f"decision.action: {decision.action}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info(f"decision.capability_name: {getattr(decision, 'capability_name', 'N/A')}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Публикуем событие progress для отображения шага
        if self.event_bus_logger and decision.action == BehaviorDecisionType.ACT:
            step_num = self._current_step + 1
            cap_name = getattr(decision, 'capability_name', 'unknown')
            await self.event_bus_logger.user_progress(
                message=f"ШАГ {step_num}: act → {cap_name}",
                step_number=step_num,
                action=decision.action.value,
                capability_name=cap_name
            )

        # Запись решения паттерна поведения
        if decision:
            self.session_context.record_decision(
                decision.action.value,
                reasoning=decision.reason
            )

        # === SAFEGUARD: ЗАПРЕТ STOP НА ПЕРВОМ ШАГЕ ===
        # Предотвращает преждевременную остановку агента
        if (
            self._current_step == 0
            and decision.action == BehaviorDecisionType.STOP
        ):
            if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.warning(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    "⚠️ Agent attempted to stop on first step - это обычно ошибка LLM или пустой список capabilities"
                )
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning("\n⚠️ SAFEGUARD TRIGGERED: Agent attempted to stop on step 0")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning(f"   Goal: {self.goal[:100]}...")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning(f"   Available capabilities: {len(available_caps)}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning("   Possible causes:")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning("   1. LLM incorrectly parsed the goal as already achieved")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning("   2. No capabilities were available to the LLM")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning("   3. Prompt template needs adjustment\n")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔴 [_execute_single_step_internal] Возврат SWITCH (safeguard)")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="fallback_pattern",
                reason="stop_on_first_step"
            )

        if decision.action == BehaviorDecisionType.STOP:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] decision.action=STOP")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.state.finished = True
            # Регистрируем финальное решение
            self.session_context.record_decision(
                decision_data="STOP",
                reasoning="goal_achieved"
            )
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔴 [_execute_single_step_internal] Возврат STOP decision")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return decision

        # Публикуем событие рассуждения агента для вывода пользователю
        if decision.action == BehaviorDecisionType.ACT and self.event_bus_logger:
            reasoning_text = decision.reason or "Принято решение о действии"
            await self.event_bus_logger.agent_thinking(
                reasoning=reasoning_text,
                capability_name=decision.capability_name or "unknown",
                parameters=decision.parameters,
                decision_action="act",
                step_number=self._current_step + 1
            )

        if decision.action == BehaviorDecisionType.ACT:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] decision.action=ACT")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            # ПРОВЕРКА: capability_name должен быть указан
            if not decision.capability_name:
                if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.error(f"ACT decision но capability_name не указан!")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.state.register_error()

                # ПРОВЕРКА: Превышен ли лимит ошибок
                if self.policy.should_fallback(self.state):
                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.error(
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            f"Превышен лимит ошибок ({self.state.error_count}/{self.policy.max_errors}). "
                            f"Агент переходит в режим завершения."
                        )
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        data=None,
                        error=f"Превышен лимит ошибок: {self.state.error_count}/{self.policy.max_errors}",
                        metadata={
                            "error_count": self.state.error_count,
                            "max_errors": self.policy.max_errors,
                            "failed_at_step": self._current_step + 1
                        }
                    )

# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔴 [_execute_single_step_internal] Возврат None (capability_name не указан)")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] Поиск capability в application_context...")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] self.event_bus_logger={self.event_bus_logger is not None}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] hasattr(application_context, 'components')={hasattr(self.application_context, 'components')}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            
            if hasattr(self.application_context, 'components'):
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [_execute_single_step_internal] application_context.components доступен")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                # Пытаемся получить через components (универсальный метод)
                # Разбиваем capability_name на skill/tool name и capability name
                parts = decision.capability_name.split('.')
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [_execute_single_step_internal] parts={parts}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                if len(parts) >= 2:
                    component_name = parts[0]
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    logger.debug(f"🔵 [_execute_single_step_internal] component_name={component_name}")
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    from core.models.enums.common_enums import ComponentType
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    logger.debug(f"🔵 [_execute_single_step_internal] Поиск в ComponentType.SKILL...")
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    comp = self.application_context.components.get(ComponentType.SKILL, component_name)
                    if comp:
                        capability = comp
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        logger.debug(f"🔵 [_execute_single_step_internal] ✅ Найден компонент SKILL.{component_name}")
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    
                    if not capability:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        logger.debug(f"🔵 [_execute_single_step_internal] Поиск в ComponentType.TOOL...")
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        comp = self.application_context.components.get(ComponentType.TOOL, component_name)
                        if comp:
                            capability = comp
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            logger.debug(f"🔵 [_execute_single_step_internal] ✅ Найден компонент TOOL.{component_name}")
                              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    
                    if not capability:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        logger.debug(f"🔵 [_execute_single_step_internal] Поиск в ComponentType.SERVICE...")
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        comp = self.application_context.components.get(ComponentType.SERVICE, component_name)
                        if comp:
                            capability = comp
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            logger.debug(f"🔵 [_execute_single_step_internal] ✅ Найден компонент SERVICE.{component_name}")
                              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔴 [_execute_single_step_internal] capability_name не содержит '.' : {decision.capability_name}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        else:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔴 [_execute_single_step_internal] application_context.components НЕ доступен")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Fallback: проверяем специальные методы если components не сработал
        if not capability:
            if hasattr(self.application_context, 'get_skill'):
                # Пытаемся получить как skill (для совместимости)
                skill_name = decision.capability_name.split('.')[0]
                capability = self.application_context.components.get(ComponentType.SKILL, skill_name)
                if capability:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    logger.debug(f"🔵 [_execute_single_step_internal] ✅ Найден skill: {skill_name}")
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        logger.debug(f"🔵 [_execute_single_step_internal] capability found: {capability is not None}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        if not capability:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.warning(f"🔴 [_execute_single_step_internal] Capability '{decision.capability_name}' не найдена")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.state.register_error()

            # ПРОВЕРКА: Превышен ли лимит ошибок
            if self.policy.should_fallback(self.state):
                if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.error(
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        f"Превышен лимит ошибок ({self.state.error_count}/{self.policy.max_errors}). "
                        f"Агент переходит в режим завершения."
                    )
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    data=None,
                    error=f"Превышен лимит ошибок: {self.state.error_count}/{self.policy.max_errors}",
                    metadata={
                        "error_count": self.state.error_count,
                        "max_errors": self.policy.max_errors,
                        "failed_at_step": self._current_step + 1
                    }
                )

            return None

        # Выполняем capability
        try:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] 🚀 Запуск выполнения {decision.capability_name}...")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # Публикуем события для вывода пользователю
            if self.event_bus_logger:
                await self.event_bus_logger.tool_call(
                    capability_name=decision.capability_name,
                    parameters=decision.parameters,
                    step_number=self._current_step + 1
                )

            # component уже найден (SKILL.book_library или TOOL.book_library)
            # capability — это компонент, а cap_obj — объект Capability для валидации
            # ← НОВОЕ: Выполнение через SafeExecutor с обработкой ошибок
            execution_result = await self.safe_executor.execute(
                capability_name=decision.capability_name,
                parameters=decision.parameters,
                context=self.session_context
            )

            # Публикуем результат выполнения
            if self.event_bus_logger:
                result_status = "completed" if execution_result.status == ExecutionStatus.COMPLETED else "failed"
                result_data = None
                if hasattr(execution_result, 'result'):
                    result_data = execution_result.result
                elif hasattr(execution_result, 'data'):
                    result_data = execution_result.data
                
                await self.event_bus_logger.tool_result(
                    capability_name=decision.capability_name,
                    result=result_data,
                    status=result_status,
                    has_result=result_data is not None,
                    step_number=self._current_step + 1
                )

# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] ✅ {decision.capability_name} выполнен успешно")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [_execute_single_step_internal] 📊 Результат: {execution_result}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # ПРОВЕРКА: Если decision требует LLM, проверяем что он был вызван
            if getattr(decision, 'requires_llm', False):
                # ExecutionResult может иметь llm_called флаг
                if hasattr(execution_result, 'llm_called') and not execution_result.llm_called:
                    raise InfrastructureError(
                        f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                    )

            # Обновление контекста выполнения
            if self.session_context:
                action_id = self.session_context.record_action({
                    "step": self._current_step + 1,
                    "action": decision.capability_name,
                    "result": execution_result,
                    "timestamp": datetime.now().isoformat()
                }, step_number=self._current_step + 1)

                if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.debug(f"✅ Action записан с ID: {action_id}")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                # КРИТИЧНО: Записываем observation из результата выполнения
                # Навыки не записывают observation явно, делаем это в runtime
                # ИСПРАВЛЕНО: записываем observation даже при ошибке
                observation_id = None
                obs_data = None
                step_status = execution_result.status
                step_summary = None
                
                try:
                    if execution_result.status == ExecutionStatus.COMPLETED:
                        # Успех — записываем результат
                        if hasattr(execution_result, 'result') and execution_result.result:
                            # Если result это dict, используем его
                            if isinstance(execution_result.result, dict):
                                obs_data = execution_result.result
                            elif hasattr(execution_result.result, 'model_dump'):
                                # Pydantic v2 модель → dict
                                obs_data = execution_result.result.model_dump()
                            elif hasattr(execution_result.result, 'dict'):
                                # Pydantic v1 модель → dict
                                obs_data = execution_result.result.dict()
                            else:
                                # Иначе оборачиваем в dict
                                obs_data = {"result": execution_result.result}
                        step_summary = f"Выполнено: {decision.capability_name}"
                        self.state.register_progress(True)  # прогресс есть
                    else:
                        # Ошибка — записываем информацию об ошибке
                        obs_data = {
                            "error": execution_result.error,
                            "error_type": execution_result.metadata.get("error_type", "unknown") if execution_result.metadata else "unknown",
                            "status": execution_result.status.value
                        }
                        step_summary = f"Ошибка при выполнении {decision.capability_name}: {execution_result.error or 'неизвестная ошибка'}"
                        self.state.register_error()  # увеличиваем счётчик ошибок

                    if obs_data:
                        observation_id = self.session_context.record_observation(
                            observation_data=obs_data,
                            source=decision.capability_name,
                            step_number=self._current_step + 1
                        )
                        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            await self.event_bus_logger.debug(f"✅ Observation записана с ID: {observation_id}")
                              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                except Exception as e:
                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.warning(f"⚠️ Не удалось записать observation: {e}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                # КРИТИЧНО: Записываем STEP чтобы update_summary() обновился!
                # Без этого get_summary() возвращает одинаковые last_steps
                # и ProgressScorer.evaluate() возвращает False
                # ИСПРАВЛЕНО: record_step -> register_step (правильное имя метода)

                # Извлекаем observation_id из metadata если есть
                observation_item_ids = []
                if observation_id:
                    observation_item_ids = [observation_id]
                elif hasattr(execution_result, 'metadata') and execution_result.metadata:
                    obs_id = execution_result.metadata.get('observation_id')
                    if obs_id:
                        observation_item_ids = [obs_id]

                try:
                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.info(f"🔵 Вызов register_step: step={self._current_step + 1}, capability={decision.capability_name}, obs_ids={observation_item_ids}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.info(f"🔵 step_context до register_step: count={self.session_context.step_context.count()}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                    self.session_context.register_step(
                        step_number=self._current_step + 1,
                        capability_name=decision.capability_name,
                        skill_name=decision.capability_name.split('.')[0] if '.' in decision.capability_name else decision.capability_name,
                        action_item_id=action_id,
                        observation_item_ids=observation_item_ids,
                        summary=step_summary,
                        status=step_status  # ← передаём ExecutionStatus вместо строки
                    )

                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.info(f"✅ Step {self._current_step + 1} зарегистрирован в step_context")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.info(f"✅ step_context.count() после register_step = {self.session_context.step_context.count()}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                except Exception as e:
                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.error(f"❌ Ошибка register_step: {e}")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                # Оценка прогресса и обновление состояния
                progressed = self.progress.evaluate(self.session_context)
                self.state.register_progress(progressed)

                # КРИТИЧНО: Помечаем результат final_answer.generate как финальный
                if decision.capability_name == "final_answer.generate":
                    if execution_result.metadata is None:
                        execution_result.metadata = {}
                    execution_result.metadata['is_final_answer'] = True
                    # Также помечаем в data если есть
                    if execution_result.data and isinstance(execution_result.data, dict):
                        execution_result.data['is_final_answer'] = True
                    # 🔧 Останавливаем агента после final_answer
                    self.state.finished = True

                return execution_result

        except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.error(f"🔴 [_execute_single_step_internal] ❌ Ошибка выполнения: {e}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error(f"Ошибка в работе агента на шаге {self._current_step + 1}: {e}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.state.register_error()

            # Регистрация ошибки в контексте
            self.session_context.record_error(
                error_data=str(e),
                error_type="execution_error",
                step_number=self._current_step + 1
            )

            # ПРОВЕРКА: Превышен ли лимит ошибок
            if self.policy.should_fallback(self.state):
                if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.error(
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        f"Превышен лимит ошибок ({self.state.error_count}/{self.policy.max_errors}). "
                        f"Агент переходит в режим завершения."
                    )
                # Возвращаем специальный маркер для прерывания цикла
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    data=None,
                    error=f"Превышен лимит ошибок: {self.state.error_count}/{self.policy.max_errors}",
                    metadata={
                        "error_count": self.state.error_count,
                        "max_errors": self.policy.max_errors,
                        "failed_at_step": self._current_step + 1
                    }
                )

            return None

        # В любом случае увеличиваем номер текущего шага для следующей итерации
        self.state.step += 1

# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        logger.debug(f"🔴 [_execute_single_step_internal] Возврат None (конец метода, decision.action={decision.action.value})")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return None

    async def _execute_single_step(self) -> Any:
        """Выполнение одного шага рассуждений."""
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.debug(f"Выполнение шага {self._current_step + 1}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Получаем доступные capability для использования в паттернах поведения
        # Агент использует ТОЛЬКО навыки (SKILL), не инструменты (TOOL)
        if hasattr(self.application_context, 'get_all_skills'):
            available_caps = self.application_context.get_all_skills()
        elif hasattr(self.application_context, 'get_all_capabilities'):
            all_caps = await self.application_context.get_all_capabilities()
            # Фильтр: только SKILL capability (не TOOL, не planning)
            available_caps = [
                cap for cap in all_caps
                if hasattr(cap, 'skill_name') and not cap.name.startswith('planning.')
            ]
        else:
            available_caps = []

        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.debug(f"RUNTIME: Получено {len(available_caps)} доступных capability: {[c.name for c in available_caps]}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Получаем решение от менеджера поведения
        decision = await self.behavior_manager.generate_next_decision(
            session_context=self.session_context,
            available_capabilities=available_caps
        )

        # Делегируем выполнение внутреннему методу
        return await self._execute_single_step_internal(decision, available_caps)

    def _is_final_result(self, step_result: Any) -> bool:
        """
        Проверка, является ли результат финальным.

        ФИНАЛЬНЫЙ РЕЗУЛЬТАТ — это выполнение final_answer.generate,
        которое содержит итоговый ответ агента.
        
        КРИТИЧНО: Метод должен корректно распознавать ExecutionResult от final_answer.generate
        ДО того, как будет установлен metadata['is_final_answer'].
        """
        from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType
        
        # Проверка 1: ExecutionResult от final_answer.generate
        if isinstance(step_result, ExecutionResult):
            # Проверяем metadata на наличие признака is_final_answer
            if step_result.metadata and step_result.metadata.get('is_final_answer'):
                return True
            # Проверяем metadata на наличие capability_name или capability
            if step_result.metadata:
                cap_name = step_result.metadata.get('capability_name') or step_result.metadata.get('capability')
                if cap_name == "final_answer.generate":
                    return True
            # Проверяем данные на наличие final_answer ключа (результат генерации)
            if step_result.data and isinstance(step_result.data, dict):
                if 'final_answer' in step_result.data:
                    return True
            # Проверяем result на наличие final_answer ключа
            if step_result.result and isinstance(step_result.result, dict):
                if 'final_answer' in step_result.result:
                    return True

        # Проверка 2: BehaviorDecision с флагом is_final
        if isinstance(step_result, BehaviorDecision):
            if getattr(step_result, 'is_final', False):
                return True
            # STOP decision тоже считается финальным
            if step_result.action == BehaviorDecisionType.STOP:
                return True

        # Проверка 3: dict с action_type (для обратной совместимости)
        if isinstance(step_result, dict) and step_result.get("action_type") == "final_answer":
            return True

        return False

    async def _extract_final_result(self) -> Any:
        """
        Извлечение финального результата.

        ПРИОРИТЕТЫ:
        1. Результат final_answer.generate (сохранённый в _final_answer_result)
        2. Данные из контекста сессии
        3. Fallback результат с явным предупреждением

        ВАЖНО: Не возвращаем пустые dict — только явные данные или fallback с warning
        """
        # Приоритет 1: Возвращаем результат final_answer.generate если он есть
        if self._final_answer_result:
            if self._final_answer_result.data:
                return self._final_answer_result.data
            # Если data пустой — проверяем metadata
            if self._final_answer_result.metadata:
                final_answer_data = self._final_answer_result.metadata.get('final_answer_data')
                if final_answer_data is not None:
                    return final_answer_data
                # ❌ Не возвращаем {} — это маскирует проблему!
                if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.error(
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        "❌ _final_answer_result.metadata существует, но 'final_answer_data' отсутствует. "
                        "Это указывает на ошибку в final_answer.generate."
                    )

        # Приоритет 2: Пытаемся извлечь из контекста сессии
        if self.session_context:
            session_ctx = self.session_context

            # Пытаемся получить последний final_answer из контекста
            try:
                all_items_result = self.executor.execute_action_sync(
                    action_name="context.get_all_items",
                    parameters={},
                    context=session_ctx
                )
                if all_items_result and all_items_result.result:
                    items = all_items_result.result.get('items', {})
                    # Ищем observation с final_answer
                    for item_id, item in items.items():
                        item_data = item if isinstance(item, dict) else (item.__dict__ if hasattr(item, '__dict__') else {})
                        if isinstance(item_data, dict):
                            content = item_data.get('content', {})
                            if isinstance(content, dict) and 'final_answer' in content:
                                return content
            except Exception as e:
                if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    await self.event_bus_logger.warning(f"⚠️ Не удалось получить final_answer из контекста: {e}")
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Приоритет 3: Fallback результат — НО с явным предупреждением!
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.warning(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                "⚠️ FINAL ANSWER НЕ НАЙДЕН! Возвращаем fallback результат. "
                "Возможные причины: "
                "1) final_answer.generate не был выполнен, "
                "2) Ошибка при генерации ответа, "
                "3) Данные не сохранились в контексте"
            )
        return {
            "final_goal": self.goal,
            "steps_completed": self._current_step,
            "summary": "Execution completed successfully",
            "warning": "FINAL_ANSWER_NOT_FOUND — агент не сгенерировал финальный ответ"
        }

    async def _run_async(self, goal: str = None, max_steps: int = None) -> ExecutionResult:
        """
        ПОЛНОСТЬЮ ASYNC цикл выполнения агента.

        ВСЕ вызовы используют await — никаких _safe_async_call и asyncio.run().

        ПАРАМЕТРЫ:
        - goal: Цель агента (опционально)
        - max_steps: Максимальное количество шагов (опционально)

        ВОЗВРАЩАЕТ:
        - ExecutionResult: Результат выполнения
        """
        if self._running:
            raise RuntimeError("Агент уже выполняется")

        # Обновляем goal если передан
        if goal:
            self.goal = goal

        self._running = True
        self._current_step = 0
        self._max_steps = max_steps or self._max_steps

        print(f"[DEBUG] Agent run started, session_context id: {self.session_context.session_id}, data_context items: {self.session_context.data_context.count()}")

        # Логирование
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info(f"Запуск агента с целью: {self.goal[:100]}...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        try:
            # Инициализация начального контекста выполнения
            if self.session_context:
                initial_context = self.session_context
                initial_context.record_action({
                    "step": 0,
                    "action": "initialization",
                    "timestamp": datetime.now().isoformat(),
                    "goal": self.goal
                }, step_number=0)

            # Инициализация менеджера поведения
            await self.behavior_manager.initialize(component_name="react_pattern")

            # Публикация события начала сессии для MetricsCollector
            event_bus = self.application_context.infrastructure_context.event_bus
            session_id = self.session_context.session_id
            await event_bus._publish_internal(
                EventType.SESSION_STARTED,
                {
                    "session_id": session_id,
                    "goal": self.goal,
                    "agent_id": getattr(self, 'agent_id', 'unknown')
                }
            )

            # ← НОВОЕ: Переменные для детекции зацикливания
            action_history: list = []  # История действий для детекции циклов
            consecutive_same_actions = 0
            last_action_key = None
            
            # Переменные для детекции отсутствия прогресса
            previous_snapshot = None
            previous_decision = None
            no_progress_counter = 0

            # Переменные для отслеживания ошибок выполнения
            consecutive_error_count = 0

            # Цикл рассуждений
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"\n🔵 [RUNTIME] НАЧАЛО ЦИКЛА: _current_step={self._current_step}, _max_steps={self._max_steps}, _running={self._running}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [RUNTIME] state.finished={self.state.finished}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            while self._running and self._current_step < self._max_steps:
                print(f"\n=== ШАГ {self._current_step} ===")
                print(f"  session_id: {self.session_context.session_id}")
                print(f"  GOAL: {self.goal}")
                print(f"  data_context.items: {self.session_context.data_context.count()}")
                print(f"  state.finished: {self.state.finished}")
                
                # Получаем summary для понимания что LLM видит
                summary = self.session_context.get_summary() if hasattr(self.session_context, 'get_summary') else {}
                print(f"  summary.step_count: {summary.get('step_count', 0)}")
                print(f"  summary.last_steps: {len(summary.get('last_steps', []))}")

                # ← НОВОЕ: Явные stop conditions
                if self._should_stop_early():
                    print(f"  -> ОСТАНОВКА: _should_stop_early()")
                    break

                if self.state.finished:
                    print(f"  -> ОСТАНОВКА: state.finished=True")
                    break

                # Получаем доступные capability
                if hasattr(self.application_context, 'get_all_skills'):
                    available_caps = self.application_context.get_all_skills()
                elif hasattr(self.application_context, 'get_all_capabilities'):
                    all_caps = await self.application_context.get_all_capabilities()
                    available_caps = [
                        cap for cap in all_caps
                        if hasattr(cap, 'skill_name') and not cap.name.startswith('planning.')
                    ]
                else:
                    available_caps = []

                print(f"  available_caps: {[c.name for c in available_caps[:5]]}")

                # Получаем decision
                decision = await self.behavior_manager.generate_next_decision(
                    session_context=self.session_context,
                    available_capabilities=available_caps
                )

                print(f"  -> DECISION: action={decision.action.value}, capability={getattr(decision, 'capability_name', 'N/A')}")
                print(f"  -> DECISION reason: {decision.reason[:100] if decision.reason else 'N/A'}")

                # ← НОВОЕ: Детекция зацикливания действий
                current_action_key = f"{decision.action.value}:{getattr(decision, 'capability_name', 'N/A')}"
                
                if current_action_key == last_action_key:
                    consecutive_same_actions += 1
                    if consecutive_same_actions >= 3:
                        # ← НОВОЕ: Прерываем цикл при 3 одинаковых действиях подряд
                        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            await self.event_bus_logger.warning(
                              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                                f"⚠️ Обнаружено зацикливание: действие {current_action_key} повторилось {consecutive_same_actions} раза подряд"
                            )
                        step_result = ExecutionResult.failure(
                            error=f"Detected action loop: {current_action_key} repeated {consecutive_same_actions} times",
                            metadata={
                                "error_type": "loop_detected",
                                "repeated_action": current_action_key,
                                "consecutive_count": consecutive_same_actions
                            }
                        )
                        self._result = step_result
                        self._running = False
                        break
                else:
                    consecutive_same_actions = 0
                
                last_action_key = current_action_key
                action_history.append(current_action_key)

                # ПРОВЕРКА 1: Повторение decision без изменения state
                if previous_decision and decision:
                    if (decision.action == previous_decision.action and
                        getattr(decision, 'capability_name', None) == getattr(previous_decision, 'capability_name', None)):
                        current_snapshot = self.state.snapshot()
                        if previous_snapshot == current_snapshot:
                            no_progress_counter += 1
                            if no_progress_counter >= 2:
                                from core.models.errors import AgentStuckError
                                raise AgentStuckError(
                                    f"Decision repeated {no_progress_counter} times without state change. "
                                    f"Action: {decision.action.value}, Capability: {decision.capability_name}"
                                )

                # Выполняем шаг
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [RUNTIME] Вызов _execute_single_step_internal()...")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                step_start_time = time.time()
                step_result = await self._execute_single_step_internal(decision, available_caps)
                step_execution_time_ms = (time.time() - step_start_time) * 1000
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [RUNTIME] _execute_single_step_internal вернул: {type(step_result).__name__}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                
                # ← НОВОЕ: Запись метрик шага через публикацию события EventBus
                capability_name = getattr(decision, 'capability_name', 'unknown')
                status = "completed" if hasattr(step_result, 'status') and str(step_result.status) == "ExecutionStatus.COMPLETED" else "failed"
                error_type = None
                if hasattr(step_result, 'metadata') and step_result.metadata:
                    error_type = step_result.metadata.get('error_type')

                # Публикация события выполнения шага для MetricsCollector
                session_id = self.session_context.session_id
                await self.application_context.infrastructure_context.event_bus._publish_internal(
                    EventType.SKILL_EXECUTED,
                    {
                        "agent_id": getattr(self, 'agent_id', 'unknown'),
                        "capability": capability_name,
                        "execution_time_ms": step_execution_time_ms,
                        "success": status == "completed",
                        "session_id": session_id,
                        "correlation_id": self.correlation_id,
                        "error_type": error_type
                    }
                )

                # Обновление состояния
                self._update_state(step_result)

                # Проверка на завершение
                if self._should_stop(step_result):
                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.info(f"Остановка агента: _should_stop=True")
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    self._result = step_result
                    self._running = False
                    break

                # ОБРАБОТКА ОШИБОК
                if isinstance(step_result, ExecutionResult) and step_result.status == ExecutionStatus.FAILED:
                    from core.models.types.retry_policy import ExecutionErrorInfo
                    error_info = ExecutionErrorInfo(
                        category=step_result.error_category,
                        message=step_result.error or "Неизвестная ошибка",
                        raw_error=step_result.error
                    )

                    retry_decision = self.policy.evaluate(
                        error=error_info,
                        attempt=consecutive_error_count
                    )

                    if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        await self.event_bus_logger.error(
                          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            f"Ошибка на шаге {self._current_step}: {step_result.error} | "
                            f"Категория: {step_result.error_category.value} | "
                            f"AgentPolicy: {retry_decision.decision.value}"
                        )

                    if retry_decision.decision == RetryDecision.RETRY:
                        consecutive_error_count += 1
                        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            await self.event_bus_logger.info(
                              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                                f"Повторная попытка {consecutive_error_count}/{self.policy.max_retries} "
                                f"через {retry_decision.delay_seconds:.2f} сек"
                            )
                        await asyncio.sleep(retry_decision.delay_seconds)
                        continue
                    elif retry_decision.decision == RetryDecision.ABORT:
                        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                            await self.event_bus_logger.warning(
                              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                                f"Abort: {retry_decision.reason}. Пропускаем действие."
                            )
                        consecutive_error_count = 0
                    else:
                        last_step_failed = True
                        last_error_message = f"{retry_decision.reason}: {step_result.error}"
                        self._result = step_result
                        self._running = False
                        break

                # ПРОВЕРКА 2: Изменился ли state
                current_snapshot = self.state.snapshot()
                if previous_snapshot and current_snapshot == previous_snapshot:
                    no_progress_counter += 1
                    if no_progress_counter >= 2:
                        # Вместо ошибки - принудительно вызываем final_answer
                        print(f"[RUNTIME] No progress for 2 steps, forcing final_answer")
                        try:
                            step_result = await self.safe_executor.execute(
                                capability_name="final_answer.generate",
                                parameters={"include_steps": True, "include_evidence": True, "format_type": "number"},
                                context=self.session_context
                            )
                            self._result = step_result
                        except Exception as e:
                            self._result = ExecutionResult.failure(error=f"Stuck: {str(e)}")
                        self._running = False
                        break
                else:
                    no_progress_counter = 0

                # Сброс счётчика ошибок при успешном выполнении
                if isinstance(step_result, ExecutionResult) and step_result.status == ExecutionStatus.COMPLETED:
                    consecutive_error_count = 0

                # Обновляем snapshot для следующей итерации
                previous_snapshot = current_snapshot
                previous_decision = decision

                self._current_step += 1
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [RUNTIME] === КОНЕЦ ИТЕРАЦИИ {self._current_step} ===")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # Формируем результат
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"\n🔵 [RUNTIME] Цикл завершен: step={self._current_step}, running={self._running}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [RUNTIME] state.finished={self.state.finished}, result={self._result}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            if self._final_answer_result:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [RUNTIME] Возвращаем final_answer_result")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                return self._final_answer_result

            if self._result:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                logger.debug(f"🔵 [RUNTIME] Возвращаем _result")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                return self._result

# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.debug(f"🔵 [RUNTIME] Возвращаем _extract_final_result()")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            final_data = await self._extract_final_result()
            return ExecutionResult.success(
                data=final_data,
                metadata={
                    "steps_completed": self._current_step,
                    "final_goal": self.goal
                }
            )

        except Exception as e:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            logger.exception(f"\n🔴 [RUNTIME] ИСКЛЮЧЕНИЕ: {type(e).__name__}: {e}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error(f"Ошибка выполнения агента: {e}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult.failure(str(e))
        finally:
            self._running = False
            
            # ← НОВОЕ: Публикация события завершения сессии
            if hasattr(self, 'application_context') and self.application_context:
                if hasattr(self.application_context, 'infrastructure_context'):
                    event_bus = self.application_context.infrastructure_context.event_bus
                    if event_bus and self.session_context:
                        session_id = self.session_context.session_id
                        await event_bus._publish_internal(
                            EventType.SESSION_COMPLETED,
                            {
                                "session_id": session_id,
                                "agent_id": getattr(self, 'agent_id', 'unknown'),
                                "steps_completed": getattr(self, '_current_step', 0),
                                "final_status": "completed" if self._result and self._result.status == ExecutionStatus.COMPLETED else "failed"
                            }
                        )

    async def stop(self):
        """Остановка выполнения агента."""
        self._running = False
        if self.event_bus_logger:
# TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.info("Агент остановлен пользователем")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def is_running(self) -> bool:
        """Проверка, выполняется ли агент."""
        return self._running

    def _update_state(self, result: ExecutionResult):
        """Обновление состояния агента."""
        if result is None:
            self.progress_metrics.error_count += 1
            self.progress_metrics.consecutive_errors += 1
            self.progress_metrics.no_progress_steps += 1
            return
        
        if result.status == ExecutionStatus.COMPLETED:
            self.progress_metrics.error_count = 0
            self.progress_metrics.consecutive_errors = 0
            self.progress_metrics.no_progress_steps = 0
        else:
            self.progress_metrics.error_count += 1
            self.progress_metrics.consecutive_errors += 1
            self.progress_metrics.no_progress_steps += 1

    def _should_stop(self, result: ExecutionResult) -> bool:
        """Проверка необходимости остановки."""
        if result is None:
            return False
        
        # Проверка на финальный результат
        if isinstance(result, ExecutionResult):
            if result.metadata and isinstance(result.metadata, dict):
                if result.metadata.get('is_final_answer', False):
                    return True
            if hasattr(result, 'data') and result.data:
                if isinstance(result.data, dict) and 'final_answer' in result.data:
                    return True

        # Проверка на превышение лимитов ошибок
        if self.progress_metrics.consecutive_errors >= self.policy.max_errors:
            return True

        # Проверка на отсутствие прогресса
        if self.progress_metrics.no_progress_steps >= self.policy.max_no_progress_steps:
            return True

        return False

    def _should_stop_early(self) -> bool:
        """
        ← НОВОЕ: Явные условия ранней остановки.
        
        КРИТЕРИИ:
        1. Цель достигнута (state.finished=True)
        2. Confidence высокий (если есть оценка > 0.95)
        3. Пустые действия (no-op) — лимит no_progress_steps
        
        ВОЗВРАЩАЕТ:
        - bool: True если нужно остановиться досрочно
        """
        # 1. Цель достигнута
        if self.state.finished:
            return True
        
        # 2. Confidence высокий (если есть оценка)
        if hasattr(self.state, 'confidence') and getattr(self.state, 'confidence', 0) > 0.95:
            return True
        
        # 3. Проверка лимита no-progress шагов
        if self.progress_metrics.no_progress_steps >= self.policy.max_no_progress_steps:
            return True
        
        return False
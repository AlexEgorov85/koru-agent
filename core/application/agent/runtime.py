"""
Основной класс выполнения агента - runtime цикл рассуждений для новой архитектуры.

СОДЕРЖИТ:
- Цикл рассуждений (reasoning loop)
- Управление стратегией выполнения
- Обработку действий и результатов
- Интеграцию с инфраструктурными сервисами
"""
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime
import uuid

from core.application.context.application_context import ApplicationContext
from core.execution.gateway import ExecutionGateway
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.infrastructure.logging import EventBusLogger

# Импорт компонентов из новой архитектуры
from .components import (
    BehaviorManager,
    ActionExecutor,
    AgentPolicy,
    ProgressScorer,
    AgentState
)
from core.application.behaviors.base import BehaviorDecisionType, BehaviorDecision
from core.models.errors import AgentStuckError, InfrastructureError

# Определяем ProgressMetrics локально
from dataclasses import dataclass, field
from typing import Dict, Optional


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
        self.policy = policy or AgentPolicy()
        self.state = AgentState()
        self.progress = ProgressScorer()

        # В новой архитектуре ApplicationContext сам является системным контекстом
        # так как наследуется от BaseSystemContext
        self.executor = ActionExecutor(application_context)

        # Инициализация менеджера поведения с executor
        self.behavior_manager = BehaviorManager(
            application_context=application_context,
            executor=self.executor  # ← Передаём executor
        )
        self.progress_metrics = ProgressMetrics()

        # Шлюз выполнения для координации действий
        self.execution_gateway = ExecutionGateway(application_context)

        # Создаем session_context, если он не существует в application_context
        if not hasattr(application_context, 'session_context') or application_context.session_context is None:
            from core.session_context.session_context import SessionContext
            # Используем session_id из infrastructure_context если доступен
            session_id = getattr(application_context.infrastructure_context, 'id', None)
            application_context.session_context = SessionContext(session_id=str(session_id))
            application_context.session_context.set_goal(goal)

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
                event_bus=self.application_context.infrastructure_context.event_bus,
                session_id="system",
                agent_id="system",
                component=self.__class__.__name__
            )
        # else: event_bus_logger останется None

    async def run(self, goal: str = None, max_steps: Optional[int] = None) -> ExecutionResult:
        """
        Запуск выполнения агента.

        ПАРАМЕТРЫ:
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

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Запуск агента с целью: {self.goal[:100]}...")

        try:
            # Инициализация начального контекста выполнения
            # В новой архитектуре контексты могут быть недоступны напрямую
            # Проверяем наличие атрибутов перед использованием
            if hasattr(self.application_context, 'session_context') and self.application_context.session_context:
                initial_context = self.application_context.session_context
                # Используем правильный метод для добавления шага в SessionContext
                initial_context.record_action({
                    "step": 0,
                    "action": "initialization",
                    "timestamp": datetime.now().isoformat(),
                    "goal": self.goal
                }, step_number=0)

            # Инициализация менеджера поведения
            await self.behavior_manager.initialize(component_name="react_pattern")

            # Переменные для детекции зацикливания
            previous_snapshot = None
            previous_decision = None
            no_progress_counter = 0
            
            # Переменные для отслеживания ошибок выполнения
            last_step_failed = False
            last_error_message = None

            # Цикл рассуждений
            print(f"\n🔵 [RUNTIME] НАЧАЛО ЦИКЛА: _current_step={self._current_step}, _max_steps={self._max_steps}, _running={self._running}", flush=True)
            print(f"🔵 [RUNTIME] state.finished={self.state.finished}", flush=True)
            
            while self._running and self._current_step < self._max_steps:
                print(f"\n🔵 [RUNTIME] === ИТЕРАЦИЯ {self._current_step} ===", flush=True)
                
                if self.state.finished:
                    print(f"🔴 [RUNTIME] BREAK: state.finished=True", flush=True)
                    break

                # Получаем доступные capability для использования в паттернах поведения
                if hasattr(self.application_context, 'get_all_capabilities'):
                    available_caps = await self.application_context.get_all_capabilities()
                elif hasattr(self.application_context, 'get_all_skills'):
                    available_caps = self.application_context.get_all_skills()
                elif hasattr(self.application_context, 'get_all_tools'):
                    available_caps = self.application_context.get_all_tools()
                else:
                    available_caps = []

                print(f"🔵 [RUNTIME] available_caps count={len(available_caps)}", flush=True)
                
                # Получаем decision
                print(f"🔵 [RUNTIME] Вызов behavior_manager.generate_next_decision()...", flush=True)
                decision = await self.behavior_manager.generate_next_decision(
                    session_context=self.application_context.session_context,
                    available_capabilities=available_caps
                )
                
                print(f"🔵 [RUNTIME] Получен decision: action={decision.action.value}, capability_name={getattr(decision, 'capability_name', 'N/A')}", flush=True)

                # ПРОВЕРКА 1: Повторение decision без изменения state
                if previous_decision and decision:
                    if (decision.action == previous_decision.action and
                        getattr(decision, 'capability_name', None) == getattr(previous_decision, 'capability_name', None)):
                        current_snapshot = self.state.snapshot()
                        if previous_snapshot == current_snapshot:
                            no_progress_counter += 1
                            if no_progress_counter >= 2:
                                raise AgentStuckError(
                                    f"Decision repeated {no_progress_counter} times without state change. "
                                    f"Action: {decision.action.value}, Capability: {decision.capability_name}"
                                )

                # Выполняем шаг (без повторного вызова generate_next_decision)
                print(f"🔵 [RUNTIME] Вызов _execute_single_step_internal()...", flush=True)
                step_result = await self._execute_single_step_internal(decision, available_caps)
                print(f"🔵 [RUNTIME] _execute_single_step_internal вернул: {type(step_result).__name__}", flush=True)

                # ПРОВЕРКА: Если шаг вернул ExecutionResult с ошибкой — прерываем цикл
                if isinstance(step_result, ExecutionResult) and step_result.status == ExecutionStatus.FAILED:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            f"Агент завершил выполнение с ошибкой на шаге {self._current_step}: {step_result.error}"
                        )
                    # Устанавливаем флаги для корректного финального статуса
                    last_step_failed = True
                    last_error_message = step_result.error
                    self._result = step_result
                    self._running = False
                    break

                # ПРОВЕРКА 2: Изменился ли state
                current_snapshot = self.state.snapshot()
                if previous_snapshot and current_snapshot == previous_snapshot:
                    no_progress_counter += 1
                    if no_progress_counter >= 2:
                        raise AgentStuckError(
                            "State did not mutate after observe() for 2 consecutive steps"
                        )
                else:
                    # Сброс счетчика если state изменился
                    no_progress_counter = 0

                previous_snapshot = current_snapshot
                previous_decision = decision

                # ПРОВЕРКА: Превышен ли лимит отсутствия прогресса
                if self.policy.should_stop_no_progress(self.state):
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
                            f"Нет прогресса в течение {self.state.no_progress_steps} шагов (лимит: {self.policy.max_no_progress_steps}). "
                            f"Агент завершает выполнение."
                        )
                    self._result = ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        data=None,
                        error=f"Нет прогресса: {self.state.no_progress_steps} шагов без изменений",
                        metadata={
                            "no_progress_steps": self.state.no_progress_steps,
                            "max_no_progress_steps": self.policy.max_no_progress_steps,
                            "steps_executed": self._current_step
                        }
                    )
                    self._running = False
                    break

                # Проверка завершения
                if self._is_final_result(step_result):
                    if self.event_bus_logger:
                        await self.event_bus_logger.info(f"Агент завершил выполнение на шаге {self._current_step}")
                    print(f"🔴 [RUNTIME] BREAK: _is_final_result=True", flush=True)
                    break

                self._current_step += 1
                print(f"🔵 [RUNTIME] _current_step увеличен до {self._current_step}", flush=True)

            # Формирование результата
            # ПРОВЕРКА: Определяем статус с учётом ошибок и отсутствия прогресса
            error_message = None
            if self.state.error_count >= self.policy.max_errors:
                final_status = ExecutionStatus.FAILED
                error_message = f"Превышен лимит ошибок: {self.state.error_count}/{self.policy.max_errors}"
            elif self.state.no_progress_steps >= self.policy.max_no_progress_steps:
                final_status = ExecutionStatus.FAILED
                error_message = f"Нет прогресса в течение {self.state.no_progress_steps} шагов"
            elif self._current_step >= self._max_steps:
                final_status = ExecutionStatus.FAILED
                error_message = "Превышено максимальное количество шагов"
            elif last_step_failed:
                # КРИТИЧНО: Если последний шаг завершился ошибкой, агент не может считаться успешным
                final_status = ExecutionStatus.FAILED
                error_message = last_error_message or "Последний шаг выполнения завершился ошибкой"
            else:
                final_status = ExecutionStatus.COMPLETED

            self._result = ExecutionResult(
                status=final_status,
                data=self._extract_final_result(),
                error=error_message,
                metadata={
                    "goal": self.goal,
                    "max_steps": self._max_steps,
                    "steps_executed": self._current_step,
                    "error_count": self.state.error_count,
                    "no_progress_steps": self.state.no_progress_steps,
                    "execution_time": datetime.now().timestamp()
                }
            )

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()

            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка выполнения агента: {str(e)}")
                await self.event_bus_logger.error(f"Traceback: {tb_str}")

            self._result = ExecutionResult(
                status=ExecutionStatus.FAILED,
                data=None,
                error=str(e),
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": tb_str,
                    "goal": self.goal,
                    "steps_executed": self._current_step,
                    "execution_time": datetime.now().timestamp()
                }
            )
        finally:
            self._running = False

        return self._result

    async def _execute_single_step_internal(self, decision, available_caps) -> Any:
        """
        Выполнение одного шага рассуждений с переданным decision.

        Используется в run() для избежания дублирования вызова generate_next_decision.
        """
        print(f"\n🔵 [_execute_single_step_internal] НАЧАЛО: step={self._current_step}, decision.action={decision.action.value}", flush=True)
        print(f"🔵 [_execute_single_step_internal] decision.capability_name={getattr(decision, 'capability_name', 'N/A')}", flush=True)
        
        if self.event_bus_logger:
            await self.event_bus_logger.debug(f"Выполнение шага {self._current_step + 1}")

        if self.event_bus_logger:
            await self.event_bus_logger.debug(f"RUNTIME: Получено {len(available_caps)} доступных capability: {[c.name for c in available_caps]}")

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"=== DECISION ПОЛУЧЕН ===")
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"decision.action: {decision.action}")
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"decision.capability_name: {getattr(decision, 'capability_name', 'N/A')}")

        # Запись решения паттерна поведения
        if decision:
            self.application_context.session_context.record_decision(
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
                await self.event_bus_logger.warning(
                    "⚠️ Agent attempted to stop on first step - это обычно ошибка LLM или пустой список capabilities"
                )
            print("\n⚠️ SAFEGUARD TRIGGERED: Agent attempted to stop on step 0")
            print(f"   Goal: {self.goal[:100]}...")
            print(f"   Available capabilities: {len(available_caps)}")
            print("   Possible causes:")
            print("   1. LLM incorrectly parsed the goal as already achieved")
            print("   2. No capabilities were available to the LLM")
            print("   3. Prompt template needs adjustment\n")

            # Возвращаем ошибку чтобы behavior manager мог переключиться на fallback
            print(f"🔴 [_execute_single_step_internal] Возврат SWITCH (safeguard)", flush=True)
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="fallback_pattern",
                reason="stop_on_first_step"
            )

        if decision.action == BehaviorDecisionType.STOP:
            print(f"🔵 [_execute_single_step_internal] decision.action=STOP", flush=True)
            self.state.finished = True
            # Регистрируем финальное решение
            self.application_context.session_context.record_decision(
                decision_data="STOP",
                reasoning="goal_achieved"
            )
            print(f"🔴 [_execute_single_step_internal] Возврат STOP decision", flush=True)
            return decision

        if decision.action == BehaviorDecisionType.ACT:
            print(f"🔵 [_execute_single_step_internal] decision.action=ACT", flush=True)
            # ПРОВЕРКА: capability_name должен быть указан
            if not decision.capability_name:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"ACT decision но capability_name не указан!")
                self.state.register_error()

                # ПРОВЕРКА: Превышен ли лимит ошибок
                if self.policy.should_fallback(self.state):
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(
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

                print(f"🔴 [_execute_single_step_internal] Возврат None (capability_name не указан)", flush=True)
                return None

            print(f"🔵 [_execute_single_step_internal] Поиск capability в application_context...", flush=True)
            print(f"🔵 [_execute_single_step_internal] self.event_bus_logger={self.event_bus_logger is not None}", flush=True)
            
            # В новой архитектуре capability хранятся в components
            capability = None
            print(f"🔵 [_execute_single_step_internal] hasattr(application_context, 'components')={hasattr(self.application_context, 'components')}", flush=True)
            
            if hasattr(self.application_context, 'components'):
                print(f"🔵 [_execute_single_step_internal] application_context.components доступен", flush=True)
                # Пытаемся получить через components (универсальный метод)
                # Разбиваем capability_name на skill/tool name и capability name
                parts = decision.capability_name.split('.')
                print(f"🔵 [_execute_single_step_internal] parts={parts}", flush=True)
                if len(parts) >= 2:
                    component_name = parts[0]  # например, book_library
                    print(f"🔵 [_execute_single_step_internal] component_name={component_name}", flush=True)
                    # Ищем во всех типах компонентов
                    from core.models.enums.common_enums import ComponentType
                    print(f"🔵 [_execute_single_step_internal] Поиск в ComponentType.SKILL...", flush=True)
                    comp = self.application_context.components.get(ComponentType.SKILL, component_name)
                    if comp:
                        capability = comp
                        print(f"🔵 [_execute_single_step_internal] ✅ Найден компонент SKILL.{component_name}", flush=True)
                    
                    if not capability:
                        print(f"🔵 [_execute_single_step_internal] Поиск в ComponentType.TOOL...", flush=True)
                        comp = self.application_context.components.get(ComponentType.TOOL, component_name)
                        if comp:
                            capability = comp
                            print(f"🔵 [_execute_single_step_internal] ✅ Найден компонент TOOL.{component_name}", flush=True)
                    
                    if not capability:
                        print(f"🔵 [_execute_single_step_internal] Поиск в ComponentType.SERVICE...", flush=True)
                        comp = self.application_context.components.get(ComponentType.SERVICE, component_name)
                        if comp:
                            capability = comp
                            print(f"🔵 [_execute_single_step_internal] ✅ Найден компонент SERVICE.{component_name}", flush=True)
            else:
                print(f"🔴 [_execute_single_step_internal] capability_name не содержит '.' : {decision.capability_name}", flush=True)
        else:
            print(f"🔴 [_execute_single_step_internal] application_context.components НЕ доступен", flush=True)

        # Fallback: проверяем специальные методы если components не сработал
        if not capability:
            if hasattr(self.application_context, 'get_skill'):
                # Пытаемся получить как skill (для совместимости)
                skill_name = decision.capability_name.split('.')[0]
                capability = self.application_context.get_skill(skill_name)
                if capability:
                    print(f"🔵 [_execute_single_step_internal] ✅ Найден skill: {skill_name}", flush=True)

        print(f"🔵 [_execute_single_step_internal] capability found: {capability is not None}", flush=True)
        if not capability:
            print(f"🔴 [_execute_single_step_internal] Capability '{decision.capability_name}' не найдена", flush=True)
            self.state.register_error()

            # ПРОВЕРКА: Превышен ли лимит ошибок
            if self.policy.should_fallback(self.state):
                if self.event_bus_logger:
                    await self.event_bus_logger.error(
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
            print(f"🔵 [_execute_single_step_internal] 🚀 Запуск выполнения {decision.capability_name}...", flush=True)
            
            # Создаём объект Capability с правильным именем для передачи в компонент
            from core.models.data.capability import Capability
            cap_obj = Capability(
                name=decision.capability_name,
                description=f"Capability {decision.capability_name}",
                skill_name=component_name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={}
            )
            
            execution_result = await self.executor.execute_capability(
                capability=cap_obj,  # Передаём объект Capability с правильным именем
                parameters=decision.parameters,
                session_context=self.application_context.session_context,
                user_context=self.user_context
            )
            print(f"🔵 [_execute_single_step_internal] ✅ {decision.capability_name} выполнен успешно", flush=True)
            print(f"🔵 [_execute_single_step_internal] 📊 Результат: {execution_result}", flush=True)

            # ПРОВЕРКА: Если decision требует LLM, проверяем что он был вызван
            if getattr(decision, 'requires_llm', False):
                # ExecutionResult может иметь llm_called флаг
                if hasattr(execution_result, 'llm_called') and not execution_result.llm_called:
                    raise InfrastructureError(
                        f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                    )

            # Обновление контекста выполнения
            if (hasattr(self.application_context, 'session_context') and
                self.application_context.session_context):
                action_id = self.application_context.session_context.record_action({
                    "step": self._current_step + 1,
                    "action": decision.capability_name,
                    "result": execution_result,
                    "timestamp": datetime.now().isoformat()
                }, step_number=self._current_step + 1)

                if self.event_bus_logger:
                    await self.event_bus_logger.debug(f"✅ Action записан с ID: {action_id}")

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
                        observation_id = self.application_context.session_context.record_observation(
                            observation_data=obs_data,
                            source=decision.capability_name,
                            step_number=self._current_step + 1
                        )
                        if self.event_bus_logger:
                            await self.event_bus_logger.debug(f"✅ Observation записана с ID: {observation_id}")
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.warning(f"⚠️ Не удалось записать observation: {e}")

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
                        await self.event_bus_logger.info(f"🔵 Вызов register_step: step={self._current_step + 1}, capability={decision.capability_name}, obs_ids={observation_item_ids}")
                        await self.event_bus_logger.info(f"🔵 step_context до register_step: count={self.application_context.session_context.step_context.count()}")

                    self.application_context.session_context.register_step(
                        step_number=self._current_step + 1,
                        capability_name=decision.capability_name,
                        skill_name=decision.capability_name.split('.')[0] if '.' in decision.capability_name else decision.capability_name,
                        action_item_id=action_id,
                        observation_item_ids=observation_item_ids,
                        summary=step_summary,
                        status=step_status  # ← передаём ExecutionStatus вместо строки
                    )

                    if self.event_bus_logger:
                        await self.event_bus_logger.info(f"✅ Step {self._current_step + 1} зарегистрирован в step_context")
                        await self.event_bus_logger.info(f"✅ step_context.count() после register_step = {self.application_context.session_context.step_context.count()}")
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"❌ Ошибка register_step: {e}")

                # Оценка прогресса и обновление состояния
                progressed = self.progress.evaluate(self.application_context.session_context)
                self.state.register_progress(progressed)

                return execution_result

        except Exception as e:
            print(f"🔴 [_execute_single_step_internal] ❌ Ошибка выполнения: {e}", flush=True)
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка в работе агента на шаге {self._current_step + 1}: {e}")
            self.state.register_error()

            # Регистрация ошибки в контексте
            self.application_context.session_context.record_error(
                error_data=str(e),
                error_type="execution_error",
                step_number=self._current_step + 1
            )

            # ПРОВЕРКА: Превышен ли лимит ошибок
            if self.policy.should_fallback(self.state):
                if self.event_bus_logger:
                    await self.event_bus_logger.error(
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

        print(f"🔴 [_execute_single_step_internal] Возврат None (конец метода, decision.action={decision.action.value})", flush=True)
        return None

    async def _execute_single_step(self) -> Any:
        """Выполнение одного шага рассуждений."""
        if self.event_bus_logger:
            await self.event_bus_logger.debug(f"Выполнение шага {self._current_step + 1}")

        # Получаем доступные capability для использования в паттернах поведения
        # В новой архитектуре используем метод get_all_capabilities() из ApplicationContext
        if hasattr(self.application_context, 'get_all_capabilities'):
            available_caps = await self.application_context.get_all_capabilities()
        elif hasattr(self.application_context, 'get_all_skills'):
            available_caps = self.application_context.get_all_skills()
        elif hasattr(self.application_context, 'get_all_tools'):
            available_caps = self.application_context.get_all_tools()
        else:
            # Если нет специальных методов, возвращаем пустой список
            available_caps = []

        if self.event_bus_logger:
            await self.event_bus_logger.debug(f"RUNTIME: Получено {len(available_caps)} доступных capability: {[c.name for c in available_caps]}")

        # Получаем решение от менеджера поведения
        decision = await self.behavior_manager.generate_next_decision(
            session_context=self.application_context.session_context,
            available_capabilities=available_caps
        )

        # Делегируем выполнение внутреннему методу
        return await self._execute_single_step_internal(decision, available_caps)

    def _is_final_result(self, step_result: Any) -> bool:
        """Проверка, является ли результат финальным."""
        # В реальной реализации здесь будет проверка на достижение цели
        # или получение финального ответа
        if isinstance(step_result, dict) and step_result.get("action_type") == "final_answer":
            return True
        return False

    def _extract_final_result(self) -> Any:
        """Извлечение финального результата."""
        # В реальной реализации здесь будет извлечение результата
        # из контекста выполнения или последнего шага
        return {
            "final_goal": self.goal,
            "steps_completed": self._current_step,
            "summary": "Execution completed successfully"
        }

    async def stop(self):
        """Остановка выполнения агента."""
        self._running = False
        if self.event_bus_logger:
            await self.event_bus_logger.info("Агент остановлен пользователем")

    def is_running(self) -> bool:
        """Проверка, выполняется ли агент."""
        return self._running
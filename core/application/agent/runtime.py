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
from core.application.behaviors.base import BehaviorDecisionType
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

        # Инициализация компонентов
        self.policy = policy or AgentPolicy()
        self.state = AgentState()
        self.progress = ProgressScorer()
        
        # В новой архитектуре ApplicationContext сам является системным контекстом
        # так как наследуется от BaseSystemContext
        self.executor = ActionExecutor(application_context)
        
        # Инициализация менеджера поведения
        self.behavior_manager = BehaviorManager(application_context=application_context)
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
            asyncio.create_task(self.event_bus_logger.info(f"Запуск агента с целью: {self.goal[:100]}..."))

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

            # Цикл рассуждений
            while self._running and self._current_step < self._max_steps:
                if self.state.finished:
                    break

                # Получаем доступные capability для использования в паттернах поведения
                if hasattr(self.application_context, 'get_all_capabilities'):
                    available_caps = self.application_context.get_all_capabilities()
                elif hasattr(self.application_context, 'get_all_skills'):
                    available_caps = self.application_context.get_all_skills()
                elif hasattr(self.application_context, 'get_all_tools'):
                    available_caps = self.application_context.get_all_tools()
                else:
                    available_caps = []

                # Получаем decision
                decision = await self.behavior_manager.generate_next_decision(
                    session_context=self.application_context.session_context,
                    available_capabilities=available_caps
                )

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
                step_result = await self._execute_single_step_internal(decision, available_caps)

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

                # Проверка завершения
                if self._is_final_result(step_result):
                    if self.event_bus_logger:
                        asyncio.create_task(self.event_bus_logger.info(f"Агент завершил выполнение на шаге {self._current_step}"))
                    break

                self._current_step += 1

            # Формирование результата
            final_status = ExecutionStatus.COMPLETED if self._current_step < self._max_steps else ExecutionStatus.FAILED
            if self._current_step >= self._max_steps:
                final_status = ExecutionStatus.FAILED  # Превышено максимальное количество шагов
            
            self._result = ExecutionResult(
                status=final_status,
                result=self._extract_final_result(),
                metadata={
                    "goal": self.goal,
                    "max_steps": self._max_steps,
                    "steps_executed": self._current_step,
                    "execution_time": datetime.now().timestamp()
                }
            )

        except Exception as e:
            if self.event_bus_logger:
                asyncio.create_task(self.event_bus_logger.error(f"Ошибка выполнения агента: {str(e)}"))
            self._result = ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=str(e),
                metadata={
                    "error": str(e),
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
        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.debug(f"Выполнение шага {self._current_step + 1}"))

        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.debug(f"RUNTIME: Получено {len(available_caps)} доступных capability: {[c.name for c in available_caps]}"))

        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.info(f"=== DECISION ПОЛУЧЕН ==="))
        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.info(f"decision.action: {decision.action}"))
        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.info(f"decision.capability_name: {getattr(decision, 'capability_name', 'N/A')}"))

        # Запись решения паттерна поведения
        if decision:
            self.application_context.session_context.record_decision(
                decision.action.value,
                reasoning=decision.reason
            )

        if decision.action == BehaviorDecisionType.STOP:
            self.state.finished = True
            # Регистрируем финальное решение
            self.application_context.session_context.record_decision(
                decision_data="STOP",
                reasoning="goal_achieved"
            )
            return decision

        if decision.action == BehaviorDecisionType.ACT:
            # ПРОВЕРКА: capability_name должен быть указан
            if not decision.capability_name:
                if self.event_bus_logger:
                    asyncio.create_task(self.event_bus_logger.error(f"ACT decision но capability_name не указан!"))
                self.state.register_error()
                return None

            if self.event_bus_logger:
                asyncio.create_task(self.event_bus_logger.info(f"=== ВЫПОЛНЕНИЕ ACT ==="))
                asyncio.create_task(self.event_bus_logger.info(f"decision.capability_name: {decision.capability_name}"))
                asyncio.create_task(self.event_bus_logger.info(f"decision.parameters: {decision.parameters}"))
                asyncio.create_task(self.event_bus_logger.info(f"🎯 Выбранный навык: {decision.capability_name}"))
                asyncio.create_task(self.event_bus_logger.info(f"📦 Параметры: {decision.parameters}"))
                asyncio.create_task(self.event_bus_logger.info(f"🔍 Поиск capability: {decision.capability_name}..."))

                # В новой архитектуре capability хранятся в components
                capability = None
                if hasattr(self.application_context, 'components'):
                    # Пытаемся получить через components (универсальный метод)
                    # Разбиваем capability_name на skill/tool name и capability name
                    parts = decision.capability_name.split('.')
                    if len(parts) >= 2:
                        component_name = parts[0]  # например, book_library
                        # Ищем во всех типах компонентов
                        from core.models.enums.common_enums import ComponentType
                        for comp_type in [ComponentType.SKILL, ComponentType.TOOL, ComponentType.SERVICE]:
                            comp = self.application_context.components.get(comp_type, component_name)
                            if comp:
                                capability = comp
                                asyncio.create_task(self.event_bus_logger.info(f"✅ Найден компонент {comp_type.value}.{component_name}"))
                                break

                # Fallback: проверяем специальные методы если components не сработал
                if not capability:
                    if hasattr(self.application_context, 'get_skill'):
                        # Пытаемся получить как skill (для совместимости)
                        skill_name = decision.capability_name.split('.')[0]
                        capability = self.application_context.get_skill(skill_name)
                        if capability:
                            asyncio.create_task(self.event_bus_logger.info(f"✅ Найден skill: {skill_name}"))

                asyncio.create_task(self.event_bus_logger.info(f"capability found: {capability is not None}"))
                if not capability:
                    asyncio.create_task(self.event_bus_logger.error(f"Capability '{decision.capability_name}' не найдена"))
                    return None

                # Выполняем capability
                try:
                    asyncio.create_task(self.event_bus_logger.info(f"🚀 Запуск выполнения {decision.capability_name}..."))
                    execution_result = await self.executor.execute_capability(
                        capability=capability,
                        parameters=decision.parameters,
                        session_context=self.application_context.session_context,
                        user_context=self.user_context
                    )
                    asyncio.create_task(self.event_bus_logger.info(f"✅ {decision.capability_name} выполнен успешно"))
                    asyncio.create_task(self.event_bus_logger.info(f"📊 Результат: {execution_result}"))

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
                        self.application_context.session_context.record_action({
                            "step": self._current_step + 1,
                            "action": decision.capability_name,
                            "result": execution_result,
                            "timestamp": datetime.now().isoformat()
                        }, step_number=self._current_step + 1)

                    # Оценка прогресса и обновление состояния
                    progressed = self.progress.evaluate(self.application_context.session_context)
                    self.state.register_progress(progressed)

                    return execution_result

                except Exception as e:
                    if self.event_bus_logger:
                        asyncio.create_task(self.event_bus_logger.error(f"Ошибка в работе агента на шаге {self._current_step + 1}: {e}"))
                    self.state.register_error()

                    # Регистрация ошибки в контексте
                    self.application_context.session_context.record_error(
                        error_data=str(e),
                        error_type="execution_error",
                        step_number=self._current_step + 1
                    )

                    return None

        # В любом случае увеличиваем номер текущего шага для следующей итерации
        self.state.step += 1

        return None

    async def _execute_single_step(self) -> Any:
        """Выполнение одного шага рассуждений."""
        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.debug(f"Выполнение шага {self._current_step + 1}"))

        # Получаем доступные capability для использования в паттернах поведения
        # В новой архитектуре используем метод get_all_capabilities() из ApplicationContext
        if hasattr(self.application_context, 'get_all_capabilities'):
            available_caps = self.application_context.get_all_capabilities()
        elif hasattr(self.application_context, 'get_all_skills'):
            available_caps = self.application_context.get_all_skills()
        elif hasattr(self.application_context, 'get_all_tools'):
            available_caps = self.application_context.get_all_tools()
        else:
            # Если нет специальных методов, возвращаем пустой список
            available_caps = []

        if self.event_bus_logger:
            asyncio.create_task(self.event_bus_logger.debug(f"RUNTIME: Получено {len(available_caps)} доступных capability: {[c.name for c in available_caps]}"))

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
            asyncio.create_task(self.event_bus_logger.info("Агент остановлен пользователем"))

    def is_running(self) -> bool:
        """Проверка, выполняется ли агент."""
        return self._running
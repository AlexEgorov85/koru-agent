"""
Минималистичный runtime агента — сжатая архитектура.

АРХИТЕКТУРА:
- AgentRuntime: тонкий оркестратор цикла
- AgentLoop: decide → execute → observe → control
- Executor: выполнение действий (+ retry middleware)
- Controller: policy + fallback решения
- Observer: анализ результатов
- Metrics: сбор метрик

КОМПОНЕНТЫ (5 вместо 10+):
1. AgentRuntime
2. AgentLoop  
3. Executor
4. Controller
5. Observer
+ Metrics (отдельно)
"""
import uuid
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType

# Ленивый импорт для избежания циклических зависимостей
if TYPE_CHECKING:
    from core.application_context.application_context import ApplicationContext


@dataclass
class AgentState:
    """
    Упрощённое состояние агента.
    
    АТРИБУТЫ:
    - goal: цель выполнения
    - steps: количество шагов
    - max_steps: лимит шагов
    - history: история выполненных действий
    - failures: количество последовательных ошибок
    - last_action: последнее действие
    - last_observation: последнее наблюдение
    """
    goal: str
    steps: int = 0
    max_steps: int = 10
    history: List[Dict[str, Any]] = field(default_factory=list)
    failures: int = 0
    last_action: Optional[str] = None
    last_observation: Optional[Dict[str, Any]] = None
    
    def apply(self, action: str, result: ExecutionResult, observation: Dict[str, Any]):
        """Применить результат шага к состоянию."""
        self.steps += 1
        self.last_action = action
        self.last_observation = observation
        
        self.history.append({
            "step": self.steps,
            "action": action,
            "result": result,
            "observation": observation,
            "timestamp": datetime.now().isoformat()
        })
        
        # Обновление счётчика ошибок (используем универсальную проверку)
        is_success = _is_execution_success(result)
        if not is_success:
            self.failures += 1
        else:
            self.failures = 0
    
    def is_goal_reached(self) -> bool:
        """Проверка достижения цели (заглушка, переопределяется в Pattern)."""
        return False


@dataclass  
class StepResult:
    """Результат шага выполнения."""
    done: bool = False
    success: bool = True
    error: Optional[str] = None
    state: Optional[AgentState] = None
    
    @classmethod
    def done(cls, state: AgentState):
        return cls(done=True, success=True, state=state)
    
    @classmethod
    def fail(cls, error: str, state: AgentState = None):
        return cls(done=True, success=False, error=error, state=state)
    
    @classmethod
    def continue_(cls, state: AgentState):
        return cls(done=False, success=True, state=state)


def _is_execution_success(result: Any) -> bool:
    """
    Проверка успешности выполнения.
    
    Поддерживает:
    - ExecutionResult (проверка status == COMPLETED или is_success property)
    - StepResult (проверка success атрибута)
    """
    from core.models.enums.common_enums import ExecutionStatus
    
    # Если это ExecutionResult
    if hasattr(result, 'status'):
        return result.status == ExecutionStatus.COMPLETED
    
    # Если есть is_success property (ExecutionResult)
    if hasattr(result, 'is_success'):
        return result.is_success is True
    
    # Если это StepResult или другой объект с атрибутом success
    if hasattr(result, 'success') and not callable(getattr(result, 'success')):
        return result.success is True
    
    return False


class AgentMetrics:
    """
    Простые метрики выполнения агента.
    
    ОТВЕТСТВЕННОСТЬ:
    - Подсчёт шагов
    - Подсчёт ошибок
    - Проверка условий остановки
    """
    
    def __init__(self):
        self.steps = 0
        self.errors = 0
        self.empty_results = 0
        self.repeated_actions = 0
    
    def update(self, step_result: StepResult):
        """Обновить метрики по результату шага."""
        self.steps += 1
        if step_result.error:
            self.errors += 1
    
    def should_stop(self, max_errors: int = 10) -> tuple[bool, str]:
        """Проверка условий остановки."""
        if self.errors >= max_errors:
            return True, f"max_errors_reached ({self.errors})"
        return False, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "steps": self.steps,
            "errors": self.errors,
            "empty_results": self.empty_results,
            "repeated_actions": self.repeated_actions
        }


class AgentRuntime:
    """
    Тонкий оркестратор цикла выполнения агента.
    
    ОТВЕТСТВЕННОСТЬ:
    - Управление циклом выполнения
    - Создание session state
    - Сбор метрик
    
    НЕ ЗНАЕТ ПРО:
    - Детали executor / policy / fallback
    - Создание зависимостей
    
    DEPRECATED: используйте MinimalAgentRuntime вместо этого класса.
    Это имя сохранено для обратной совместимости.
    """
    
    def __init__(
        self,
        loop: Any,  # AgentLoop
        metrics: AgentMetrics,
        application_context: 'ApplicationContext',
        goal: str,
        max_steps: int = 10,
        agent_id: str = "agent_001",
        correlation_id: Optional[str] = None
    ):
        self.loop = loop
        self.metrics = metrics
        self.application_context = application_context
        self.goal = goal
        self.max_steps = max_steps
        self.agent_id = agent_id
        self.correlation_id = correlation_id or str(uuid.uuid4())
        
        # Логгер
        log_session = application_context.infrastructure_context.log_session
        self.log = log_session.create_agent_logger(agent_id)
    
    async def run(self, goal: str = None, max_steps: int = None) -> ExecutionResult:
        """
        Запуск цикла выполнения.
        
        ПАРАМЕТРЫ:
        - goal: цель (переопределяет начальную)
        - max_steps: лимит шагов (переопределяет начальный)
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        """
        if goal:
            self.goal = goal
        if max_steps:
            self.max_steps = max_steps
        
        # Создание состояния
        state = AgentState(goal=self.goal, max_steps=self.max_steps)
        
        self.log.info(
            f"Агент {self.agent_id} запущен, цель: {self.goal[:50]}...",
            extra={"event_type": LogEventType.AGENT_START}
        )
        
        # Цикл выполнения
        for step in range(self.max_steps):
            # Проверка условий остановки по метрикам
            should_stop, stop_reason = self.metrics.should_stop()
            if should_stop:
                self.log.warning(
                    f"🛑 Остановка: {stop_reason}",
                    extra={"event_type": LogEventType.AGENT_STOP}
                )
                return ExecutionResult.failure(f"Stopped: {stop_reason}")
            
            result = await self.loop.step(state)
            
            # Обновление метрик
            self.metrics.update(result)
            
            # Проверка завершения
            if result.done:
                if result.success:
                    self.log.info(
                        f"Агент завершил работу успешно за {state.steps} шагов",
                        extra={"event_type": LogEventType.AGENT_STOP}
                    )
                    return ExecutionResult.create_success(
                        data={
                            "steps": state.steps,
                            "history": state.history
                        }
                    )
                else:
                    self.log.error(
                        f"Агент остановлен с ошибкой: {result.error}",
                        extra={"event_type": LogEventType.AGENT_STOP}
                    )
                    return ExecutionResult.failure(result.error)
        
        # Лимит шагов исчерпан
        self.log.warning(
            f"Агент достиг лимита шагов ({self.max_steps})",
            extra={"event_type": LogEventType.AGENT_STOP}
        )
        return ExecutionResult.failure(f"Max steps ({self.max_steps}) reached")


class AgentLoop:
    """
    Сердце системы — цикл decide → execute → observe → control.
    
    ОТВЕТСТВЕННОСТЬ:
    1. DecisionMaker.decide() — выбор действия
    2. Executor.execute() — выполнение действия
    3. Observer.observe() — анализ результата
    4. State.apply() — обновление состояния
    5. Controller.evaluate() — policy + fallback решения
    
    ЗАМЕНЯЕТ:
    - Pattern
    - StepExecutor
    - часть Runtime
    - часть Policy
    """
    
    def __init__(
        self,
        decision_maker: Any,  # Pattern / DecisionMaker
        executor: Any,  # Executor
        observer: Any,  # Observer
        controller: Any  # Controller
    ):
        self.decision_maker = decision_maker
        self.executor = executor
        self.observer = observer
        self.controller = controller
    
    async def step(self, state: AgentState) -> StepResult:
        """
        Один шаг цикла агента.
        
        ПАРАМЕТРЫ:
        - state: текущее состояние
        
        ВОЗВРАЩАЕТ:
        - StepResult: результат шага
        """
        # 1. Decide — выбор действия
        action = await self.decision_maker.decide(state)
        
        # 2. Execute — выполнение действия
        result = await self.executor.execute(action, state)
        
        # 3. Observe — анализ результата
        observation = await self.observer.observe(result, state)
        
        # 4. Update state — применение изменений
        state.apply(action, result, observation)
        
        # 5. Control — policy + fallback решения
        decision = self.controller.evaluate(state, result)
        
        return decision


class Executor:
    """
    Выполнение действий через tool registry.
    
    ОТВЕТСТВЕННОСТЬ:
    - Получение инструмента из registry
    - Выполнение инструмента
    - Публикация событий в event bus
    - Возврат ExecutionResult
    
    ЗАМЕНЯЕТ:
    - ActionExecutor
    - SafeExecutor (частично)
    - StepExecutor (частично)
    """
    
    def __init__(
        self,
        tool_registry: Any,
        event_bus: Any,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ):
        self.tool_registry = tool_registry
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
    
    async def execute(self, action: str, state: AgentState) -> ExecutionResult:
        """
        Выполнить действие.
        
        ПАРАМЕТРЫ:
        - action: имя действия/инструмента
        - state: текущее состояние
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        """
        from datetime import datetime
        
        tool = self.tool_registry.get(action)
        
        if not tool:
            return ExecutionResult.failure(f"Tool not found: {action}")
        
        start_time = datetime.now()
        
        try:
            # Выполнение инструмента
            # Параметры берём из state или передаём пустыми
            params = getattr(state, 'last_observation', {}) or {}
            result = await tool.run(params)
            
            latency = (datetime.now() - start_time).total_seconds()
            
            # Публикация события успеха
            if self.event_bus:
                await self.event_bus.publish("TOOL_SUCCESS", {
                    "action": action,
                    "latency": latency,
                    "result": result
                }, session_id=self.session_id, agent_id=self.agent_id)
            
            return ExecutionResult.create_success(result)
            
        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds()
            
            # Публикация события ошибки
            if self.event_bus:
                await self.event_bus.publish("TOOL_ERROR", {
                    "action": action,
                    "error": str(e),
                    "latency": latency
                }, session_id=self.session_id, agent_id=self.agent_id)
            
            return ExecutionResult.failure(str(e))


class RetryExecutor:
    """
    Middleware для retry поверх Executor.
    
    ОТВЕТСТВЕННОСТЬ:
    - Повторное выполнение при ошибках
    - Экспоненциальная задержка между попытками
    
    ЗАМЕНЯЕТ:
    - SafeExecutor (retry логику)
    """
    
    def __init__(self, executor: Executor, max_retries: int = 2, base_delay: float = 0.5):
        self.executor = executor
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def execute(self, action: str, state: AgentState) -> ExecutionResult:
        """
        Выполнить действие с retry.
        
        ПАРАМЕТРЫ:
        - action: имя действия
        - state: состояние
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат
        """
        import asyncio
        import random
        
        for attempt in range(self.max_retries + 1):
            result = await self.executor.execute(action, state)
            
            # Используем универсальную проверку успешности
            if _is_execution_success(result):
                return result
            
            # Если это не последняя попытка — задержка
            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** attempt)
                jitter = random.uniform(0.5, 1.5)
                await asyncio.sleep(delay * jitter)
        
        return result


class Controller:
    """
    Контроллер — policy + fallback решения.
    
    ОТВЕТСТВЕННОСТЬ:
    - Проверка условий остановки
    - Обработка ошибок
    - Fallback логика
    
    ЗАМЕНЯЕТ:
    - Policy
    - FailureMemory
    - FallbackStrategy
    """
    
    def __init__(
        self,
        max_steps: int = 10,
        max_failures: int = 3,
        max_empty_results: int = 3
    ):
        self.max_steps = max_steps
        self.max_failures = max_failures
        self.max_empty_results = max_empty_results
    
    def evaluate(self, state: AgentState, result: ExecutionResult) -> StepResult:
        """
        Оценить результат и принять решение.
        
        ПАРАМЕТРЫ:
        - state: текущее состояние
        - result: результат выполнения
        
        ВОЗВРАЩАЕТ:
        - StepResult: решение о продолжении/завершении
        """
        # Stop condition — лимит шагов
        if state.steps >= self.max_steps:
            return StepResult.done(state)
        
        # Success condition — цель достигнута
        is_success = _is_execution_success(result)
        if is_success and state.is_goal_reached():
            return StepResult.done(state)
        
        # Failure handling
        if not is_success:
            # Проверяем количество последовательных ошибок
            if state.failures > self.max_failures:
                error_msg = getattr(result, 'error', 'unknown error') or 'unknown error'
                return StepResult.fail(f"too many errors: {error_msg}", state)
        
        # Продолжаем выполнение
        return StepResult.continue_(state)


class Observer:
    """
    Простой observer для анализа результатов.
    
    ОТВЕТСТВЕННОСТЬ:
    - Анализ результата (success/error/empty)
    - Извлечение ключевой информации
    
    УПРОЩЁННАЯ ВЕРСИЯ — без LLM
    """
    
    async def observe(self, result: ExecutionResult, state: AgentState) -> Dict[str, Any]:
        """
        Наблюдение за результатом.
        
        ПАРАМЕТРЫ:
        - result: результат выполнения
        - state: текущее состояние
        
        ВОЗВРАЩАЕТ:
        - observation: словарь с наблюдением
        """
        is_success = _is_execution_success(result)
        
        observation = {
            "success": is_success,
            "error": result.error if hasattr(result, 'error') else None,
            "status": "success" if is_success else "error"
        }
        
        # Проверка на пустой результат
        if is_success:
            data = getattr(result, 'data', None)
            if data is None or (isinstance(data, (list, dict)) and len(data) == 0):
                observation["status"] = "empty"
        
        return observation


# Алиас для обратной совместимости
MinimalAgentRuntime = AgentRuntime

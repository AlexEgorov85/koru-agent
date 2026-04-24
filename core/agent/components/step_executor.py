"""
StepExecutor — конфигурируемый исполнитель шагов агента.

АРХИТЕКТУРА:
- Обёртка над SafeExecutor для применения конфигурации шага
- Реализует таймауты, retry с экспоненциальным backoff, fallback-логику
- Публикует события в EventBus для наблюдаемости

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
```python
step_executor = StepExecutor(
    safe_executor=safe_executor,
    event_bus=event_bus,
    session_id="session_123",
    agent_id="agent_001"
)

result = await step_executor.execute_with_config(
    step_config=step_config,
    parameters={"query": "SELECT * FROM users"},
    context=execution_context
)
```
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.components.action_executor import ExecutionContext
from core.agent.models import StepConfig, StepExecutionStatus, StepAttempt, StepMetrics
from core.infrastructure.event_bus.unified_event_bus import EventType

if TYPE_CHECKING:
    from core.agent.components.safe_executor import SafeExecutor
    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus


class StepExecutor:
    """
    Конфигурируемый исполнитель шагов агента.
    
    ОТВЕТСТВЕННОСТЬ:
    - Применение таймаутов из конфигурации шага
    - Retry с экспоненциальным backoff
    - Fallback-логика при ошибках
    - Сбор метрик выполнения
    - Публикация событий в EventBus
    
    АТРИБУТЫ:
    - safe_executor: базовый исполнитель для вызова capability
    - event_bus: шина событий для публикации событий шагов
    - session_id: идентификатор сессии
    - agent_id: идентификатор агента
    """
    
    def __init__(
        self,
        safe_executor: 'SafeExecutor',
        event_bus: Optional['UnifiedEventBus'] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        log_session: Optional[Any] = None
    ):
        """
        Инициализация StepExecutor.
        
        ПАРАМЕТРЫ:
        - safe_executor: SafeExecutor для выполнения capability
        - event_bus: EventBus для публикации событий (опционально)
        - session_id: идентификатор сессии
        - agent_id: идентификатор агента
        - log_session: сессия логирования
        """
        self.safe_executor = safe_executor
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
        self._log_session = log_session
        
        # Кэш метрик по шагам
        self._step_metrics: dict[str, StepMetrics] = {}
    
    def _get_logger(self) -> logging.Logger:
        """Получение логгера."""
        if self._log_session and hasattr(self._log_session, 'app_logger'):
            return self._log_session.app_logger
        return logging.getLogger(__name__)
    
    async def execute_with_config(
        self,
        step_config: StepConfig,
        parameters: dict,
        context: ExecutionContext,
        step_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Выполнить шаг с применением конфигурации.
        
        ПАРАМЕТРЫ:
        - step_config: конфигурация шага
        - parameters: параметры для capability
        - context: контекст выполнения
        - step_id: уникальный идентификатор шага (генерируется если не передан)
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        
        АЛГОРИТМ:
        1. Инициализация метрик шага
        2. Цикл попыток (max_retries)
        3. Применение таймаута через asyncio.wait_for
        4. При ошибке — retry/fallback/stop согласно on_error
        5. Сохранение метрик
        """
        step_id = step_id or f"step_{step_config.capability.replace('.', '_')}_{datetime.utcnow().timestamp()}"
        
        # Инициализация метрик
        metrics = StepMetrics(step_id=step_id, capability=step_config.capability)
        self._step_metrics[step_id] = metrics
        
        logger = self._get_logger()
        logger.info(
            f"Запуск шага {step_id}: {step_config.capability} "
            f"(timeout={step_config.timeout_ms}ms, retries={step_config.max_retries})",
            extra={"event_type": EventType.STEP_STARTED}
        )
        
        # Публикация события START
        await self._publish_event("STEP_STARTED", {
            "step_id": step_id,
            "capability": step_config.capability,
            "timeout_ms": step_config.timeout_ms,
            "max_retries": step_config.max_retries
        })
        
        last_error: Optional[Exception] = None
        last_result: Optional[ExecutionResult] = None
        
        for attempt in range(1, step_config.max_retries + 2):  # +1 для первой попытки
            attempt_start = datetime.utcnow()
            
            try:
                # Создание записи о попытке
                attempt_record = StepAttempt(
                    attempt_number=attempt,
                    started_at=attempt_start,
                    status=StepExecutionStatus.RUNNING
                )
                
                # Выполнение с таймаутом
                timeout_seconds = step_config.get_timeout_seconds()
                logger.debug(
                    f"Попытка {attempt}/{step_config.max_retries + 1} "
                    f"(timeout={timeout_seconds}s)",
                    extra={"event_type": EventType.DEBUG}
                )
                
                result = await asyncio.wait_for(
                    self._execute_capability(step_config.capability, parameters, context),
                    timeout=timeout_seconds
                )
                
                # Успех
                attempt_completed = datetime.utcnow()
                attempt_record.completed_at = attempt_completed
                attempt_record.duration_ms = int((attempt_completed - attempt_start).total_seconds() * 1000)
                attempt_record.status = (
                    StepExecutionStatus.COMPLETED 
                    if result.status == ExecutionStatus.COMPLETED 
                    else StepExecutionStatus.FAILED
                )
                
                if result.status != ExecutionStatus.COMPLETED:
                    attempt_record.error = result.error
                
                metrics.add_attempt(attempt_record)
                
                if result.status == ExecutionStatus.COMPLETED:
                    logger.info(
                        f"Шаг {step_id} завершён успешно (попытка {attempt}, "
                        f"длительность={attempt_record.duration_ms}ms)",
                        extra={"event_type": EventType.STEP_COMPLETED}
                    )
                    
                    await self._publish_event("STEP_COMPLETED", {
                        "step_id": step_id,
                        "capability": step_config.capability,
                        "attempt": attempt,
                        "duration_ms": attempt_record.duration_ms
                    })
                    
                    return result
                
                # Результат не успешен, но это была последняя попытка
                last_result = result
                last_error = Exception(result.error or "Unknown error")
                
            except asyncio.TimeoutError:
                # Таймаут
                attempt_completed = datetime.utcnow()
                attempt_record.completed_at = attempt_completed
                attempt_record.duration_ms = int((attempt_completed - attempt_start).total_seconds() * 1000)
                attempt_record.status = StepExecutionStatus.TIMEOUT
                attempt_record.error = f"Timeout after {timeout_seconds}s"
                attempt_record.error_type = "TIMEOUT"
                
                metrics.add_attempt(attempt_record)
                
                logger.warning(
                    f"Таймаут шага {step_id} (попытка {attempt}, "
                    f"длительность={attempt_record.duration_ms}ms)",
                    extra={"event_type": EventType.WARNING}
                )
                
                await self._publish_event("STEP_TIMEOUT", {
                    "step_id": step_id,
                    "capability": step_config.capability,
                    "attempt": attempt,
                    "timeout_ms": step_config.timeout_ms
                })
                
                last_error = asyncio.TimeoutError(f"Step timed out after {timeout_seconds}s")
                
            except Exception as e:
                # Исключение
                attempt_completed = datetime.utcnow()
                attempt_record.completed_at = attempt_completed
                attempt_record.duration_ms = int((attempt_completed - attempt_start).total_seconds() * 1000)
                attempt_record.status = StepExecutionStatus.FAILED
                attempt_record.error = str(e)
                attempt_record.error_type = type(e).__name__
                
                metrics.add_attempt(attempt_record)
                
                logger.error(
                    f"Ошибка шага {step_id} (попытка {attempt}): {e}",
                    extra={"event_type": EventType.ERROR},
                    exc_info=True
                )
                
                await self._publish_event("STEP_ERROR", {
                    "step_id": step_id,
                    "capability": step_config.capability,
                    "attempt": attempt,
                    "error_type": type(e).__name__,
                    "error": str(e)
                })
                
                last_error = e
            
            # Обработка ошибки согласно стратегии (ПЕРЕД проверкой на исчерпание попыток)
            if step_config.on_error.value == "fallback" and step_config.has_fallback():
                logger.info(
                    f"Активация fallback для шага {step_id}: {step_config.fallback_capability}",
                    extra={"event_type": EventType.INFO}
                )
                
                await self._publish_event("STEP_FALLBACK_TRIGGERED", {
                    "step_id": step_id,
                    "capability": step_config.capability,
                    "fallback_capability": step_config.fallback_capability
                })
                
                # Попытка fallback
                try:
                    fallback_result = await self._execute_capability(
                        step_config.fallback_capability,
                        parameters,
                        context
                    )
                    
                    metrics.fallback_triggered = True
                    
                    if fallback_result.status == ExecutionStatus.COMPLETED:
                        logger.info(
                            f"Fallback успешен для шага {step_id}",
                            extra={"event_type": EventType.STEP_COMPLETED}
                        )
                        
                        await self._publish_event("STEP_FALLBACK_SUCCESS", {
                            "step_id": step_id,
                            "fallback_capability": step_config.fallback_capability
                        })
                        
                        return fallback_result
                    
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback не удался для шага {step_id}: {fallback_error}",
                        extra={"event_type": EventType.ERROR}
                    )
                    
                    await self._publish_event("STEP_FALLBACK_FAILED", {
                        "step_id": step_id,
                        "fallback_capability": step_config.fallback_capability,
                        "error": str(fallback_error)
                    })
                
                # Fallback не удался, продолжаем retry если есть
                metrics.fallback_triggered = False  # Сбрасываем, т.к. fallback не удался
            
            # Проверка: это была последняя попытка?
            if attempt > step_config.max_retries:
                break
            
            # Задержка перед следующей попыткой (exponential backoff)
            delay_seconds = step_config.get_retry_delay_seconds(attempt - 1)
            logger.debug(
                f"Задержка перед retry {attempt}: {delay_seconds:.2f}s",
                extra={"event_type": EventType.DEBUG}
            )
            await asyncio.sleep(delay_seconds)
        
        # Все попытки исчерпаны
        logger.error(
            f"Шаг {step_id} исчерпал все попытки ({step_config.max_retries + 1})",
            extra={"event_type": EventType.STEP_EXHAUSTED}
        )
        
        await self._publish_event("STEP_EXHAUSTED", {
            "step_id": step_id,
            "capability": step_config.capability,
            "total_attempts": metrics.total_attempts,
            "last_error": str(last_error) if last_error else None
        })
        
        # Возвращаем последний результат или создаём failure
        if last_result:
            return last_result
        
        return ExecutionResult.failure(
            error=f"Step exhausted after {metrics.total_attempts} attempts: {last_error}",
            metadata={
                "step_id": step_id,
                "capability": step_config.capability,
                "total_attempts": metrics.total_attempts,
                "metrics": metrics.to_dict()
            }
        )
    
    async def _execute_capability(
        self,
        capability_name: str,
        parameters: dict,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнить capability через SafeExecutor.
        
        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - parameters: параметры
        - context: контекст выполнения
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        """
        return await self.safe_executor.execute(
            capability_name=capability_name,
            parameters=parameters,
            context=context
        )
    
    async def _publish_event(self, event_type: str, data: dict):
        """
        Опубликовать событие в EventBus.
        
        ПАРАМЕТРЫ:
        - event_type: тип события
        - data: данные события
        """
        if not self.event_bus:
            return
        
        try:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            
            await self.event_bus.publish(
                EventType.DEBUG,  # Используем DEBUG как обёртку
                {
                    "event_type": event_type,
                    **data
                },
                session_id=self.session_id,
                agent_id=self.agent_id
            )
        except Exception as e:
            logger = self._get_logger()
            logger.debug(f"Не удалось опубликовать событие {event_type}: {e}")
    
    def get_step_metrics(self, step_id: str) -> Optional[StepMetrics]:
        """
        Получить метрики шага.
        
        ПАРАМЕТРЫ:
        - step_id: идентификатор шага
        
        ВОЗВРАЩАЕТ:
        - StepMetrics или None если шаг не найден
        """
        return self._step_metrics.get(step_id)
    
    def get_all_metrics(self) -> dict[str, StepMetrics]:
        """
        Получить все метрики шагов.
        
        ВОЗВРАЩАЕТ:
        - dict[step_id: StepMetrics]
        """
        return self._step_metrics.copy()

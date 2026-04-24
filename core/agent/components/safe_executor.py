"""
Безопасный исполнитель действий с network retry и step-конфигурацией.

АРХИТЕКТУРА (Этап 2 + Refactor v2.0):
- Обёртка над ActionExecutor для network retry
- ТОЛЬКО retry для TRANSIENT ошибок (timeout, connection)
- НЕ принимает решений о switch/abort/fail
- Запись ошибок в FailureMemory для Pattern
- Реализует таймауты, retry с экспоненциальным backoff, fallback-логику из StepExecutor

ОТВЕТСТВЕННОСТЬ:
- Выполнение действий через ActionExecutor
- Retry для временных ошибок (TRANSIENT)
- Запись в FailureMemory
- Применение конфигурации шага (timeout, retries, fallback)

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
safe_executor = SafeExecutor(
    executor=action_executor,
    failure_memory=FailureMemory(),
    max_retries=3
)

# Pattern сам читает failures и решает что делать
result = await safe_executor.execute_with_config(step_config, parameters, context)
"""
import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.infrastructure.logging.session import LoggingSession

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.errors.failure_memory import FailureMemory
from core.components.action_executor import ActionExecutor, ExecutionContext

if TYPE_CHECKING:
    from core.agent.models import StepConfig


class SafeExecutor:
    """
    Безопасный исполнитель действий с обработкой ошибок.
    
    ПРИНЦИПЫ:
    - Изоляция ошибок от основного потока выполнения
    - Классификация ошибок для правильных решений
    - Экспоненциальная задержка для retry
    - Запись в FailureMemory для анализа паттернов
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    safe_executor = SafeExecutor(
        executor=action_executor,
        failure_memory=FailureMemory()
    )
    
    result = await safe_executor.execute(
        capability_name="search.database",
        parameters={"query": "test"},
        context=context
    )
    
    if result.status == ExecutionStatus.FAILED:
        # Проверка рекомендации
        recommendation = result.metadata.get("recommendation")
        if recommendation == "switch_pattern":
            # Переключить паттерн
            pass
    """
    
    def __init__(
        self,
        executor: ActionExecutor,
        failure_memory: FailureMemory,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        jitter: bool = True,
        log_session: Optional['LoggingSession'] = None
    ):
        """
        Инициализация безопасного исполнителя.

        ПАРАМЕТРЫ:
        - executor: ActionExecutor для выполнения действий
        - failure_memory: FailureMemory для записи ошибок
        - max_retries: максимальное количество попыток
        - base_delay: базовая задержка (сек) для экспоненциального увеличения
        - max_delay: максимальная задержка (сек)
        - jitter: применять ли случайное изменение задержки
        - log_session: сессия логирования
        """
        self.executor = executor
        self.failure_memory = failure_memory
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self._log_session = log_session

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session или fallback."""
        if self._log_session and self._log_session.app_logger:
            return self._log_session.app_logger
        return logging.getLogger(__name__)
    
    async def execute_with_config(
        self,
        step_config: 'StepConfig',
        parameters: dict,
        context: ExecutionContext,
        step_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Выполнить шаг с применением конфигурации.
        
        ПАРАМЕТРЫ:
        - step_config: конфигурация шага (ОБЯЗАТЕЛЬНО)
        - parameters: параметры для capability
        - context: контекст выполнения
        - step_id: уникальный идентификатор шага
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        
        АЛГОРИТМ:
        1. Инициализация метрик шага
        2. Цикл попыток (max_retries из step_config)
        3. Применение таймаута через asyncio.wait_for
        4. При ошибке — retry/fallback/stop согласно on_error
        5. Сохранение метрик
        
        FAIL-FAST: Если step_config не передан — выбрасывается ValueError
        """
        if step_config is None:
            raise ValueError("StepConfig required")
        
        step_id = step_id or f"step_{step_config.capability.replace('.', '_')}_{datetime.utcnow().timestamp()}"
        
        logger = self._get_logger()
        logger.info(
            f"Запуск шага {step_id}: {step_config.capability} "
            f"(timeout={step_config.timeout_ms}ms, retries={step_config.max_retries})"
        )
        
        last_error: Optional[Exception] = None
        last_result: Optional[ExecutionResult] = None
        
        for attempt in range(1, step_config.max_retries + 2):  # +1 для первой попытки
            attempt_start = datetime.utcnow()
            
            try:
                # Выполнение с таймаутом
                timeout_seconds = step_config.get_timeout_seconds()
                logger.debug(
                    f"Попытка {attempt}/{step_config.max_retries + 1} "
                    f"(timeout={timeout_seconds}s)"
                )
                
                result = await asyncio.wait_for(
                    self._execute_capability(step_config.capability, parameters, context),
                    timeout=timeout_seconds
                )
                
                if result.status == ExecutionStatus.COMPLETED:
                    logger.info(
                        f"Шаг {step_id} завершён успешно (попытка {attempt})"
                    )
                    return result
                
                # Результат не успешен, но это была последняя попытка
                last_result = result
                last_error = Exception(result.error or "Unknown error")
                
            except asyncio.TimeoutError:
                # Таймаут
                logger.warning(
                    f"Таймаут шага {step_id} (попытка {attempt})"
                )
                last_error = asyncio.TimeoutError(f"Step timed out after {timeout_seconds}s")
                
            except Exception as e:
                # Исключение
                logger.error(
                    f"Ошибка шага {step_id} (попытка {attempt}): {e}",
                    exc_info=True
                )
                last_error = e
            
            # Обработка ошибки согласно стратегии (ПЕРЕД проверкой на исчерпание попыток)
            if step_config.on_error.value == "fallback" and step_config.has_fallback():
                logger.info(
                    f"Активация fallback для шага {step_id}: {step_config.fallback_capability}"
                )
                
                # Попытка fallback
                try:
                    fallback_result = await self._execute_capability(
                        step_config.fallback_capability,
                        parameters,
                        context
                    )
                    
                    if fallback_result.status == ExecutionStatus.COMPLETED:
                        logger.info(
                            f"Fallback успешен для шага {step_id}"
                        )
                        return fallback_result
                    
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback не удался для шага {step_id}: {fallback_error}"
                    )
                
                # Fallback не удался, продолжаем retry если есть
            
            # Проверка: это была последняя попытка?
            if attempt > step_config.max_retries:
                break
            
            # Задержка перед следующей попыткой (exponential backoff)
            delay_seconds = step_config.get_retry_delay_seconds(attempt - 1)
            logger.debug(
                f"Задержка перед retry {attempt}: {delay_seconds:.2f}s"
            )
            await asyncio.sleep(delay_seconds)
        
        # Все попытки исчерпаны
        logger.error(
            f"Шаг {step_id} исчерпал все попытки ({step_config.max_retries + 1})"
        )
        
        # Возвращаем последний результат или создаём failure
        if last_result:
            return last_result
        
        return ExecutionResult.failure(
            error=f"Step exhausted after {attempt} attempts: {last_error}",
            metadata={
                "step_id": step_id,
                "capability": step_config.capability,
                "total_attempts": attempt
            }
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Рассчитать задержку перед retry.
        
        ПАРАМЕТРЫ:
        - attempt: номер попытки (0-based)
        
        ВОЗВРАЩАЕТ:
        - float: задержка в секундах
        
        ФОРМУЛА:
        delay = min(base_delay * (2 ^ attempt), max_delay) + jitter
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        if self.jitter:
            # Добавляем случайный jitter от 50% до 150%
            delay *= random.uniform(0.5, 1.5)
        
        return delay
    
    def get_failure_memory(self) -> FailureMemory:
        """
        Получить FailureMemory для внешней проверки.
        
        ВОЗВРАЩАЕТ:
        - FailureMemory: экземпляр памяти ошибок
        """
        return self.failure_memory
    
    async def _execute_capability(
        self,
        capability_name: str,
        parameters: dict,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнить capability через ActionExecutor.
        
        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - parameters: параметры
        - context: контекст выполнения
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат выполнения
        """
        return await self.executor.execute_action(
            action_name=capability_name,
            parameters=parameters,
            context=context
        )

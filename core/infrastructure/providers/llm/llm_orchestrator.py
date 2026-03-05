"""
LLMOrchestrator - централизованное управление вызовами LLM с расширенным логированием.

АРХИТЕКТУРНАЯ РОЛЬ:
- Инкапсулирует пул потоков/процессов для синхронных LLM вызовов
- Управляет таймаутами и повторными попытками
- Отслеживает активные вызовы и предотвращает утечку ресурсов
- Предоставляет единый интерфейс для всех компонентов
- Возвращает структурированные ответы с полем error вместо исключений
- Централизованное логирование всех вызовов LLM
- Публикация событий для интеграции с системой мониторинга

ПРОБЛЕМА КОТОРУЮ РЕШАЕТ:
При использовании asyncio.wait_for с run_in_executor:
1. При таймауте исключение пробрасывается вверх
2. Фоновый поток продолжает выполнение и потребляет ресурсы
3. Результат вызова теряется
4. Пул потоков может переполниться "висячими" задачами
5. Нет наблюдаемости и возможности отладки

РЕШЕНИЕ:
1. Реестр активных вызовов с отслеживанием статуса
2. При таймауте вызов помечается как "timed_out", но поток завершается
3. Когда поток завершается, проверяем статус и логируем опоздание
4. Агент получает StructuredLLMResponse с error вместо исключения
5. Полное логирование всех вызовов с correlation_id
6. Интеграция с EventBus для событий LLM_PROMPT_GENERATED и LLM_RESPONSE_RECEIVED
7. Метрики для мониторинга производительности
"""
import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    StructuredLLMResponse,
    RawLLMResponse,
    StructuredOutputConfig
)
from core.infrastructure.logging import EventBusLogger
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.providers.llm.json_parser import (
    validate_structured_response,
    schema_to_pydantic_model,
    extract_json_from_response
)
from pydantic import BaseModel, ValidationError
import json
from json import JSONDecodeError


class CallStatus(str, Enum):
    """Статусы LLM вызова."""
    PENDING = "pending"           # Ожидает запуска
    RUNNING = "running"           # Выполняется
    COMPLETED = "completed"       # Успешно завершён
    TIMED_OUT = "timed_out"       # Превышен таймаут (но поток ещё работает)
    FAILED = "failed"             # Ошибка выполнения
    CANCELLED = "cancelled"       # Отменён пользователем


@dataclass
class RetryAttempt:
    """Информация о попытке структурированного вывода."""
    attempt_number: int
    prompt: str
    raw_response: Optional[str]
    success: bool
    error_type: Optional[str]  # "json_error", "validation_error", "incomplete", "timeout"
    error_message: Optional[str]
    duration: float
    tokens_used: int = 0


@dataclass
class LLMMetrics:
    """Метрики LLM вызовов."""
    total_calls: int = 0
    completed_calls: int = 0
    timed_out_calls: int = 0
    failed_calls: int = 0
    orphaned_calls: int = 0  # Вызовы завершившиеся после таймаута
    total_generation_time: float = 0.0
    total_wait_time: float = 0.0  # Время ожидания в таймаутах
    
    # Метрики для структурированного вывода
    structured_calls: int = 0
    structured_success: int = 0
    structured_retries: int = 0  # Общее количество повторных попыток
    total_retry_attempts: int = 0  # Сумма всех попыток по всем вызовам

    @property
    def avg_generation_time(self) -> float:
        """Среднее время генерации для успешных вызовов."""
        if self.completed_calls == 0:
            return 0.0
        return self.total_generation_time / self.completed_calls

    @property
    def timeout_rate(self) -> float:
        """Процент таймаутов."""
        if self.total_calls == 0:
            return 0.0
        return self.timed_out_calls / self.total_calls

    @property
    def orphan_rate(self) -> float:
        """Процент "брошенных" вызовов."""
        if self.total_calls == 0:
            return 0.0
        return self.orphaned_calls / self.total_calls

    @property
    def structured_success_rate(self) -> float:
        """Процент успешных структурированных вызовов."""
        if self.structured_calls == 0:
            return 0.0
        return self.structured_success / self.structured_calls

    @property
    def avg_retries_per_call(self) -> float:
        """Среднее количество попыток на вызов."""
        if self.structured_calls == 0:
            return 0.0
        return self.total_retry_attempts / self.structured_calls

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "total_calls": self.total_calls,
            "completed_calls": self.completed_calls,
            "timed_out_calls": self.timed_out_calls,
            "failed_calls": self.failed_calls,
            "orphaned_calls": self.orphaned_calls,
            "avg_generation_time": round(self.avg_generation_time, 3),
            "timeout_rate": round(self.timeout_rate, 3),
            "orphan_rate": round(self.orphan_rate, 3),
            # Метрики структурированного вывода
            "structured_calls": self.structured_calls,
            "structured_success": self.structured_success,
            "structured_success_rate": round(self.structured_success_rate, 3),
            "total_retry_attempts": self.total_retry_attempts,
            "avg_retries_per_call": round(self.avg_retries_per_call, 2)
        }


@dataclass
class CallRecord:
    """Запись об активном LLM вызове с полным контекстом."""
    call_id: str
    request: LLMRequest
    status: CallStatus = CallStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    timeout: Optional[float] = None
    error: Optional[str] = None
    result: Optional[LLMResponse] = None
    thread_name: Optional[str] = None
    
    # Контекст для трассировки
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    step_number: Optional[int] = None
    phase: Optional[str] = None  # "think", "act", etc.
    goal: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Длительность вызова в секундах."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для логирования."""
        return {
            "call_id": self.call_id,
            "capability_name": self.request.capability_name,
            "status": self.status.value,
            "duration": round(self.duration, 3) if self.duration else None,
            "timeout": self.timeout,
            "error": self.error,
            "prompt_length": len(self.request.prompt),
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "step_number": self.step_number,
            "phase": self.phase
        }


class LLMOrchestrator:
    """
    Централизованный оркестратор для управления LLM вызовами с расширенным логированием.

    ПРИНЦИПЫ РАБОТЫ:
    1. Все вызовы регистрируются в реестре с уникальным ID
    2. При таймауте вызов помечается как timed_out, но поток не прерывается
    3. Когда поток завершается, проверяем статус:
       - Если timed_out -> логируем опоздание, результат отбрасываем
       - Если running -> завершаем успешно
    4. Периодическая очистка старых записей
    5. Метрики для мониторинга здоровья системы
    6. Полное логирование с трассировкой по сессиям и шагам агента

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    orchestrator = LLMOrchestrator(event_bus, max_workers=4)
    await orchestrator.initialize()

    # Вызов с таймаутом и контекстом
    response = await orchestrator.execute(
        request=request,
        timeout=60.0,
        provider=llm_provider,
        session_id="session_123",
        agent_id="agent_001",
        step_number=5,
        phase="think"
    )
    if response.metadata.get('error'):
        # Обрабатываем ошибку без падения агента
        return BehaviorDecision.switch_to_fallback(reason=response.metadata['error'])

    await orchestrator.shutdown()
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        max_workers: int = 4,
        cleanup_interval: float = 60.0,
        max_pending_calls: int = 100
    ):
        """
        Инициализация оркестратора.

        ПАРАМЕТРЫ:
        - event_bus: Шина событий для логирования
        - max_workers: Максимальное количество потоков в пуле
        - cleanup_interval: Интервал очистки старых записей (секунды)
        - max_pending_calls: Максимальное количество ожидающих вызовов
        """
        self._event_bus = event_bus
        self._max_workers = max_workers
        self._cleanup_interval = cleanup_interval
        self._max_pending_calls = max_pending_calls

        # Пул потоков для синхронных LLM вызовов
        self._executor: Optional[ThreadPoolExecutor] = None

        # Реестр активных вызовов
        self._pending_calls: Dict[str, CallRecord] = {}

        # Метрики
        self._metrics = LLMMetrics()

        # Задачи фоновой очистки
        self._cleanup_task: Optional[asyncio.Task] = None

        # Логгер (инициализируется в initialize)
        self._logger: Optional[EventBusLogger] = None

        # Флаг работы
        self._running = False

        # Блокировка для потокобезопасности реестра
        self._lock = asyncio.Lock()

        # Счётчик для генерации ID
        self._call_counter = 0
    
    async def initialize(self) -> bool:
        """
        Инициализация оркестратора.
        
        ВОЗВРАЩАЕТ:
        - bool: True если успешно
        """
        try:
            # Создание пула потоков
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix='llm_orchestrator'
            )
            
            # Создание логгера
            self._logger = EventBusLogger(
                event_bus=self._event_bus,
                session_id="system",
                agent_id="system",
                component="LLMOrchestrator"
            )
            
            # Запуск фоновой задачи очистки
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            await self._logger.info(
                f"LLMOrchestrator инициализирован: max_workers={self._max_workers}, "
                f"cleanup_interval={self._cleanup_interval}с"
            )
            
            return True
            
        except Exception as e:
            if self._logger:
                await self._logger.error(f"Ошибка инициализации LLMOrchestrator: {e}")
            return False
    
    async def shutdown(self) -> None:
        """
        Корректное завершение работы оркестратора.
        """
        try:
            self._running = False
            
            # Остановка задачи очистки
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Остановка пула потоков
            if self._executor:
                self._executor.shutdown(wait=True, cancel_futures=False)
                self._executor = None
            
            # Логируем статистику
            if self._logger:
                metrics = self._metrics.to_dict()
                await self._logger.info(
                    f"LLMOrchestrator завершён. Метрики: {metrics}"
                )
            
            await self._logger.info("LLMOrchestrator остановлен")
            
        except Exception as e:
            if self._logger:
                await self._logger.error(f"Ошибка при shutdown LLMOrchestrator: {e}")
    
    async def execute(
        self,
        request: LLMRequest,
        timeout: Optional[float] = None,
        provider: Any = None,
        capability_name: Optional[str] = None,
        # Контекст для трассировки
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None,
        phase: Optional[str] = None,
        goal: Optional[str] = None
    ) -> LLMResponse:
        """
        Выполнение LLM вызова с управлением таймаутом и расширенным логированием.

        ВАЖНО: Не бросает исключения при таймауте! Возвращает LLMResponse с error.

        ПАРАМЕТРЫ:
        - request: Запрос к LLM
        - timeout: Таймаут ожидания (секунды). Если None - используется timeout из request
        - provider: LLM провайдер для вызова
        - capability_name: Имя capability (для логирования)
        - session_id: ID сессии для трассировки
        - agent_id: ID агента для трассировки
        - step_number: Номер шага агента
        - phase: Фаза выполнения ("think", "act")
        - goal: Цель выполнения

        ВОЗВРАЩАЕТ:
        - LLMResponse: Результат вызова (с полем metadata.error при ошибке)
        """
        # Генерация уникального ID вызова
        call_id = self._generate_call_id()

        # Проверка лимита ожидающих вызовов
        async with self._lock:
            pending_count = sum(
                1 for r in self._pending_calls.values()
                if r.status == CallStatus.PENDING
            )
            if pending_count >= self._max_pending_calls:
                return LLMResponse(
                    content="",
                    model="orchestrator",
                    tokens_used=0,
                    generation_time=0.0,
                    finish_reason="error",
                    metadata={
                        "error": f"Превышен лимит ожидающих вызовов ({self._max_pending_calls})",
                        "call_id": call_id
                    }
                )

            # Регистрация вызова в реестре с полным контекстом
            call_record = CallRecord(
                call_id=call_id,
                request=request,
                status=CallStatus.PENDING,
                timeout=timeout,
                session_id=session_id,
                agent_id=agent_id,
                step_number=step_number,
                phase=phase,
                goal=goal
            )
            self._pending_calls[call_id] = call_record

        # Обновление метрик
        self._metrics.total_calls += 1

        # Логирование начала вызова
        await self._log_call_start(call_record)

        try:
            # Запуск выполнения
            return await self._execute_with_timeout(
                call_id=call_id,
                request=request,
                timeout=timeout,
                provider=provider,
                call_record=call_record
            )

        finally:
            # Очистка записи (не сразу, чтобы сохранить метрики)
            asyncio.create_task(self._schedule_cleanup(call_id))

    async def _log_call_start(self, record: CallRecord) -> None:
        """Логирование начала LLM вызова."""
        if not self._logger:
            return

        await self._logger.info(
            f"🧩 LLM вызов | call_id={record.call_id} | "
            f"session={record.session_id} | agent={record.agent_id} | "
            f"step={record.step_number} | phase={record.phase} | "
            f"prompt_len={len(record.request.prompt)} | "
            f"timeout={record.timeout}s"
        )

        # Публикация события LLM_PROMPT_GENERATED
        await self._publish_prompt_event(record)

    async def execute_structured(
        self,
        request: LLMRequest,
        provider: Any,
        max_retries: int = 3,
        attempt_timeout: Optional[float] = None,
        total_timeout: Optional[float] = None,
        # Контекст для трассировки
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None,
        phase: Optional[str] = None,
        goal: Optional[str] = None
    ) -> StructuredLLMResponse:
        """
        Выполнение LLM вызова со структурированным выводом и повторными попытками.

        АРХИТЕКТУРА:
        1. Первичный запрос с указанием JSON схемы
        2. Парсинг и валидация ответа
        3. При ошибке - формирование corrective prompt с обратной связью
        4. Повтор до max_retries или успеха
        5. Возврат StructuredLLMResponse с историей попыток

        ПАРАМЕТРЫ:
        - request: Запрос к LLM (должен иметь structured_output)
        - provider: LLM провайдер
        - max_retries: Максимальное количество попыток (по умолчанию 3)
        - attempt_timeout: Таймаут на одну попытку (секунды)
        - total_timeout: Общий таймаут на все попытки (секунды)
        - session_id, agent_id, step_number, phase, goal: Контекст трассировки

        ВОЗВРАЩАЕТ:
        - StructuredLLMResponse: Результат с историей попыток
        """
        if not request.structured_output:
            return StructuredLLMResponse(
                parsed_content=None,  # type: ignore
                raw_response=RawLLMResponse(
                    content="",
                    model="orchestrator",
                    tokens_used=0,
                    generation_time=0.0
                ),
                parsing_attempts=0,
                validation_errors=[{"error": "structured_output не указан в запросе"}]
            )

        # Генерация ID вызова
        call_id = self._generate_call_id()
        start_time = time.time()

        # Обновление метрик
        self._metrics.structured_calls += 1

        # История попыток
        attempts: List[RetryAttempt] = []
        last_error: Optional[str] = None
        current_request = request

        # Логирование начала структурированного вызова
        await self._log_structured_start(call_id, request, max_retries, session_id)

        try:
            for attempt_num in range(1, max_retries + 1):
                # Проверка общего таймаута
                if total_timeout:
                    elapsed = time.time() - start_time
                    if elapsed >= total_timeout:
                        await self._log_structured_failure(
                            call_id, attempt_num, "total_timeout",
                            f"Превышен общий таймаут {total_timeout}s"
                        )
                        break

                # Выполнение попытки
                attempt = await self._execute_structured_attempt(
                    call_id=call_id,
                    request=current_request,
                    provider=provider,
                    attempt_num=attempt_num,
                    attempt_timeout=attempt_timeout,
                    session_id=session_id,
                    agent_id=agent_id,
                    step_number=step_number,
                    phase=phase
                )

                attempts.append(attempt)
                self._metrics.total_retry_attempts += 1

                if attempt.success:
                    # Успех!
                    self._metrics.structured_success += 1
                    await self._log_structured_success(
                        call_id, attempt_num, attempt.duration, session_id
                    )

                    # Возвращаем успешный ответ
                    return StructuredLLMResponse(
                        parsed_content=attempt.raw_response,  # type: ignore
                        raw_response=RawLLMResponse(
                            content=attempt.raw_response or "",
                            model="structured",
                            tokens_used=attempt.tokens_used,
                            generation_time=attempt.duration
                        ),
                        parsing_attempts=attempt_num,
                        validation_errors=[],
                        provider_native_validation=False
                    )
                else:
                    # Неудача - логируем и готовим следующую попытку
                    last_error = attempt.error_message
                    self._metrics.structured_retries += 1

                    await self._log_structured_retry(
                        call_id, attempt_num, attempt.error_type,
                        attempt.error_message, len(attempts) < max_retries
                    )

                    # Формируем corrective prompt для следующей попытки
                    if attempt_num < max_retries:
                        current_request = self._build_corrective_prompt(
                            original_request=request,
                            current_request=current_request,
                            failed_response=attempt.raw_response,
                            error_type=attempt.error_type,
                            error_message=attempt.error_message
                        )

            # Все попытки исчерпаны
            await self._log_structured_exhausted(
                call_id, len(attempts), last_error, session_id
            )

            return StructuredLLMResponse(
                parsed_content=None,  # type: ignore
                raw_response=RawLLMResponse(
                    content="",
                    model="structured_error",
                    tokens_used=0,
                    generation_time=time.time() - start_time
                ),
                parsing_attempts=len(attempts),
                validation_errors=[
                    {"attempt": i + 1, "error": a.error_type, "message": a.error_message}
                    for i, a in enumerate(attempts)
                ],
                provider_native_validation=False
            )

        except Exception as e:
            # Критическая ошибка
            await self._log_structured_error(call_id, str(e), session_id)
            return StructuredLLMResponse(
                parsed_content=None,  # type: ignore
                raw_response=RawLLMResponse(
                    content="",
                    model="structured_exception",
                    tokens_used=0,
                    generation_time=time.time() - start_time
                ),
                parsing_attempts=len(attempts),
                validation_errors=[{"error": "exception", "message": str(e)}],
                provider_native_validation=False
            )

    async def _execute_structured_attempt(
        self,
        call_id: str,
        request: LLMRequest,
        provider: Any,
        attempt_num: int,
        attempt_timeout: Optional[float],
        session_id: Optional[str],
        agent_id: Optional[str],
        step_number: Optional[int],
        phase: Optional[str]
    ) -> RetryAttempt:
        """
        Выполнение одной попытки структурированного вывода.

        ВОЗВРАЩАЕТ:
        - RetryAttempt: Результат попытки
        """
        start_time = time.time()
        effective_timeout = attempt_timeout or 60.0  # Default 60s per attempt

        try:
            # Выполняем вызов через оркестратор
            response = await self.execute(
                request=request,
                timeout=effective_timeout,
                provider=provider,
                session_id=session_id,
                agent_id=agent_id,
                step_number=step_number,
                phase=phase
            )

            duration = time.time() - start_time

            # Проверка на ошибку в ответе
            if response.finish_reason == "error":
                error_msg = response.metadata.get('error', 'Unknown error') if response.metadata else 'Unknown error'
                return RetryAttempt(
                    attempt_number=attempt_num,
                    prompt=request.prompt,
                    raw_response=None,
                    success=False,
                    error_type="llm_error",
                    error_message=error_msg,
                    duration=duration
                )

            # Парсинг и валидация ответа
            raw_content = response.content
            validation_result = self._validate_structured_response(
                raw_content=raw_content,
                schema=request.structured_output.schema_def if request.structured_output else None
            )

            if validation_result["success"]:
                return RetryAttempt(
                    attempt_number=attempt_num,
                    prompt=request.prompt,
                    raw_response=raw_content,
                    success=True,
                    error_type=None,
                    error_message=None,
                    duration=duration,
                    tokens_used=response.tokens_used
                )
            else:
                return RetryAttempt(
                    attempt_number=attempt_num,
                    prompt=request.prompt,
                    raw_response=raw_content,
                    success=False,
                    error_type=validation_result["error_type"],
                    error_message=validation_result["error_message"],
                    duration=duration,
                    tokens_used=response.tokens_used
                )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return RetryAttempt(
                attempt_number=attempt_num,
                prompt=request.prompt,
                raw_response=None,
                success=False,
                error_type="timeout",
                error_message=f"Attempt {attempt_num} timed out after {effective_timeout}s",
                duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            return RetryAttempt(
                attempt_number=attempt_num,
                prompt=request.prompt,
                raw_response=None,
                success=False,
                error_type="exception",
                error_message=str(e),
                duration=duration
            )

    def _validate_structured_response(
        self,
        raw_content: str,
        schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Валидация структурированного ответа.

        ПРОВЕРКИ:
        1. JSON парсинг
        2. Соответствие схеме через Pydantic (если указана)
        3. Полнота ответа (не обрезан ли)

        ВОЗВРАЩАЕТ:
        - Dict с полями: success, error_type, error_message
        """
        # Проверка 1: JSON парсинг
        try:
            parsed = json.loads(raw_content)
        except JSONDecodeError as e:
            return {
                "success": False,
                "error_type": "json_error",
                "error_message": f"JSON парсинг не удался: {str(e)}"
            }

        # Проверка 2: Соответствие схеме через Pydantic
        if schema:
            try:
                # Создаём динамическую Pydantic модель из схемы
                from pydantic import ValidationError, create_model
                from typing import Any, List, Optional, Union, Dict
                
                def schema_field_to_type(field_schema: Dict[str, Any], field_name: str = "field"):
                    """Преобразует JSON Schema поле в Python тип."""
                    field_type = field_schema.get('type')
                    
                    if field_type == 'string':
                        return str
                    elif field_type == 'integer':
                        return int
                    elif field_type == 'number':
                        return float
                    elif field_type == 'boolean':
                        return bool
                    elif field_type == 'array':
                        items = field_schema.get('items', {})
                        item_type = schema_field_to_type(items, f"{field_name}_item")
                        return List[item_type]
                    elif field_type == 'object':
                        # Рекурсивное создание вложенной модели
                        nested_model = schema_to_pydantic_model(field_schema, f"{field_name.title()}Object")
                        return nested_model
                    else:
                        return Any
                
                def schema_to_pydantic_model(schema: Dict[str, Any], model_name: str = "DynamicModel"):
                    """Создаёт Pydantic модель из JSON Schema."""
                    properties = schema.get('properties', {})
                    required = set(schema.get('required', []))
                    
                    fields = {}
                    for field_name, field_schema in properties.items():
                        field_type = schema_field_to_type(field_schema, field_name)
                        is_required = field_name in required
                        
                        if is_required:
                            fields[field_name] = (field_type, ...)
                        else:
                            # Опциональное поле с default=None
                            from typing import Optional
                            fields[field_name] = (Optional[field_type], None)
                    
                    return create_model(model_name, **fields)
                
                # Создаём модель из схемы
                DynamicModel = schema_to_pydantic_model(schema, "StructuredOutput")
                
                # Валидируем через Pydantic
                parsed_content = DynamicModel.model_validate(parsed)
                
                # Успех - валидация пройдена
                return {
                    "success": True,
                    "error_type": None,
                    "error_message": None,
                    "parsed": parsed_content  # Возвращаем валидированную модель
                }
                
            except ValidationError as e:
                # Детальное сообщение об ошибке валидации
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error.get('loc', []))
                    msg = error.get('msg', 'validation error')
                    error_details.append(f"{field}: {msg}")
                
                return {
                    "success": False,
                    "error_type": "validation_error",
                    "error_message": f"Валидация схемы не пройдена: {'; '.join(error_details)}"
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error_type": "validation_error",
                    "error_message": f"Ошибка валидации схемы: {type(e).__name__}: {str(e)}"
                }
        else:
            # Схема не указана - логируем предупреждение
            if hasattr(self, '_logger') and self._logger:
                if hasattr(self._logger, 'warning_sync'):
                    self._logger.warning_sync("Schema not provided for structured output validation - only JSON parsing performed")
            
            # Всё равно пытаемся распарсить JSON
            return {
                "success": True,
                "error_type": None,
                "error_message": None,
                "parsed": parsed
            }

        # Проверка 3: Полнота ответа (эвристика)
        if raw_content and not raw_content.strip().endswith('}'):
            # Возможно ответ обрезан
            if len(raw_content) > 100:  # Не срабатывает на коротких ответах
                return {
                    "success": False,
                    "error_type": "incomplete",
                    "error_message": "Ответ может быть обрезан (не закрывающая скобка)"
                }

        return {
            "success": True,
            "error_type": None,
            "error_message": None
        }

    def _build_corrective_prompt(
        self,
        original_request: LLMRequest,
        current_request: LLMRequest,
        failed_response: Optional[str],
        error_type: Optional[str],
        error_message: Optional[str]
    ) -> LLMRequest:
        """
        Формирование corrective prompt с обратной связью.

        ВКЛЮЧАЕТ:
        - Исходный запрос
        - JSON схему (явно!)
        - Неудачный ответ (если есть)
        - Описание ошибки
        - Инструкцию исправить

        ВОЗВРАЩАЕТ:
        - Новый LLMRequest с обновлённым промптом
        """
        import json
        
        error_descriptions = {
            "json_error": "Ваш ответ не является валидным JSON. Пожалуйста, исправьте синтаксис JSON.",
            "validation_error": "Ваш ответ не соответствует ожидаемой схеме. Проверьте наличие всех обязательных полей и типов данных.",
            "incomplete": "Ваш ответ был обрезан. Пожалуйста, предоставьте полный ответ.",
            "timeout": "Предыдущая попытка превысила время ожидания. Пожалуйста, предоставьте более краткий ответ."
        }

        base_error = error_descriptions.get(error_type, f"Произошла ошибка: {error_message}")
        
        # Получаем схему для добавления в промпт
        schema_def = current_request.structured_output.schema_def if current_request.structured_output else None

        # Формируем corrective prompt с ЯВНЫМ указанием схемы
        schema_section = ""
        if schema_def:
            schema_section = f"""
### ТРЕБУЕМЫЙ ФОРМАТ ОТВЕТА (JSON Schema) ###
Твой ответ ДОЛЖЕН быть валидным JSON, соответствующим этой схеме:

```json
{json.dumps(schema_def, indent=2, ensure_ascii=False)}
```

⚠️ **ВАЖНО:**
- ОТВЕТЬ ТОЛЬКО JSON
- Не добавляй никаких объяснений
- Все поля из "required" обязательны
- Соблюдай типы данных

"""

        # Формируем основной corrective prompt
        corrective_prompt = f"""{original_request.prompt}

{schema_section}---
ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ
---

Ошибка: {base_error}

{f'Ваш ответ: {failed_response[:500]}...' if failed_response and len(failed_response) > 500 else f'Ваш ответ: {failed_response}' if failed_response else ''}

---
ИНСТРУКЦИЯ
---
Пожалуйста, исправьте ответ и верните ТОЛЬКО валидный JSON, соответствующий ожидаемой схеме выше.
Не добавляйте никаких пояснений, только JSON."""

        return LLMRequest(
            prompt=corrective_prompt,
            system_prompt=current_request.system_prompt,
            temperature=0.1,  # Снижаем температуру для точности
            max_tokens=min(current_request.max_tokens * 1.5, 2000),  # Увеличиваем max_tokens
            top_p=current_request.top_p,
            frequency_penalty=current_request.frequency_penalty,
            presence_penalty=current_request.presence_penalty,
            stop_sequences=current_request.stop_sequences,
            structured_output=current_request.structured_output,
            metadata=current_request.metadata,
            correlation_id=current_request.correlation_id,
            capability_name=current_request.capability_name
        )

    async def _log_structured_start(
        self,
        call_id: str,
        request: LLMRequest,
        max_retries: int,
        session_id: Optional[str]
    ) -> None:
        """Логирование начала структурированного вызова."""
        if not self._logger:
            return

        await self._logger.info(
            f"📋 Structured LLM | call_id={call_id} | "
            f"session={session_id} | max_retries={max_retries} | "
            f"schema={request.structured_output.output_model if request.structured_output else 'unknown'}"
        )

    async def _log_structured_success(
        self,
        call_id: str,
        attempt_num: int,
        duration: float,
        session_id: Optional[str]
    ) -> None:
        """Логирование успешного структурированного вызова."""
        if not self._logger:
            return

        await self._logger.info(
            f"✅ Structured SUCCESS | call_id={call_id} | "
            f"session={session_id} | attempt={attempt_num} | "
            f"duration={duration:.2f}s"
        )

    async def _log_structured_retry(
        self,
        call_id: str,
        attempt_num: int,
        error_type: Optional[str],
        error_message: Optional[str],
        will_retry: bool
    ) -> None:
        """Логирование неудачной попытки."""
        if not self._logger:
            return

        icon = "🔄" if will_retry else "⚠️"
        await self._logger.warning(
            f"{icon} Structured RETRY | call_id={call_id} | "
            f"attempt={attempt_num} | error={error_type} | "
            f"message={error_message[:100] if error_message else 'unknown'} | "
            f"will_retry={will_retry}"
        )

    async def _log_structured_exhausted(
        self,
        call_id: str,
        total_attempts: int,
        last_error: Optional[str],
        session_id: Optional[str]
    ) -> None:
        """Логирование исчерпания попыток."""
        if not self._logger:
            return

        await self._logger.error(
            f"❌ Structured EXHAUSTED | call_id={call_id} | "
            f"session={session_id} | total_attempts={total_attempts} | "
            f"last_error={last_error[:100] if last_error else 'unknown'}"
        )

    async def _log_structured_failure(
        self,
        call_id: str,
        attempt_num: int,
        failure_type: str,
        message: str
    ) -> None:
        """Логирование критической неудачи."""
        if not self._logger:
            return

        await self._logger.error(
            f"❌ Structured FAILURE | call_id={call_id} | "
            f"attempt={attempt_num} | type={failure_type} | "
            f"message={message[:100]}"
        )

    async def _log_structured_error(
        self,
        call_id: str,
        error: str,
        session_id: Optional[str]
    ) -> None:
        """Логирование исключения."""
        if not self._logger:
            return

        await self._logger.error(
            f"❌ Structured EXCEPTION | call_id={call_id} | "
            f"session={session_id} | error={error[:200]}"
        )

    async def _execute_with_timeout(
        self,
        call_id: str,
        request: LLMRequest,
        timeout: Optional[float],
        provider: Any,
        call_record: CallRecord
    ) -> LLMResponse:
        """
        Выполнение вызова с таймаутом и полным логированием.

        ВОЗВРАЩАЕТ:
        - LLMResponse: Результат вызова
        """
        start_time = time.time()

        # Обновление статуса
        async with self._lock:
            record = self._pending_calls[call_id]
            record.status = CallStatus.RUNNING
            record.start_time = start_time

        try:
            # Запуск в executor
            future = asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._sync_call_wrapper,
                call_id,
                request,
                provider,
                call_record
            )

            # Ожидание с таймаутом
            effective_timeout = timeout or self._get_default_timeout(request)
            result = await asyncio.wait_for(future, timeout=effective_timeout)

            # Успешное завершение
            async with self._lock:
                record = self._pending_calls[call_id]
                record.status = CallStatus.COMPLETED
                record.end_time = time.time()
                record.result = result

            # Обновление метрик
            self._metrics.completed_calls += 1
            self._metrics.total_generation_time += record.duration or 0

            # Логирование успешного завершения
            await self._log_call_success(record, result)

            return result

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time

            # Помечаем как timed_out (но поток продолжает работу!)
            async with self._lock:
                record = self._pending_calls[call_id]
                record.status = CallStatus.TIMED_OUT
                record.error = f"Timeout after {elapsed:.2f}s"

            # Обновление метрик
            self._metrics.timed_out_calls += 1
            self._metrics.total_wait_time += elapsed

            # Логирование таймаута
            await self._log_call_timeout(record, elapsed, effective_timeout)

            # Возвращаем ошибку вместо исключения
            return LLMResponse(
                content="",
                model="timeout",
                tokens_used=0,
                generation_time=elapsed,
                finish_reason="error",
                metadata={
                    "error": f"LLM timeout после {elapsed:.2f}с (лимит: {effective_timeout}с)",
                    "call_id": call_id,
                    "timeout": True
                }
            )

        except Exception as e:
            elapsed = time.time() - start_time

            # Помечаем как failed
            async with self._lock:
                record = self._pending_calls[call_id]
                record.status = CallStatus.FAILED
                record.end_time = time.time()
                record.error = str(e)

            # Обновление метрик
            self._metrics.failed_calls += 1

            # Логирование ошибки
            await self._log_call_error(record, e, elapsed)

            return LLMResponse(
                content="",
                model="error",
                tokens_used=0,
                generation_time=elapsed,
                finish_reason="error",
                metadata={
                    "error": str(e),
                    "call_id": call_id
                }
            )

    async def _log_call_success(self, record: CallRecord, result: LLMResponse) -> None:
        """Логирование успешного завершения вызова."""
        if not self._logger:
            return

        content_length = len(result.content) if result.content else 0
        await self._logger.info(
            f"✅ LLM ответ | call_id={record.call_id} | "
            f"session={record.session_id} | step={record.step_number} | "
            f"response_len={content_length} | tokens={result.tokens_used} | "
            f"duration={record.duration:.2f}s"
        )

        # Публикация события LLM_RESPONSE_RECEIVED
        await self._publish_response_event(record, result, record.duration or 0, success=True)

    async def _log_call_timeout(self, record: CallRecord, elapsed: float, timeout: float) -> None:
        """Логирование таймаута вызова."""
        if not self._logger:
            return

        await self._logger.warning(
            f"⏰ LLM TIMEOUT | call_id={record.call_id} | "
            f"session={record.session_id} | agent={record.agent_id} | "
            f"step={record.step_number} | phase={record.phase} | "
            f"elapsed={elapsed:.2f}s | timeout={timeout}s | "
            f"prompt_len={len(record.request.prompt)}"
        )

        # Публикация события LLM_CALL_FAILED с таймаутом
        await self._publish_response_event(
            record,
            None,
            elapsed,
            success=False,
            error_type="timeout",
            error_message=f"LLM timeout после {elapsed:.2f}с (лимит: {timeout}с)"
        )

    async def _log_call_error(self, record: CallRecord, error: Exception, elapsed: float) -> None:
        """Логирование ошибки вызова."""
        if not self._logger:
            return

        await self._logger.error(
            f"❌ LLM ERROR | call_id={record.call_id} | "
            f"session={record.session_id} | step={record.step_number} | "
            f"{type(error).__name__}: {str(error)[:200]} | elapsed={elapsed:.2f}s"
        )

        # Публикация события об ошибке
        await self._publish_response_event(
            record,
            None,
            elapsed,
            success=False,
            error_type=type(error).__name__,
            error_message=str(error)
        )

    def _sync_call_wrapper(
        self,
        call_id: str,
        request: LLMRequest,
        provider: Any,
        call_record: CallRecord
    ) -> Optional[LLMResponse]:
        """
        Обёртка для синхронного вызова LLM.

        Выполняется в потоке executor'а. Проверяет статус вызова после завершения.

        ПАРАМЕТРЫ:
        - call_id: ID вызова
        - request: Запрос к LLM
        - provider: LLM провайдер
        - call_record: Запись о вызове для обновления

        ВОЗВРАЩАЕТ:
        - LLMResponse или None если вызов был отменён
        """
        import threading
        thread_name = threading.current_thread().name

        # Сохраняем имя потока в записи
        if call_id in self._pending_calls:
            self._pending_calls[call_id].thread_name = thread_name

        try:
            # Синхронный вызов провайдера
            if not provider:
                raise ValueError("LLM provider не указан")

            # Вызываем _generate_impl напрямую (синхронная версия)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(provider._generate_impl(request))
            finally:
                loop.close()

            # ПРОВЕРКА: не истёк ли таймаут пока мы работали
            if call_id in self._pending_calls:
                record = self._pending_calls[call_id]
                if record.status == CallStatus.TIMED_OUT:
                    # Вызов завершился после таймаута - логируем опоздание
                    self._log_orphaned_call(record)
                    # Возвращаем None чтобы оркестратор знал что результат не нужен
                    return None

            return result

        except Exception as e:
            # Логируем ошибку в потоке
            if hasattr(self, '_logger') and self._logger:
                if hasattr(self._logger, 'error_sync'):
                    self._logger.error_sync(f"Ошибка в sync вызове {call_id}: {e}")
            raise

    def _log_orphaned_call(self, record: CallRecord) -> None:
        """
        Логирование "брошенного" вызова.

        Вызов завершился после таймаута - его результат никому не нужен.
        """
        # Обновление метрик
        self._metrics.orphaned_calls += 1

        # Логирование
        if self._logger and hasattr(self._logger, 'warning_sync'):
            self._logger.warning_sync(
                f"🗑️ ORPHANED CALL | call_id={record.call_id} | "
                f"завершился через {record.duration:.2f}с после таймаута | "
                f"session={record.session_id} | step={record.step_number} | "
                f"capability={record.request.capability_name}"
            )

        # Публикация события о позднем ответе
        if self._event_bus:
            asyncio.run_coroutine_threadsafe(
                self._publish_late_response_event(record),
                self._event_bus._loop
            )

    async def _publish_prompt_event(self, record: CallRecord) -> None:
        """Публикация события LLM_PROMPT_GENERATED."""
        if not self._event_bus:
            return

        await self._event_bus.publish(
            event_type=EventType.LLM_PROMPT_GENERATED,
            data={
                "call_id": record.call_id,
                "session_id": record.session_id,
                "agent_id": record.agent_id,
                "step_number": record.step_number,
                "phase": record.phase,
                "goal": record.goal,
                "capability_name": record.request.capability_name,
                "system_prompt": record.request.system_prompt or "",
                "user_prompt": record.request.prompt,
                "prompt_length": len(record.request.prompt),
                "temperature": record.request.temperature,
                "max_tokens": record.request.max_tokens,
                "timeout": record.timeout
            },
            source="LLMOrchestrator",
            correlation_id=record.call_id
        )

    async def _publish_response_event(
        self,
        record: CallRecord,
        result: Optional[LLMResponse],
        duration: float,
        success: bool,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Публикация события LLM_RESPONSE_RECEIVED."""
        if not self._event_bus:
            return

        # Извлекаем контент ответа
        response_content = ""
        if result and hasattr(result, 'content'):
            response_content = result.content or ""

        data = {
            "call_id": record.call_id,
            "session_id": record.session_id,
            "agent_id": record.agent_id,
            "step_number": record.step_number,
            "phase": record.phase,
            "success": success,
            "duration_ms": duration * 1000,
            "capability_name": record.request.capability_name,
            # Сырой ответ (JSON строка)
            "raw_response": response_content,
            "response_length": len(response_content) if response_content else 0
        }

        if success and result:
            # Пытаемся распарсить JSON для удобства чтения
            try:
                import json
                parsed = json.loads(response_content)
                # Сохраняем и сырой, и распарсенный ответ
                data["parsed_response"] = parsed
                data["response_preview"] = json.dumps(parsed, ensure_ascii=False, indent=2)[:500]
            except (json.JSONDecodeError, Exception):
                # Не JSON - сохраняем как текст
                data["response_preview"] = response_content[:500]
            
            data.update({
                "tokens_used": result.tokens_used,
                "model": result.model
            })
        else:
            data.update({
                "error_type": error_type,
                "error_message": error_message[:500] if error_message else None
            })

        await self._event_bus.publish(
            event_type=EventType.LLM_RESPONSE_RECEIVED,
            data=data,
            source="LLMOrchestrator",
            correlation_id=record.call_id
        )

    async def _publish_late_response_event(self, record: CallRecord) -> None:
        """Публикация события о позднем ответе (после таймаута)."""
        if not self._event_bus:
            return

        # Извлекаем контент ответа если доступен
        response_content = ""
        if record.result and hasattr(record.result, 'content'):
            response_content = record.result.content or ""

        data = {
            "call_id": record.call_id,
            "session_id": record.session_id,
            "agent_id": record.agent_id,
            "step_number": record.step_number,
            "late_response": True,
            "duration_ms": (record.duration or 0) * 1000,
            "capability_name": record.request.capability_name,
            "orphaned": True,
            # Сырой ответ (JSON строка)
            "raw_response": response_content,
            "response_length": len(response_content) if response_content else 0
        }

        # Пытаемся распарсить JSON для удобства чтения
        if response_content:
            try:
                import json
                parsed = json.loads(response_content)
                data["parsed_response"] = parsed
                data["response_preview"] = json.dumps(parsed, ensure_ascii=False, indent=2)[:500]
            except (json.JSONDecodeError, Exception):
                data["response_preview"] = response_content[:500]

        await self._event_bus.publish(
            event_type=EventType.LLM_RESPONSE_RECEIVED,
            data=data,
            source="LLMOrchestrator",
            correlation_id=record.call_id
        )
    
    async def _cleanup_loop(self) -> None:
        """
        Фоновая задача периодической очистки старых записей.
        """
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_old_records()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._logger:
                    await self._logger.error(f"Ошибка в cleanup loop: {e}")
    
    async def _cleanup_old_records(self, max_age: float = 300.0) -> int:
        """
        Очистка старых записей из реестра.
        
        ПАРАМЕТРЫ:
        - max_age: Максимальный возраст записи (секунды)
        
        ВОЗВРАЩАЕТ:
        - int: Количество удалённых записей
        """
        removed = 0
        now = time.time()
        
        async with self._lock:
            to_remove = []
            for call_id, record in self._pending_calls.items():
                # Удаляем завершённые вызовы старше max_age
                if record.end_time and (now - record.end_time) > max_age:
                    to_remove.append(call_id)
            
            for call_id in to_remove:
                del self._pending_calls[call_id]
                removed += 1
        
        if removed > 0 and self._logger:
            await self._logger.debug(f"Очищено {removed} старых записей")
        
        return removed
    
    async def _schedule_cleanup(self, call_id: str, delay: float = 60.0) -> None:
        """
        Отложенная очистка записи вызова.
        """
        await asyncio.sleep(delay)
        async with self._lock:
            if call_id in self._pending_calls:
                record = self._pending_calls[call_id]
                # Не удаляем если ещё выполняется
                if record.status not in (CallStatus.RUNNING, CallStatus.PENDING):
                    del self._pending_calls[call_id]
    
    def _generate_call_id(self) -> str:
        """Генерация уникального ID вызова."""
        self._call_counter += 1
        return f"llm_{int(time.time())}_{self._call_counter}"
    
    def _get_default_timeout(self, request: LLMRequest) -> float:
        """Получение таймаута по умолчанию."""
        # Если в request есть metadata с timeout, используем его
        if request.metadata and 'timeout' in request.metadata:
            return float(request.metadata['timeout'])
        # Иначе используем дефолтное значение
        return 120.0  # 2 минуты по умолчанию
    
    async def _publish_call_started(self, call_id: str, request: LLMRequest) -> None:
        """Публикация события начала вызова."""
        await self._event_bus.publish(
            event_type=EventType.LLM_CALL_STARTED,
            data={
                "call_id": call_id,
                "capability_name": request.capability_name,
                "prompt_length": len(request.prompt),
                "max_tokens": request.max_tokens,
                "temperature": request.temperature
            },
            source="LLMOrchestrator",
            correlation_id=call_id
        )
    
    async def _publish_call_completed(
        self,
        call_id: str,
        result: LLMResponse,
        duration: Optional[float]
    ) -> None:
        """Публикация события завершения вызова."""
        await self._event_bus.publish(
            event_type=EventType.LLM_CALL_COMPLETED,
            data={
                "call_id": call_id,
                "success": result.finish_reason != "error",
                "duration": duration,
                "tokens_used": result.tokens_used,
                "content_length": len(result.content) if result.content else 0
            },
            source="LLMOrchestrator",
            correlation_id=call_id
        )
    
    async def _publish_call_timeout(
        self,
        call_id: str,
        elapsed: float,
        timeout: float
    ) -> None:
        """Публикация события таймаута."""
        await self._event_bus.publish(
            event_type=EventType.LLM_CALL_FAILED,
            data={
                "call_id": call_id,
                "error_type": "timeout",
                "elapsed": elapsed,
                "timeout": timeout
            },
            source="LLMOrchestrator",
            correlation_id=call_id
        )
    
    async def _publish_call_failed(
        self,
        call_id: str,
        error: Exception,
        elapsed: float
    ) -> None:
        """Публикация события ошибки."""
        await self._event_bus.publish(
            event_type=EventType.ERROR_OCCURRED,
            data={
                "call_id": call_id,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "elapsed": elapsed
            },
            source="LLMOrchestrator",
            correlation_id=call_id
        )
    
    def get_metrics(self) -> LLMMetrics:
        """Получение текущих метрик."""
        return self._metrics
    
    def get_pending_calls(self) -> List[Dict[str, Any]]:
        """Получение списка активн��х вызовов."""
        return [
            record.to_dict()
            for record in self._pending_calls.values()
            if record.status in (CallStatus.RUNNING, CallStatus.PENDING)
        ]
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получение статуса здоровья оркестратора."""
        metrics = self._metrics.to_dict()
        pending = self.get_pending_calls()
        
        # Оценка здоровья
        status = "healthy"
        if metrics["timeout_rate"] > 0.5:
            status = "degraded"
        if metrics["timeout_rate"] > 0.8:
            status = "unhealthy"
        
        return {
            "status": status,
            "executor_running": self._executor is not None,
            "pending_calls": len(pending),
            "metrics": metrics,
            "recent_calls": pending[:10]  # Последние 10
        }

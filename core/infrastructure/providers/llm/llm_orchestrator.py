"""
LLMOrchestrator - централизованное управление вызовами LLM с расширенным логированием.

АРХИТЕКТУРНАЯ РОЛЬ:
- Маршрутизирует вызовы к LLM провайдерам
- Отслеживает активные вызовы и предотвращает утечку ресурсов
- Предоставляет единый интерфейс для всех компонентов
- Централизованное логирование всех вызовов LLM
- Публикация событий для интеграции с системой мониторинга
- Сбор метрик производительности

АРХИТЕКТУРА:
- Провайдеры сами управляют потоками (run_in_executor внутри провайдера)
- Оркестратор только маршрутизирует, логирует и собирает метрики
- Таймауты обрабатываются на уровне провайдера (где есть контекст модели)

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
orchestrator = LLMOrchestrator(event_bus)
await orchestrator.initialize()

response = await orchestrator.execute(
    request=request,
    provider=llm_provider,
    session_id="session_123",
    agent_id="agent_001",
    step_number=5,
    phase="think"
)

await orchestrator.shutdown()
"""
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List

from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    RawLLMResponse
)
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.providers.llm.json_parser import (
    validate_structured_response
)
from core.errors.exceptions import StructuredOutputError


# ========================================================================
# Утилиты для динамического создания Pydantic моделей из JSON Schema
# ========================================================================

def _create_model_from_schema(
    model_name: str,
    schema: dict,
    defs: dict
) -> type:
    """
    Создаёт динамическую Pydantic модель из JSON Schema с поддержкой $ref.

    ARGS:
    - model_name: Имя создаваемой модели
    - schema: JSON Schema (с properties, required, $defs)
    - defs: Словарь определений ($defs) для разрешения $ref

    RETURNS:
    - Динамический класс Pydantic BaseModel
    """
    from pydantic import create_model

    fields = {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for field_name, field_def in properties.items():
        field_type = _resolve_field_type(field_def, defs)
        is_required = field_name in required
        fields[field_name] = (field_type, ...) if is_required else (field_type, None)

    return create_model(model_name, **fields)


def _resolve_field_type(field_def: dict, defs: dict) -> type:
    """
    Рекурсивно разрешает тип поля из JSON Schema.

    Поддерживает:
    - Примитивы: string, integer, number, boolean
    - Массивы: array с items (в т.ч. с $ref)
    - Объекты: inline object с properties
    - $ref: ссылки на определения в $defs
    """
    from pydantic import create_model

    # $ref → разрешение ссылки
    if "$ref" in field_def:
        ref_path = field_def["$ref"]
        # Формат: "#/$defs/ModelName" или "#/definitions/ModelName"
        ref_name = ref_path.split("/")[-1]
        if ref_name in defs:
            nested_schema = defs[ref_name]
            return _create_model_from_schema(ref_name, nested_schema, defs)
        # Если определение не найдено — fallback на dict
        return dict

    json_type = field_def.get("type", "string")

    # array → list[ItemType]
    if json_type == "array":
        items_schema = field_def.get("items")
        if items_schema:
            item_type = _resolve_field_type(items_schema, defs)
            return list[item_type]
        return list

    # object inline → вложенная модель
    if json_type == "object" and "properties" in field_def:
        nested_model_name = field_def.get("title", "NestedObject")
        return _create_model_from_schema(nested_model_name, field_def, defs)

    # Примитивы
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(json_type, str)


class CallStatus(str, Enum):
    """Статусы LLM вызова."""
    PENDING = "pending"           # Ожидает запуска
    RUNNING = "running"           # Выполняется
    COMPLETED = "completed"       # Успешно завершён
    FAILED = "failed"             # Ошибка выполнения
    CANCELLED = "cancelled"       # Отменён пользователем


@dataclass
class RetryAttempt:
    """Информация о попытке структурированного вывода."""
    attempt_number: int
    prompt: str
    raw_response: Optional[str]  # Сырой JSON текст
    parsed_content: Optional[Any] = None  # ✅ НОВОЕ: Распарсенная Pydantic модель
    success: bool = False
    error_type: Optional[str] = None  # "json_error", "validation_error", "incomplete", "timeout"
    error_message: Optional[str] = None
    duration: float = 0.0
    tokens_used: int = 0


@dataclass
class LLMMetrics:
    """Метрики LLM вызовов."""
    total_calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    total_generation_time: float = 0.0

    # Метрики для структурированного вывода
    structured_calls: int = 0
    structured_success: int = 0
    total_retry_attempts: int = 0  # Сумма всех попыток по всем вызовам

    @property
    def avg_generation_time(self) -> float:
        """Среднее время генерации для успешных вызовов."""
        if self.completed_calls == 0:
            return 0.0
        return self.total_generation_time / self.completed_calls

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
            "failed_calls": self.failed_calls,
            "avg_generation_time": round(self.avg_generation_time, 3),
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
    orchestrator = LLMOrchestrator(event_bus)
    await orchestrator.initialize()

    # Вызов с контекстом для трассировки
    response = await orchestrator.execute(
        request=request,
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
        cleanup_interval: float = 600.0,
        max_pending_calls: int = 100
    ):
        """
        Инициализация оркестратора.

        ПАРАМЕТРЫ:
        - event_bus: Шина событий для логирования
        - cleanup_interval: Интервал очистки старых записей (секунды)
        - max_pending_calls: Максимальное количество ожидающих вызовов

        АРХИТЕКТУРА (Вариант A):
        - executor НЕ создаётся — провайдеры сами управляют потоками
        - Оркестратор только маршрутизирует, логирует и собирает метрики
        """
        self._event_bus = event_bus
        self._cleanup_interval = cleanup_interval
        self._max_pending_calls = max_pending_calls

        # model_name для обратной совместимости
        self.model_name = "unknown"

        # Реестр активных вызовов
        self._pending_calls: Dict[str, CallRecord] = {}

        # Метрики
        self._metrics = LLMMetrics()

        # Задачи фоновой очистки
        self._cleanup_task: Optional[asyncio.Task] = None

        # Логгер
        self._logger: Optional[logging.Logger] = None

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
            # Создание логгера
            self._logger = logging.getLogger("core.infrastructure.providers.llm.llm_orchestrator")

            # Запуск фоновой задачи очистки
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            self._logger.info(
                "LLMOrchestrator инициализирован: max_workers=%d, cleanup_interval=%dс",
                self._max_workers, self._cleanup_interval,
                extra={"event_type": LogEventType.SYSTEM_INIT}
            )
            
            # Event bus publish
            if self._event_bus:
                await self._event_bus.publish(
                    EventType.DEBUG,
                    {"message": "LLMOrchestrator initialized"},
                    source="LLMOrchestrator"
                )

            return True

        except Exception as e:
            if self._logger:
                self._logger.error(f"Ошибка инициализации LLMOrchestrator: {e}")
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

            # Логируем статистику
            if self._logger:
                metrics = self._metrics.to_dict()
                self._logger.info(
                    f"LLMOrchestrator завершён. Метрики: {metrics}"
                )

            self._logger.info("LLMOrchestrator остановлен")

            # Event bus publish
            if self._event_bus:
                await self._event_bus.publish(
                    EventType.DEBUG,
                    {"message": "LLMOrchestrator shutdown", "metrics": self._metrics.to_dict()},
                    source="LLMOrchestrator"
                )
            
        except Exception as e:
            if self._logger:
                self._logger.error(f"Ошибка при shutdown LLMOrchestrator: {e}")
    
    async def execute(
        self,
        request: LLMRequest,
        provider: Any = None,
        # Контекст для трассировки
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None,
        phase: Optional[str] = None,
        goal: Optional[str] = None
    ) -> LLMResponse:
        """
        Выполнение LLM вызова с расширенным логированием.

        АРХИТЕКТУРА (Вариант A):
        - Вызываем provider._generate_impl() напрямую
        - Провайдер сам управляет потоками и таймаутами
        - Оркестратор только маршрутизирует, логирует и собирает метрики

        ПАРАМЕТРЫ:
        - request: Запрос к LLM
        - provider: LLM провайдер для вызова
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

        # Установка контекста в провайдере для логирования
        if hasattr(provider, 'set_call_context'):
            provider.set_call_context(
                event_bus=self._event_bus,
                session_id=session_id or "unknown",
                agent_id=agent_id or "system",
                component=request.capability_name or "unknown",
                phase=phase or "unknown",
                goal=goal or "unknown"
            )

        try:
            # Вызов провайдера напрямую (он сам управляет потоками)
            return await self._execute_call(
                call_id=call_id,
                request=request,
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

        self._logger.info(
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
        max_retries: int = 3,  # 3 попытки для надёжности
        use_native_structured_output: bool = True,
        # Контекст для трассировки
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None,
        phase: Optional[str] = None,
        goal: Optional[str] = None
    ) -> LLMResponse:
        """
        Выполнение LLM вызова со структурированным выводом.

        АРХИТЕКТУРА:
        1. Первичный запрос с указанием JSON схемы
        2. Парсинг и валидация ответа (в провайдере)
        3. При ошибке — выбрасываем StructuredOutputError
        4. Возврат LLMResponse с типизированной моделью

        ПАРАМЕТРЫ:
        - request: Запрос к LLM (должен иметь structured_output)
        - provider: LLM провайдер
        - max_retries: Максимальное количество попыток (по умолчанию 1, строгая валидация)
        - use_native_structured_output: Использовать нативную поддержку схемы (по умолчанию True)
        - session_id, agent_id, step_number, phase, goal: Контекст трассировки

        ВОЗВРАЩАЕТ:
        - LLMResponse[T]: Результат с типизированной моделью
          - parsed_content: Pydantic модель типа T
          - raw_response: Сырой ответ для отладки
          - parsing_attempts: Количество попыток
          - validation_errors: Ошибки валидации
        """
        if not request.structured_output:
            return LLMResponse(
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

        # Обновление метрик
        self._metrics.structured_calls += 1

        # Логирование начала структурированного вызова
        await self._log_structured_start(call_id, request, session_id)

        try:
            # Fail-fast: проверяем провайдер
            if provider is None:
                self._logger.warning("Provider is None — модель не загружена!", extra={"event_type": LogEventType.LLM_ERROR})
                raise StructuredOutputError(
                    message="LLM провайдер не инициализирован (provider=None)",
                    model_name=getattr(request, 'model_name', self.model_name),
                    attempts=0,
                    validation_errors=[{"error": "provider_not_initialized", "message": "LLM provider is None"}]
                )

            # Retry loop: до max_retries попыток
            last_attempt = None

            for attempt_num in range(1, max_retries + 1):

                if self._logger:
                    self._logger.info(
                        f"🔵 [STRUCTURED] Выполнение попытки {attempt_num}/{max_retries} | "
                        f"prompt_len={len(request.prompt)} | "
                        f"use_native_structured_output={use_native_structured_output}"
                    )

                attempt = await self._execute_structured_attempt(
                    call_id=call_id,
                    request=request,
                    provider=provider,
                    attempt_num=attempt_num,
                    use_native_structured_output=use_native_structured_output,
                    session_id=session_id,
                    agent_id=agent_id,
                    step_number=step_number,
                    phase=phase
                )

                self._metrics.total_retry_attempts += 1

                self._logger.debug(
                    "[STRUCTURED] Результат попытки %d/%d | success=%s | error_type=%s | error_message=%s",
                    attempt_num, max_retries, attempt.success, attempt.error_type,
                    attempt.error_message if attempt.error_message else 'None',
                    extra={"event_type": LogEventType.LLM_CALL}
                )
                    
                # Детальное логирование сырого ответа при ошибке
                if not attempt.success and attempt.raw_response:
                    self._logger.error(
                        f"❌ [STRUCTURED] RAW LLM RESPONSE (attempt {attempt_num}):\n{attempt.raw_response}"
                    )

                if attempt.success:
                    # Успех!
                    self._metrics.structured_success += 1
                    await self._log_structured_success(
                        call_id=call_id,
                        attempt_num=attempt_num,
                        duration=attempt.duration,
                        session_id=session_id,
                        response_content=attempt.raw_response or "",
                        tokens_used=attempt.tokens_used,
                        model="structured"
                    )

                    # Возвращаем успешный ответ с распарсенной моделью
                    return LLMResponse(
                        parsed_content=attempt.parsed_content,
                        raw_response=RawLLMResponse(
                            content=attempt.raw_response or "",
                            model="structured",
                            tokens_used=attempt.tokens_used,
                            generation_time=attempt.duration
                        ),
                        parsing_attempts=attempt_num,
                        validation_errors=[]
                    )
                else:
                    # Ошибка — логируем и пробуем снова
                    last_attempt = attempt
                    await self._log_structured_retry(
                        call_id, attempt_num, attempt.error_type,
                        attempt.error_message, attempt_num < max_retries
                    )

                    if attempt_num < max_retries:
                        if self._logger:
                            self._logger.warning(
                                f"⚠️ [STRUCTURED] Retry {attempt_num}/{max_retries} failed, trying again..."
                            )
                    # Продолжаем цикл — следующая попытка

            # Все попытки исчерпаны
            await self._log_structured_exhausted(
                call_id, max_retries, last_attempt.error_message if last_attempt else "No attempts made", session_id
            )

            # Выбрасываем StructuredOutputError с деталями всех попыток
            raise StructuredOutputError(
                message=f"Не удалось получить валидный структурированный ответ после {max_retries} попыток",
                model_name=getattr(request, 'model_name', self.model_name),
                attempts=max_retries,
                validation_errors=[{"error": last_attempt.error_type, "message": last_attempt.error_message}] if last_attempt else []
            )

        except StructuredOutputError:
            # Пробрасываем дальше
            raise
        except Exception as e:
            # Критическая ошибка
            await self._log_structured_error(call_id, str(e), session_id)
            # Пробрасываем StructuredOutputError
            raise StructuredOutputError(
                message=f"Критическая ошибка структурированного вывода: {str(e)}",
                model_name=getattr(request, 'model_name', self.model_name),
                attempts=1,
                validation_errors=[{"error": "exception", "message": str(e)}]
            )

    async def _execute_structured_attempt(
        self,
        call_id: str,
        request: LLMRequest,
        provider: Any,
        attempt_num: int,
        use_native_structured_output: bool = True,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_number: Optional[int] = None,
        phase: Optional[str] = None
    ) -> RetryAttempt:
        """
        Выполнение одной попытки структурированного вывода.

        ВОЗВРАЩАЕТ:
        - RetryAttempt: Результат попытки
        """
        start_time = time.time()

        try:
            # Выполняем вызов через оркестратор
            response = await self.execute(
                request=request,
                provider=provider,
                session_id=session_id,
                agent_id=agent_id,
                step_number=step_number,
                phase=phase
            )

            # Логирование ответа
            if self._logger:
                self._logger.info(
                    f"🔵 [STRUCTURED] LLM response: type={type(response).__name__}, "
                    f"content_len={self._get_content_length(response)}, "
                    f"has_parsed={hasattr(response, 'parsed_content')}, "
                    f"finish_reason={self._get_finish_reason(response)}"
                )
                
                # Логируем сырой ответ для отладки
                if hasattr(response, 'raw_response') and response.raw_response:
                    raw_content = response.raw_response.content if hasattr(response.raw_response, 'content') else str(response.raw_response)
                    self._logger.info(
                        f"🔵 [STRUCTURED] Raw response: {raw_content}..."
                    )

            duration = time.time() - start_time

            # Проверка на ошибку в ответе
            finish_reason = self._get_finish_reason(response)
            if finish_reason == "error":
                error_msg = response.metadata.get('error', 'Unknown error') if response.metadata else 'Unknown error'

                # Для structured output — всё равно пробуем распарсить raw_response
                # (провайдер мог вернуть сырой ответ с markdown-обёрткой)
                if hasattr(response, 'raw_response') and response.raw_response:
                    raw_content = response.raw_response.content if hasattr(response.raw_response, 'content') else str(response.raw_response)
                    if self._logger:
                        self._logger.warning(
                            f"⚠️ [STRUCTURED] finish_reason=error, но пробуем распарсить raw_response (len={len(raw_content)})"
                        )
                    # Продолжаем обработку ниже
                else:
                    return RetryAttempt(
                        attempt_number=attempt_num,
                        prompt=request.prompt,
                        raw_response=None,
                        success=False,
                        error_type="llm_error",
                        error_message=error_msg,
                        duration=duration
                    )
            else:
                # Нормальный finish_reason (stop/length) — продолжаем
                pass

            # Проверка: LLMResponse с raw_response.content (JSON строка)
            if hasattr(response, 'raw_response') and response.raw_response:
                # LLMResponse от провайдера
                raw_content = response.raw_response.content if hasattr(response.raw_response, 'content') else str(response.raw_response)

                if self._logger:
                    self._logger.info(
                        f"🔵 [STRUCTURED] Найден raw_response.content, len={len(raw_content) if raw_content else 0}"
                    )

                # Проверяем есть ли уже parsed_content (Pydantic модель)
                if hasattr(response, 'parsed_content') and response.parsed_content:
                    # Модель уже создана провайдером (редкий случай)
                    if self._logger:
                        self._logger.info(
                            f"🔵 [STRUCTURED] parsed_content уже заполнен: {type(response.parsed_content).__name__}"
                        )
                    return RetryAttempt(
                        attempt_number=attempt_num,
                        prompt=request.prompt,
                        raw_response=raw_content,
                        parsed_content=response.parsed_content,
                        success=True,
                        error_type=None,
                        error_message=None,
                        duration=duration,
                        tokens_used=self._get_tokens_used(response)
                    )

                # parsed_content=None — создаём Pydantic модель из JSON Schema
                if request.structured_output:
                    try:
                        import json
                        from pydantic import create_model
                        from core.infrastructure.providers.llm.json_parser import extract_json_from_response

                        # Логируем сырой JSON для отладки
                        if self._logger:
                            self._logger.info(f"🔵 [STRUCTURED] JSON для парсинга: {raw_content}...")

                        # Извлекаем JSON из markdown-обёртки (если есть)
                        cleaned_json = extract_json_from_response(raw_content)

                        # Парсим JSON из строки
                        json_data = json.loads(cleaned_json)
                        
                        if self._logger:
                            self._logger.info(f"✅ [STRUCTURED] JSON распарсен: ключи={list(json_data.keys()) if isinstance(json_data, dict) else 'not a dict'}")
                        
                        # Создаём динамическую Pydantic модель из JSON Schema
                        schema = request.structured_output.schema_def
                        model_name = request.structured_output.output_model or "DynamicModel"

                        # Создаём модель динаически с поддержкой вложенных объектов ($ref)
                        defs = schema.get("$defs", {})
                        DynamicModel = _create_model_from_schema(
                            model_name, schema, defs
                        )
                        parsed_content = DynamicModel(**json_data)
                        
                        if self._logger:
                            self._logger.info(
                                f"✅ [STRUCTURED] Создана Pydantic модель {model_name} из JSON"
                            )
                        
                        return RetryAttempt(
                            attempt_number=attempt_num,
                            prompt=request.prompt,
                            raw_response=raw_content,
                            parsed_content=parsed_content,  # ← Pydantic модель!
                            success=True,
                            error_type=None,
                            error_message=None,
                            duration=duration,
                            tokens_used=self._get_tokens_used(response)
                        )
                        
                    except json.JSONDecodeError as json_err:
                        if self._logger:
                            self._logger.error(
                                f"❌ [STRUCTURED] JSON parse error: {json_err}"
                            )
                        return RetryAttempt(
                            attempt_number=attempt_num,
                            prompt=request.prompt,
                            raw_response=raw_content,
                            parsed_content=None,
                            success=False,
                            error_type="json_error",
                            error_message=str(json_err),
                            duration=duration,
                            tokens_used=self._get_tokens_used(response)
                        )
                        
                    except Exception as model_err:
                        if self._logger:
                            self._logger.warning(
                                f"⚠️ [STRUCTURED] Не удалось создать Pydantic модель: {model_err}"
                            )
                        return RetryAttempt(
                            attempt_number=attempt_num,
                            prompt=request.prompt,
                            raw_response=raw_content,
                            parsed_content=None,
                            success=False,
                            error_type="validation_error",
                            error_message=str(model_err),
                            duration=duration,
                            tokens_used=self._get_tokens_used(response)
                        )
                else:
                    # Нет structured_output — не должно произойти
                    if self._logger:
                        self._logger.error("❌ [STRUCTURED] Нет structured_output в запросе")
                    return RetryAttempt(
                        attempt_number=attempt_num,
                        prompt=request.prompt,
                        raw_response=raw_content,
                        parsed_content=None,
                        success=False,
                        error_type="exception",
                        error_message="structured_output не указан",
                        duration=duration,
                        tokens_used=self._get_tokens_used(response)
                    )
            else:
                # LLMResponse (старый формат) — берём content и валидируем
                if self._logger:
                    self._logger.warning(
                        f"⚠️ [STRUCTURED] Нет raw_response, используем LLMResponse.content"
                    )
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
                    parsed_content=None,
                    success=True,
                    error_type=None,
                    error_message=None,
                    duration=duration,
                    tokens_used=self._get_tokens_used(response)
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
                    tokens_used=self._get_tokens_used(response)
                )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return RetryAttempt(
                attempt_number=attempt_num,
                prompt=request.prompt,
                raw_response=None,
                success=False,
                error_type="timeout",
                error_message=f"Attempt {attempt_num} timed out",
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
        
        ДЕЛЕГИРОВАНИЕ: Вызывает функции из json_parser.py
        
        ПРОВЕРКИ:
        1. JSON парсинг
        2. Соответствие схеме через Pydantic (если указана)
        3. Полнота ответа (не обрезан ли)

        ВОЗВРАЩАЕТ:
        - Dict с полями: success, error_type, error_message, parsed
        """
        # Делегируем логику в json_parser
        return validate_structured_response(raw_content, schema)

    async def _log_structured_start(
        self,
        call_id: str,
        request: LLMRequest,
        session_id: Optional[str]
    ) -> None:
        """Логирование начала структурированного вызова."""
        if not self._logger:
            return

        self._logger.info(
            f"📋 Structured LLM | call_id={call_id} | "
            f"session={session_id} | "
            f"schema={request.structured_output.output_model if request.structured_output else 'unknown'}"
        )

        # Публикация события LLM_PROMPT_GENERATED
        if self._event_bus:
            timeout = request.metadata.get("timeout") if request.metadata else None
            await self._event_bus.publish(
                EventType.LLM_PROMPT_GENERATED,
                data={
                    "call_id": call_id,
                    "session_id": session_id,
                    "agent_id": None,
                    "step_number": None,
                    "phase": "structured",
                    "goal": None,
                    "capability_name": request.capability_name,
                    "system_prompt": request.system_prompt or "",
                    "user_prompt": request.prompt,
                    "prompt_length": len(request.prompt) if request.prompt else 0,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "timeout": timeout
                },
                source="LLMOrchestrator",
                session_id=session_id or "",
                agent_id=None,
                correlation_id=call_id
            )
            self._logger.debug("Опубликовано LLM_PROMPT_GENERATED: call_id=%s", call_id, extra={"event_type": LogEventType.LLM_CALL})

    async def _log_structured_success(
        self,
        call_id: str,
        attempt_num: int,
        duration: float,
        session_id: Optional[str],
        response_content: str = "",
        tokens_used: int = 0,
        model: str = ""
    ) -> None:
        """Логирование успешного структурированного вызова."""
        if not self._logger:
            return

        self._logger.info(
            f"✅ Structured SUCCESS | call_id={call_id} | "
            f"session={session_id} | attempt={attempt_num} | "
            f"duration={duration:.2f}s"
        )

        # Публикация события LLM_RESPONSE_RECEIVED
        if self._event_bus:
            await self._event_bus.publish(
                EventType.LLM_RESPONSE_RECEIVED,
                data={
                    "call_id": call_id,
                    "session_id": session_id,
                    "agent_id": None,
                    "step_number": None,
                    "phase": "structured",
                    "success": True,
                    "duration_ms": duration * 1000,
                    "capability_name": None,
                    "response": response_content,
                    "raw_response": response_content,
                    "response_length": len(response_content) if response_content else 0,
                    "tokens_used": tokens_used,
                    "model": model
                },
                source="LLMOrchestrator",
                session_id=session_id or "",
                agent_id=None,
                correlation_id=call_id
            )
            self._logger.debug("Опубликовано LLM_RESPONSE_RECEIVED: call_id=%s", call_id, extra={"event_type": LogEventType.LLM_RESPONSE})

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
        self._logger.warning(
            f"{icon} Structured RETRY | call_id={call_id} | "
            f"attempt={attempt_num} | error={error_type} | "
            f"message={error_message if error_message else 'unknown'} | "
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

        self._logger.error(
            f"❌ Structured EXHAUSTED | call_id={call_id} | "
            f"session={session_id} | total_attempts={total_attempts} | "
            f"last_error={last_error if last_error else 'unknown'}"
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

        self._logger.error(
            f"❌ Structured FAILURE | call_id={call_id} | "
            f"attempt={attempt_num} | type={failure_type} | "
            f"message={message}"
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

        self._logger.error(
            f"❌ Structured EXCEPTION | call_id={call_id} | "
            f"session={session_id} | error={error}"
        )

    async def _execute_call(
        self,
        call_id: str,
        request: LLMRequest,
        provider: Any,
        call_record: CallRecord
    ) -> LLMResponse:
        """
        Выполнение вызова LLM.

        АРХИТЕКТУРА (Вариант A):
        - Вызываем provider._generate_impl() напрямую
        - Провайдер сам управляет потоками и таймаутами
        - Оркестратор только маршрутизирует, логирует и собирает метрики

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
            # Вызываем провайдер напрямую — он сам управляет потоком
            result = await provider._generate_impl(request)

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

        self._logger.info(
            f"✅ LLM ответ | call_id={record.call_id} | "
            f"session={record.session_id} | step={record.step_number} | "
            f"response_len={self._get_content_length(result)} | tokens={self._get_tokens_used(result)} | "
            f"duration={record.duration:.2f}s"
        )

        # Публикация события LLM_RESPONSE_RECEIVED
        await self._publish_response_event(record, result, record.duration or 0, success=True)

    async def _log_call_timeout(self, record: CallRecord, elapsed: float, timeout: float) -> None:
        """Логирование таймаута вызова."""
        if not self._logger:
            return

        self._logger.warning(
            f"⏰ LLM TIMEOUT | call_id={record.call_id} | "
            f"session={record.session_id} | agent={record.agent_id} | "
            f"step={record.step_number} | phase={record.phase} | "
            f"elapsed={elapsed:.2f}s | timeout={timeout}s | "
            f"prompt_len={len(record.request.prompt)}"
        )

        # Публикация события LLM_RESPONSE_RECEIVED с ошибкой
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

        self._logger.error(
            f"❌ LLM ERROR | call_id={record.call_id} | "
            f"session={record.session_id} | step={record.step_number} | "
            f"{type(error).__name__}: {str(error)} | elapsed={elapsed:.2f}s"
        )

        # Публикация события LLM_RESPONSE_RECEIVED с ошибкой
        await self._publish_response_event(
            record,
            None,
            elapsed,
            success=False,
            error_type=type(error).__name__,
            error_message=str(error)
        )

    async def _publish_prompt_event(self, record: CallRecord) -> None:
        """Публикация события LLM_PROMPT_GENERATED."""
        if not self._event_bus:
            return

        await self._event_bus.publish(
            EventType.LLM_PROMPT_GENERATED,
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
            session_id=record.session_id or "",
            agent_id=record.agent_id or "",
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

        # Извлекаем контент ответа через helper-метод
        response_content = self._get_content(result) if result else ""
        raw_response_content = ""

        if result and hasattr(result, 'raw_response') and result.raw_response:
            raw_response_content = result.raw_response.content if hasattr(result.raw_response, 'content') else str(result.raw_response)

        data = {
            "call_id": record.call_id,
            "session_id": record.session_id,
            "agent_id": record.agent_id,
            "step_number": record.step_number,
            "phase": record.phase,
            "success": success,
            "duration_ms": duration * 1000,
            "capability_name": record.request.capability_name,
            # Ответ: parsed content или raw content
            "response": response_content or raw_response_content,
            "raw_response": raw_response_content,
            "response_length": len(response_content) if response_content else len(raw_response_content)
        }

        if success and result:
            # Пытаемся распарсить JSON для удобства чтения
            content_to_parse = response_content or raw_response_content
            if content_to_parse:
                try:
                    import json
                    parsed = json.loads(content_to_parse)
                    data["parsed_response"] = parsed
                    data["response_preview"] = json.dumps(parsed, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, Exception):
                    data["response_preview"] = content_to_parse

            # tokens_used и model через helper-методы
            data.update({
                "tokens_used": self._get_tokens_used(result),
                "model": getattr(result.raw_response, 'model', getattr(result, 'model', 'unknown')) if hasattr(result, 'raw_response') else getattr(result, 'model', 'unknown')
            })
        else:
            data.update({
                "error_type": error_type,
                "error_message": error_message if error_message else None
            })

        await self._event_bus.publish(
            EventType.LLM_RESPONSE_RECEIVED,
            data=data,
            source="LLMOrchestrator",
            session_id=record.session_id or "",
            agent_id=record.agent_id or "",
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
                    self._logger.error(f"Ошибка в cleanup loop: {e}")
    
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
            self._logger.debug(f"Очищено {removed} старых записей")
        
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

    # === Helper-методы для извлечения данных из ответов ===

    @staticmethod
    def _get_tokens_used(response) -> int:
        """
        Извлечение tokens_used из ответа.

        ПРИОРИТЕТ:
        1. response.raw_response.tokens_used
        2. response.tokens_used
        3. 0 (по умолчанию)
        """
        if hasattr(response, 'raw_response') and response.raw_response:
            return response.raw_response.tokens_used
        return getattr(response, 'tokens_used', 0)

    @staticmethod
    def _get_finish_reason(response) -> str:
        """
        Извлечение finish_reason из ответа.

        ПРИОРИТЕТ:
        1. response.raw_response.finish_reason
        2. response.finish_reason
        3. 'unknown' (по умолчанию)
        """
        if hasattr(response, 'raw_response') and response.raw_response:
            return response.raw_response.finish_reason
        return getattr(response, 'finish_reason', 'unknown')

    @staticmethod
    def _get_content(response) -> str:
        """
        Извлечение контента из ответа.

        ПРИОРИТЕТ:
        1. str(response.parsed_content)
        2. response.content
        3. '' (по умолчанию)
        """
        if hasattr(response, 'parsed_content') and response.parsed_content:
            return str(response.parsed_content)
        return getattr(response, 'content', '')

    @staticmethod
    def _get_content_length(response) -> int:
        """Получение длины контента."""
        return len(LLMOrchestrator._get_content(response))

    # === Конец helper-методов ===

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

        # Оценка здоровья по проценту ошибок
        status = "healthy"
        if metrics["failed_calls"] > 0:
            fail_rate = metrics["failed_calls"] / max(1, metrics["total_calls"])
            if fail_rate > 0.5:
                status = "degraded"
            if fail_rate > 0.8:
                status = "unhealthy"

        return {
            "status": status,
            "pending_calls": len(pending),
            "metrics": metrics,
            "recent_calls": pending[:10]  # Последние 10
        }
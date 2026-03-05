"""
LLMOrchestrator - централизованное управление вызовами LLM.

АРХИТЕКТУРНАЯ РОЛЬ:
- Инкапсулирует пул потоков/процессов для синхронных LLM вызовов
- Управляет таймаутами и повторными попытками
- Отслеживает активные вызовы и предотвращает утечку ресурсов
- Предоставляет единый интерфейс для всех компонентов
- Возвращает структурированные ответы с полем error вместо исключений

ПРОБЛЕМА КОТОРУЮ РЕШАЕТ:
При использовании asyncio.wait_for с run_in_executor:
1. При таймауте исключение пробрасывается вверх
2. Фоновый поток продолжает выполнение и потребляет ресурсы
3. Результат вызова теряется
4. Пул потоков может переполниться "висячими" задачами

РЕШЕНИЕ:
1. Реестр активных вызовов с отслеживанием статуса
2. При таймауте вызов помечается как "timed_out", но поток завершается
3. Когда поток завершается, проверяем статус и логируем опоздание
4. Агент получает StructuredLLMResponse с error вместо исключения
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


class CallStatus(str, Enum):
    """Статусы LLM вызова."""
    PENDING = "pending"           # Ожидает запуска
    RUNNING = "running"           # Выполняется
    COMPLETED = "completed"       # Успешно завершён
    TIMED_OUT = "timed_out"       # Превышен таймаут (но поток ещё работает)
    FAILED = "failed"             # Ошибка выполнения
    CANCELLED = "cancelled"       # Отменён пользователем


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
            "orphan_rate": round(self.orphan_rate, 3)
        }


@dataclass
class CallRecord:
    """Запись об активном LLM вызове."""
    call_id: str
    request: LLMRequest
    status: CallStatus = CallStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    timeout: Optional[float] = None
    error: Optional[str] = None
    result: Optional[LLMResponse] = None
    thread_name: Optional[str] = None
    
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
            "prompt_length": len(self.request.prompt)
        }


class LLMOrchestrator:
    """
    Централизованный оркестратор для управления LLM вызовами.
    
    ПРИНЦИПЫ РАБОТЫ:
    1. Все вызовы регистрируются в реестре с уникальным ID
    2. При таймауте вызов помечается как timed_out, но поток не прерывается
    3. Когда поток завершается, проверяем статус:
       - Если timed_out -> логируем опоздание, результат отбрасываем
       - Если running -> завершаем успешно
    4. Периодическая очистка старых записей
    5. Метрики для мониторинга здоровья системы
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    orchestrator = LLMOrchestrator(event_bus, max_workers=4)
    await orchestrator.initialize()
    
    # Вызов с таймаутом
    response = await orchestrator.execute(request, timeout=60.0)
    if response.status == "error":
        # Обрабатываем ошибку без падения агента
        return BehaviorDecision.switch_to_fallback(reason=response.error)
    
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
        capability_name: Optional[str] = None
    ) -> LLMResponse:
        """
        Выполнение LLM вызова с управлением таймаутом.
        
        ВАЖНО: Не бросает исключения при таймауте! Возвращает LLMResponse с error.
        
        ПАРАМЕТРЫ:
        - request: Запрос к LLM
        - timeout: Таймаут ожидания (секунды). Если None - используется timeout из request
        - provider: LLM провайдер для вызова
        - capability_name: Имя capability (для логирования)
        
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
            
            # Регистрация вызова в реестре
            call_record = CallRecord(
                call_id=call_id,
                request=request,
                status=CallStatus.PENDING,
                timeout=timeout
            )
            self._pending_calls[call_id] = call_record
        
        # Обновление метрик
        self._metrics.total_calls += 1
        
        try:
            # Запуск выполнения
            return await self._execute_with_timeout(
                call_id=call_id,
                request=request,
                timeout=timeout,
                provider=provider
            )
        
        finally:
            # Очистка записи (не сразу, чтобы сохранить метрики)
            asyncio.create_task(self._schedule_cleanup(call_id))
    
    async def _execute_with_timeout(
        self,
        call_id: str,
        request: LLMRequest,
        timeout: Optional[float],
        provider: Any
    ) -> LLMResponse:
        """
        Выполнение вызова с таймаутом.
        
        ВОЗВРАЩАЕТ:
        - LLMResponse: Результат вызова
        """
        start_time = time.time()
        
        # Обновление статуса
        async with self._lock:
            record = self._pending_calls[call_id]
            record.status = CallStatus.RUNNING
            record.start_time = start_time
        
        # Публикация события начала вызова
        await self._publish_call_started(call_id, request)
        
        try:
            # Запуск в executor
            future = asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._sync_call_wrapper,
                call_id,
                request,
                provider
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
            
            # Публикация события завершения
            await self._publish_call_completed(call_id, result, record.duration)
            
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
            
            # Логирование
            if self._logger:
                await self._logger.warning(
                    f"⏰ LLM TIMEOUT | call_id={call_id} | "
                    f"elapsed={elapsed:.2f}s | timeout={effective_timeout}s | "
                    f"capability={request.capability_name}"
                )
            
            # Публикация события таймаута
            await self._publish_call_timeout(call_id, elapsed, effective_timeout)
            
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
            
            # Логирование
            if self._logger:
                await self._logger.error(
                    f"❌ LLM ERROR | call_id={call_id} | "
                    f"{type(e).__name__}: {str(e)[:200]} | elapsed={elapsed:.2f}s"
                )
            
            # Публикация события ошибки
            await self._publish_call_failed(call_id, e, elapsed)
            
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
    
    def _sync_call_wrapper(
        self,
        call_id: str,
        request: LLMRequest,
        provider: Any
    ) -> LLMResponse:
        """
        Обёртка для синхронного вызова LLM.
        
        Выполняется в потоке executor'а. Проверяет статус вызова после завершения.
        """
        import threading
        thread_name = threading.current_thread().name
        
        # Сохраняем имя потока в записи
        if call_id in self._pending_calls:
            self._pending_calls[call_id].thread_name = thread_name
        
        try:
            # Синхронный вызов провайдера
            # Провайдер должен иметь метод generate() который возвращает LLMResponse
            if not provider:
                raise ValueError("LLM provider не указан")
            
            # Вызываем _generate_impl напрямую (синхронная версия)
            # Или используем asyncio.run для вызова асинхронного метода
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
                    self._log_orphaned_call(call_id, record)
                    # Возвращаем None чтобы оркестратор знал что результат не нужен
                    return None
            
            return result
            
        except Exception as e:
            # Логируем ошибку в потоке
            if self._logger:
                # Используем sync версию логгера если доступна
                if hasattr(self._logger, 'error_sync'):
                    self._logger.error_sync(f"Ошибка в sync вызове {call_id}: {e}")
            raise
    
    def _log_orphaned_call(self, call_id: str, record: CallRecord) -> None:
        """
        Логирование "брошенного" вызова.
        
        Вызов завершился после таймаута - его результат никому не нужен.
        """
        # Обновление метрик
        self._metrics.orphaned_calls += 1
        
        # Логирование
        if self._logger and hasattr(self._logger, 'warning_sync'):
            self._logger.warning_sync(
                f"🗑️ ORPHANED CALL | call_id={call_id} | "
                f"завершился через {record.duration:.2f}с после таймаута | "
                f"capability={record.request.capability_name}"
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
        """Получение списка активных вызовов."""
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

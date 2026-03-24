"""
Миксины для EventBusLogger.

АРХИТЕКТУРА:
- SyncLoggerMixin — синхронный вывод (stdout/stderr)
- AsyncLoggerMixin — асинхронная публикация через EventBus
- LLMMixin — логирование LLM вызовов
- SessionMixin — управление сессиями
- EventBusLogger — основной класс (композит миксинов)

USAGE:
```python
class EventBusLogger(SyncLoggerMixin, AsyncLoggerMixin, LLMMixin, SessionMixin):
    pass
```
"""
import asyncio
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Callable

from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


# ============================================================
# ENUMS
# ============================================================

class LoggerInitializationState(Enum):
    """Состояние инициализации логгера."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"


# ============================================================
# MIXIN 1: SyncLoggerMixin — синхронный вывод
# ============================================================

class SyncLoggerMixin:
    """
    Миксин синхронного логирования.
    
    FEATURES:
    - Прямая запись в stdout/stderr
    - Обработка ошибок с fallback
    - UTF-8 поддержка для Windows
    """
    
    def _write_sync(self, message: str, level: str, stream=None):
        """
        Синхронная запись в stdout/stderr.
        
        ARGS:
        - message: Сообщение
        - level: Уровень (INFO, DEBUG, WARNING, ERROR)
        - stream: Поток (stdout/stderr)
        """
        if stream is None:
            stream = sys.stderr if level in ("ERROR", "CRITICAL") else sys.stdout

        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            component = getattr(self, 'component', 'unknown')
            formatted = f"[{timestamp}] [{level}] [{component}] {message}"

            try:
                stream.buffer.write((formatted + '\n').encode('utf-8'))
                stream.buffer.flush()
            except (AttributeError, UnicodeEncodeError):
                print(formatted, file=stream, flush=True)

        except Exception as e:
            self._write_fallback(message, level, str(e))

    def _write_fallback(self, message: str, level: str, reason: str):
        """Fallback запись через EventBus при ошибке stdout."""
        try:
            event_type = {
                "INFO": EventType.LOG_INFO,
                "DEBUG": EventType.LOG_DEBUG,
                "WARNING": EventType.LOG_WARNING,
                "ERROR": EventType.LOG_ERROR,
            }.get(level, EventType.LOG_INFO)

            data = {
                "message": f"[FALLBACK] {message}",
                "level": level,
                "session_id": getattr(self, 'session_id', 'unknown'),
                "agent_id": getattr(self, 'agent_id', 'unknown'),
                "component": getattr(self, 'component', 'unknown'),
                "timestamp": datetime.now().isoformat() + 'Z',
                "fallback_reason": f"stdout write failed: {reason}"
            }

            event_bus = getattr(self, 'event_bus', None)
            if event_bus:
                event_bus.publish_sync(
                    event_type=event_type,
                    data=data,
                    source=getattr(self, 'component', 'unknown'),
                    session_id=getattr(self, 'session_id', 'unknown'),
                    agent_id=getattr(self, 'agent_id', 'unknown')
                )
        except Exception:
            pass  # Полная неудача

    # === PUBLIC SYNC METHODS ===

    def info_sync(self, message: str, *args, **extra_data):
        """INFO сообщение (синхронно)."""
        if args:
            message = message % args
        self._write_sync(message, "INFO")

    def debug_sync(self, message: str, *args, **extra_data):
        """DEBUG сообщение (синхронно)."""
        if args:
            message = message % args
        self._write_sync(message, "DEBUG")

    def warning_sync(self, message: str, *args, **extra_data):
        """WARNING сообщение (синхронно)."""
        if args:
            message = message % args
        self._write_sync(message, "WARNING")

    def error_sync(self, message: str, *args, **extra_data):
        """ERROR сообщение (синхронно)."""
        if args:
            message = message % args
        self._write_sync(message, "ERROR")


# ============================================================
# MIXIN 2: AsyncLoggerMixin — асинхронная публикация
# ============================================================

class AsyncLoggerMixin:
    """
    Миксин асинхронного логирования.
    
    FEATURES:
    - Публикация через EventBus
    - Автоматическое переключение sync/async
    - Форматирование сообщений
    """
    
    def _is_initializing(self) -> bool:
        """Проверка фазы инициализации."""
        callback = getattr(self, '_get_init_state_callback', None)
        if callback:
            state = callback()
            return state in (
                LoggerInitializationState.NOT_INITIALIZED,
                LoggerInitializationState.INITIALIZING
            )
        
        state = getattr(self, '_init_state', LoggerInitializationState.NOT_INITIALIZED)
        return state in (
            LoggerInitializationState.NOT_INITIALIZED,
            LoggerInitializationState.INITIALIZING
        )

    def _set_initializing(self):
        """Установить состояние INITIALIZING."""
        self._init_state = LoggerInitializationState.INITIALIZING

    def _set_ready(self):
        """Установить состояние READY."""
        self._init_state = LoggerInitializationState.READY

    async def _publish(self, event_type: EventType, message: str, level: str, **extra_data):
        """Публикация события в EventBus."""
        data = {
            "message": message,
            "level": level,
            "session_id": getattr(self, 'session_id', 'unknown'),
            "agent_id": getattr(self, 'agent_id', 'unknown'),
            "component": getattr(self, 'component', 'unknown'),
            "timestamp": datetime.now().isoformat() + 'Z',
            **extra_data
        }

        event_bus = getattr(self, 'event_bus', None)
        if event_bus:
            await event_bus.publish(
                event_type=event_type,
                data=data,
                source=getattr(self, 'component', 'unknown'),
                session_id=getattr(self, 'session_id', 'unknown'),
                agent_id=getattr(self, 'agent_id', 'unknown')
            )

    def _publish_sync(self, event_type: EventType, message: str, level: str, **extra_data):
        """Синхронная публикация события."""
        data = {
            "message": message,
            "level": level,
            "session_id": getattr(self, 'session_id', 'unknown'),
            "agent_id": getattr(self, 'agent_id', 'unknown'),
            "component": getattr(self, 'component', 'unknown'),
            "timestamp": datetime.now().isoformat() + 'Z',
            **extra_data
        }

        event_bus = getattr(self, 'event_bus', None)
        if event_bus:
            event_bus.publish_sync(
                event_type=event_type,
                data=data,
                source=getattr(self, 'component', 'unknown'),
                session_id=getattr(self, 'session_id', 'unknown'),
                agent_id=getattr(self, 'agent_id', 'unknown')
            )

    # === PUBLIC ASYNC METHODS ===

    async def info(self, message: str, *args, **extra_data):
        """INFO сообщение (авто-режим)."""
        if args:
            message = message % args

        if self._is_initializing():
            self._write_sync(message, "INFO")
        else:
            await self._publish(EventType.LOG_INFO, message, "INFO", **extra_data)

    async def debug(self, message: str, *args, **extra_data):
        """DEBUG сообщение (авто-режим)."""
        if args:
            message = message % args

        if self._is_initializing():
            self._write_sync(message, "DEBUG")
        else:
            await self._publish(EventType.LOG_DEBUG, message, "DEBUG", **extra_data)

    async def warning(self, message: str, *args, **extra_data):
        """WARNING сообщение (авто-режим)."""
        if args:
            message = message % args

        if self._is_initializing():
            self._write_sync(message, "WARNING")
        else:
            await self._publish(EventType.LOG_WARNING, message, "WARNING", **extra_data)

    async def error(self, message: str, *args, **extra_data):
        """ERROR сообщение (авто-режим)."""
        if args:
            message = message % args

        if self._is_initializing():
            self._write_sync(message, "ERROR")
        else:
            await self._publish(EventType.LOG_ERROR, message, "ERROR", **extra_data)

    async def exception(self, message: str, exc: Exception, **extra_data):
        """ERROR сообщение с исключением."""
        full_message = f"{message}: {exc}"

        if self._is_initializing():
            self._write_sync(full_message, "ERROR")
        else:
            await self._publish(
                EventType.LOG_ERROR,
                full_message,
                "ERROR",
                exception_type=type(exc).__name__,
                **extra_data
            )


# ============================================================
# MIXIN 3: LLMMixin — логирование LLM вызовов
# ============================================================

class LLMMixin:
    """
    Миксин для логирования LLM вызовов.
    
    FEATURES:
    - Логирование промптов
    - Логирование ответов
    - Метрики (токены, задержки)
    """

    async def log_llm_prompt(
        self,
        component: str,
        phase: str,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ):
        """Логирование LLM промпта."""
        await self._publish(
            EventType.LLM_PROMPT_GENERATED,
            f"LLM Prompt: {component}/{phase}",
            "INFO",
            component=component,
            phase=phase,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_length=len(system_prompt) + len(user_prompt),
            **kwargs
        )

    async def log_llm_response(
        self,
        component: str,
        phase: str,
        response: Any,
        tokens: Optional[int] = None,
        latency_ms: Optional[float] = None,
        **kwargs
    ):
        """Логирование LLM ответа."""
        await self._publish(
            EventType.LLM_RESPONSE_RECEIVED,
            f"LLM Response: {component}/{phase}",
            "INFO",
            component=component,
            phase=phase,
            response=response if isinstance(response, (str, int, float, bool, type(None))) else str(response),
            tokens=tokens,
            latency_ms=latency_ms,
            **kwargs
        )

    async def log_llm_call_started(self, component: str, phase: str, **kwargs):
        """Начало LLM вызова."""
        await self._publish(
            EventType.LLM_CALL_STARTED,
            f"LLM Call Started: {component}/{phase}",
            "INFO",
            component=component,
            phase=phase,
            **kwargs
        )

    async def log_llm_call_completed(self, component: str, phase: str, **kwargs):
        """Завершение LLM вызова."""
        await self._publish(
            EventType.LLM_CALL_COMPLETED,
            f"LLM Call Completed: {component}/{phase}",
            "INFO",
            component=component,
            phase=phase,
            **kwargs
        )


# ============================================================
# MIXIN 4: SessionMixin — управление сессиями
# ============================================================

class SessionMixin:
    """
    Миксин для управления сессиями.
    
    FEATURES:
    - Начало сессии
    - Завершение сессии
    - Статус сессии
    """

    async def start_session(self, goal: str, **kwargs):
        """Начало сессии."""
        await self._publish(
            EventType.SESSION_STARTED,
            f"Session started: {goal[:100]}...",
            "INFO",
            goal=goal,
            **kwargs
        )

    async def end_session(self, success: bool = True, result: Optional[str] = None, **kwargs):
        """Завершение сессии."""
        event_type = EventType.SESSION_COMPLETED if success else EventType.SESSION_FAILED
        status = "completed" if success else "failed"
        
        await self._publish(
            event_type,
            f"Session {status}",
            "INFO",
            success=success,
            result=result,
            **kwargs
        )

    async def log_session_step(self, step: int, action: str, result: Optional[str] = None, **kwargs):
        """Логирование шага сессии."""
        await self._publish(
            EventType.SESSION_STEP,
            f"Step {step}: {action}",
            "INFO",
            step=step,
            action=action,
            result=result,
            **kwargs
        )


# ============================================================
# MIXIN 5: SelfImprovementMixin — логирование самообучения
# ============================================================

class SelfImprovementMixin:
    """
    Миксин для логирования самообучения агента.
    
    FEATURES:
    - Запуск/завершение самообучения
    - Размышление (запрос и ответ LLM)
    - Принятие решений
    - Запуск действий
    - Отчёты
    """

    async def log_self_improvement_started(self, goal: str, capability: str = None, **kwargs):
        """Запуск самообучения."""
        await self._publish(
            EventType.SELF_IMPROVEMENT_STARTED,
            f"🧠 Самообучение запущено: {goal[:100]}...",
            "INFO",
            goal=goal,
            capability=capability,
            **kwargs
        )

    async def log_self_improvement_thinking(
        self,
        phase: str,
        system_prompt: str,
        user_prompt: str,
        response: str = None,
        tokens: int = None,
        duration_ms: float = None,
        success: bool = True,
        error: str = None,
        **kwargs
    ):
        """Логирование размышления (запрос + ответ от LLM)."""
        if not success:
            event_type = EventType.SELF_IMPROVEMENT_FAILED
            await self._publish(
                event_type,
                f"❌ Размышление не удалось: {error}",
                "ERROR",
                phase=phase,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=error,
                **kwargs
            )
        elif response:
            event_type = EventType.SELF_IMPROVEMENT_THINKING_COMPLETED
            await self._publish(
                event_type,
                f"✅ Размышление завершено ({len(response)} символов)",
                "INFO",
                phase=phase,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=response,
                tokens=tokens,
                duration_ms=duration_ms,
                **kwargs
            )
        else:
            event_type = EventType.SELF_IMPROVEMENT_THINKING_STARTED
            await self._publish(
                event_type,
                f"🔄 Размышление начато: {phase}",
                "INFO",
                phase=phase,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                **kwargs
            )

    async def log_self_improvement_decision(
        self,
        decision: str,
        reasoning: str = None,
        confidence: float = None,
        **kwargs
    ):
        """Логирование принятого решения."""
        await self._publish(
            EventType.SELF_IMPROVEMENT_DECISION,
            f"🎯 Решение принято: {decision}",
            "INFO",
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            **kwargs
        )

    async def log_self_improvement_action(
        self,
        action: str,
        parameters: dict = None,
        started: bool = True,
        result: str = None,
        success: bool = True,
        **kwargs
    ):
        """Логирование запущенного действия."""
        if started:
            event_type = EventType.SELF_IMPROVEMENT_ACTION_STARTED
            await self._publish(
                event_type,
                f"⚡ Запуск действия: {action}",
                "INFO",
                action=action,
                parameters=parameters,
                **kwargs
            )
        else:
            status = "успешно" if success else "с ошибкой"
            await self._publish(
                EventType.SELF_IMPROVEMENT_ACTION_COMPLETED,
                f"{'✅' if success else '❌'} Действие {action}: {status}",
                "INFO" if success else "ERROR",
                action=action,
                parameters=parameters,
                result=result,
                success=success,
                **kwargs
            )

    async def log_self_improvement_report(
        self,
        summary: str,
        metrics: dict = None,
        improvements: dict = None,
        **kwargs
    ):
        """Логирование отчёта о самообучении."""
        await self._publish(
            EventType.SELF_IMPROVEMENT_REPORT,
            f"📊 Отчёт: {summary[:100]}...",
            "INFO",
            summary=summary,
            metrics=metrics,
            improvements=improvements,
            **kwargs
        )

    async def log_self_improvement_completed(
        self,
        success: bool,
        summary: str = None,
        iterations: int = None,
        **kwargs
    ):
        """Завершение самообучения."""
        status = "завершено" if success else "не удалось"
        await self._publish(
            EventType.SELF_IMPROVEMENT_COMPLETED if success else EventType.SELF_IMPROVEMENT_FAILED,
            f"{'✅' if success else '❌'} Самообучение {status}",
            "INFO" if success else "ERROR",
            success=success,
            summary=summary,
            iterations=iterations,
            **kwargs
        )


# ============================================================
# MAIN CLASS: EventBusLogger (композит миксинов)
# ============================================================

class EventBusLogger(SyncLoggerMixin, AsyncLoggerMixin, LLMMixin, SessionMixin, SelfImprovementMixin):
    """
    Универсальный логгер через EventBus.
    
    КОМПОЗИЦИЯ:
    - SyncLoggerMixin — синхронный вывод
    - AsyncLoggerMixin — асинхронная публикация
    - LLMMixin — LLM логирование
    - SessionMixin — управление сессиями
    - SelfImprovementMixin — логирование самообучения
    
    USAGE:
    ```python
    logger = EventBusLogger(event_bus, session_id, agent_id, "my_component")
    await logger.info("Started")
    await logger.log_self_improvement_started(goal="Learn X")
    ```
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        session_id: str,
        agent_id: str,
        component: str = "unknown",
        get_init_state_callback: Optional[Callable[[], LoggerInitializationState]] = None
    ):
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
        self.component = component
        self._init_state = LoggerInitializationState.NOT_INITIALIZED
        self._get_init_state_callback = get_init_state_callback


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_logger(
    event_bus: UnifiedEventBus,
    session_id: str,
    agent_id: str,
    component: str = "unknown"
) -> EventBusLogger:
    """Создание логгера для компонента."""
    return EventBusLogger(event_bus, session_id, agent_id, component)


# ============================================================
# GLOBAL LOGGER
# ============================================================

_global_event_bus: Optional[UnifiedEventBus] = None
_default_logger: Optional[EventBusLogger] = None


async def init_logging_system(
    event_bus: Optional[UnifiedEventBus] = None,
    session_id: str = "system",
    agent_id: str = "system",
    **kwargs
):
    """Инициализация системы логирования."""
    global _global_event_bus, _default_logger

    print("🚀 Инициализация системы логирования...", flush=True)

    if event_bus is not None:
        _global_event_bus = event_bus
    else:
        from core.infrastructure.event_bus.unified_event_bus import get_event_bus
        _global_event_bus = get_event_bus()

    _default_logger = EventBusLogger(_global_event_bus, session_id, agent_id, 'system')

    print("✅ Система логирования инициализирована", flush=True)
    return _global_event_bus


async def shutdown_logging_system(timeout: float = 30.0):
    """Корректное завершение системы логирования."""
    global _global_event_bus, _default_logger

    if _global_event_bus:
        from core.infrastructure.event_bus.unified_event_bus import shutdown_event_bus
        await shutdown_event_bus(timeout=timeout)
        _global_event_bus = None
        _default_logger = None


def get_session_logger(session_id: str, agent_id: str = "unknown") -> EventBusLogger:
    """Получение логгера для сессии."""
    global _global_event_bus

    if _global_event_bus is None:
        from core.infrastructure.event_bus.unified_event_bus import get_event_bus
        _global_event_bus = get_event_bus()

    return EventBusLogger(_global_event_bus, session_id, agent_id, 'session')


def get_global_logger() -> Optional[EventBusLogger]:
    """Получение глобального логгера."""
    return _default_logger


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    # Enums
    'LoggerInitializationState',
    
    # Mixins
    'SyncLoggerMixin',
    'AsyncLoggerMixin',
    'LLMMixin',
    'SessionMixin',
    'SelfImprovementMixin',
    
    # Main class
    'EventBusLogger',
    
    # Factory
    'create_logger',
    
    # Global
    'init_logging_system',
    'shutdown_logging_system',
    'get_session_logger',
    'get_global_logger',
]

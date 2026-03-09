"""
EventBusLogger — единый API для логирования через EventBus.

ИСПОЛЬЗОВАНИЕ:
```python
class MyComponent:
    def __init__(self, event_bus, session_id, agent_id):
        self.logger = EventBusLogger(event_bus, session_id, agent_id, "my_component")

    async def do_something(self):
        await self.logger.info("Started")
        await self.logger.debug("Details", extra={"key": "value"})
```

АРХИТЕКТУРА ЛОГИРОВАНИЯ:
- Во время инициализации компонента (состояние CREATED → INITIALIZING → READY) 
  логи выводятся СИНХРОННО напрямую в stdout/stderr для гарантии порядка
- После инициализации (состояние READY) логи публикуются АСИНХРОННО через EventBus
- Переключение режима происходит автоматически при смене состояния компонента
"""
import asyncio
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Callable

from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


class LoggerInitializationState(Enum):
    """Состояние инициализации логгера."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"


class EventBusLogger:
    """
    Универсальный логгер через EventBus.

    Все сообщения публикуются как события LOG_INFO/DEBUG/WARNING/ERROR
    и обрабатываются подписчиками (TerminalHandler, FileHandler, LogCollector).

    FEATURES:
    - Автоматическое определение фазы инициализации
    - Синхронный вывод во время инициализации (гарантия порядка)
    - Асинхронная публикация после запуска (производительность)
    - Обработка ошибок с fallback на альтернативный канал

    ATTRIBUTES:
    - event_bus: Шина событий для публикации
    - session_id: ID сессии
    - agent_id: ID агента
    - component: Имя компонента-источника
    - _init_state: Текущее состояние инициализации
    - _get_init_state_callback: Callback для получения состояния компонента
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
        
        # Состояние инициализации (по умолчанию NOT_INITIALIZED)
        self._init_state = LoggerInitializationState.NOT_INITIALIZED
        # Callback для получения состояния от компонента
        self._get_init_state_callback = get_init_state_callback

    def _is_initializing(self) -> bool:
        """
        Проверка: находится ли компонент в фазе инициализации.
        
        Возвращает True если:
        - Явно установлено состояние INITIALIZING
        - Callback возвращает INITIALIZING или NOT_INITIALIZED
        
        Это означает что компонент ещё не готов и нужно использовать
        синхронный вывод для гарантии порядка логов.
        """
        if self._get_init_state_callback:
            state = self._get_init_state_callback()
            return state in (
                LoggerInitializationState.NOT_INITIALIZED,
                LoggerInitializationState.INITIALIZING
            )
        return self._init_state in (
            LoggerInitializationState.NOT_INITIALIZED,
            LoggerInitializationState.INITIALIZING
        )

    def _set_initializing(self):
        """Установить состояние INITIALIZING."""
        self._init_state = LoggerInitializationState.INITIALIZING

    def _set_ready(self):
        """Установить состояние READY (асинхронный режим)."""
        self._init_state = LoggerInitializationState.READY

    def _write_sync(self, message: str, level: str, stream=None):
        """
        Синхронная запись в stdout/stderr с обработкой ошибок.
        
        Если запись не удалась, пытается опубликовать событие через EventBus.
        
        ARGS:
        - message: Сообщение для записи
        - level: Уровень логирования (INFO, DEBUG, WARNING, ERROR)
        - stream: Поток для записи (sys.stdout или sys.stderr)
        """
        if stream is None:
            stream = sys.stderr if level in ("ERROR", "CRITICAL") else sys.stdout
        
        try:
            # Форматируем сообщение с префиксом
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] [{level}] [{self.component}] {message}"
            
            # Запись в поток с поддержкой UTF-8 в Windows
            try:
                stream.buffer.write((formatted + '\n').encode('utf-8'))
                stream.buffer.flush()
            except (AttributeError, UnicodeEncodeError):
                # Fallback для старых терминалов
                print(formatted, file=stream, flush=True)
                
        except Exception as e:
            # Fallback: попытка опубликовать через EventBus
            # Это предотвращает потерю логов при проблемах с stdout
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
                    "session_id": self.session_id,
                    "agent_id": self.agent_id,
                    "component": self.component,
                    "timestamp": datetime.now().isoformat() + 'Z',
                    "fallback_reason": f"stdout write failed: {e}"
                }
                
                # Синхронная публикация как последний шанс
                self.event_bus.publish_sync(
                    event_type=event_type,
                    data=data,
                    source=self.component,
                    session_id=self.session_id,
                    agent_id=self.agent_id
                )
            except Exception:
                # Полная неудача — ничего не можем сделать
                pass

    async def info(self, message: str, *args, **extra_data):
        """INFO сообщение (автоматический выбор режима)."""
        if args:
            message = message % args
        
        if self._is_initializing():
            # Синхронный вывод во время инициализации
            self._write_sync(message, "INFO")
        else:
            # Асинхронная публикация после инициализации
            await self._publish(EventType.LOG_INFO, message, "INFO", **extra_data)

    def info_sync(self, message: str, *args, **extra_data):
        """INFO сообщение (принудительно синхронная версия)."""
        if args:
            message = message % args
        self._write_sync(message, "INFO")

    async def debug(self, message: str, *args, **extra_data):
        """DEBUG сообщение (автоматический выбор режима)."""
        if args:
            message = message % args
        
        if self._is_initializing():
            self._write_sync(message, "DEBUG")
        else:
            await self._publish(EventType.LOG_DEBUG, message, "DEBUG", **extra_data)

    def debug_sync(self, message: str, *args, **extra_data):
        """DEBUG сообщение (принудительно синхронная версия)."""
        if args:
            message = message % args
        self._write_sync(message, "DEBUG")

    async def warning(self, message: str, *args, **extra_data):
        """WARNING сообщение (автоматический выбор режима)."""
        if args:
            message = message % args
        
        if self._is_initializing():
            self._write_sync(message, "WARNING")
        else:
            await self._publish(EventType.LOG_WARNING, message, "WARNING", **extra_data)

    def warning_sync(self, message: str, *args, **extra_data):
        """WARNING сообщение (принудительно синхронная версия)."""
        if args:
            message = message % args
        self._write_sync(message, "WARNING")

    async def error(self, message: str, *args, **extra_data):
        """ERROR сообщение (автоматический выбор режима)."""
        if args:
            message = message % args
        
        if self._is_initializing():
            self._write_sync(message, "ERROR")
        else:
            await self._publish(EventType.LOG_ERROR, message, "ERROR", **extra_data)

    def error_sync(self, message: str, *args, **extra_data):
        """ERROR сообщение (принудительно синхронная версия)."""
        if args:
            message = message % args
        self._write_sync(message, "ERROR")

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
        await self._publish(
            EventType.SESSION_COMPLETED if success else EventType.SESSION_FAILED,
            f"Session {'completed' if success else 'failed'}",
            "INFO",
            success=success,
            result=result,
            **kwargs
        )

    async def _publish(
        self,
        event_type: EventType,
        message: str,
        level: str,
        **extra_data
    ):
        """Публикация события в EventBus."""
        data = {
            "message": message,
            "level": level,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "component": self.component,
            "timestamp": datetime.now().isoformat() + 'Z',
            **extra_data
        }

        await self.event_bus.publish(
            event_type=event_type,
            data=data,
            source=self.component,
            session_id=self.session_id,
            agent_id=self.agent_id
        )

    def _publish_sync(
        self,
        event_type: EventType,
        message: str,
        level: str,
        **extra_data
    ):
        """Синхронная публикация события в EventBus."""
        data = {
            "message": message,
            "level": level,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "component": self.component,
            "timestamp": datetime.now().isoformat() + 'Z',
            **extra_data
        }

        self.event_bus.publish_sync(
            event_type=event_type,
            data=data,
            source=self.component,
            session_id=self.session_id,
            agent_id=self.agent_id
        )


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_logger(
    event_bus: UnifiedEventBus,
    session_id: str,
    agent_id: str,
    component: str = "unknown"
) -> EventBusLogger:
    """
    Создание логгера для компонента.
    
    ARGS:
        event_bus: Шина событий
        session_id: ID сессии
        agent_id: ID агента
        component: Имя компонента
    
    RETURNS:
        EventBusLogger для логирования
    """
    return EventBusLogger(event_bus, session_id, agent_id, component)


# =============================================================================
# GLOBAL LOGGER (для обратной совместимости и простого использования)
# =============================================================================

_global_event_bus: Optional[UnifiedEventBus] = None
_default_logger: Optional[EventBusLogger] = None


async def init_logging_system(
    event_bus: Optional[UnifiedEventBus] = None,
    session_id: str = "system",
    agent_id: str = "system",
    **kwargs
):
    """
    Инициализация системы логирования.
    
    USAGE:
        await init_logging_system(event_bus, session_id="my_session")
    
    ARGS:
        event_bus: Шина событий (если None, используется get_event_bus())
        session_id: ID сессии по умолчанию
        agent_id: ID агента по умолчанию
    """
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
    """
    Корректное завершение системы логирования.
    
    ARGS:
        timeout: Таймаут завершения
    """
    global _global_event_bus, _default_logger
    
    if _global_event_bus:
        from core.infrastructure.event_bus.unified_event_bus import shutdown_event_bus
        await shutdown_event_bus(timeout=timeout)
        _global_event_bus = None
        _default_logger = None


def get_session_logger(session_id: str, agent_id: str = "unknown") -> EventBusLogger:
    """
    Получение логгера для сессии.
    
    ARGS:
        session_id: ID сессии
        agent_id: ID агента
    
    RETURNS:
        EventBusLogger для сессии
    """
    global _global_event_bus
    
    if _global_event_bus is None:
        from core.infrastructure.event_bus.unified_event_bus import get_event_bus
        _global_event_bus = get_event_bus()
    
    return EventBusLogger(_global_event_bus, session_id, agent_id, 'session')


def get_global_logger() -> Optional[EventBusLogger]:
    """Получение глобального логгера."""
    return _default_logger

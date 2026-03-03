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
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


class EventBusLogger:
    """
    Универсальный логгер через EventBus.
    
    Все сообщения публикуются как события LOG_INFO/DEBUG/WARNING/ERROR
    и обрабатываются подписчиками (TerminalHandler, FileHandler, LogCollector).
    
    ATTRIBUTES:
    - event_bus: Шина событий для публикации
    - session_id: ID сессии
    - agent_id: ID агента
    - component: Имя компонента-источника
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        session_id: str,
        agent_id: str,
        component: str = "unknown"
    ):
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
        self.component = component

    async def info(self, message: str, *args, **extra_data):
        """INFO сообщение."""
        if args:
            message = message % args
        await self._publish(EventType.LOG_INFO, message, "INFO", **extra_data)

    def info_sync(self, message: str, *args, **extra_data):
        """INFO сообщение (синхронная версия)."""
        if args:
            message = message % args
        asyncio.create_task(self._publish(EventType.LOG_INFO, message, "INFO", **extra_data))

    async def debug(self, message: str, *args, **extra_data):
        """DEBUG сообщение."""
        if args:
            message = message % args
        await self._publish(EventType.LOG_DEBUG, message, "DEBUG", **extra_data)

    def debug_sync(self, message: str, *args, **extra_data):
        """DEBUG сообщение (синхронная версия)."""
        if args:
            message = message % args
        asyncio.create_task(self._publish(EventType.LOG_DEBUG, message, "DEBUG", **extra_data))

    async def warning(self, message: str, *args, **extra_data):
        """WARNING сообщение."""
        if args:
            message = message % args
        await self._publish(EventType.LOG_WARNING, message, "WARNING", **extra_data)

    def warning_sync(self, message: str, *args, **extra_data):
        """WARNING сообщение (синхронная версия)."""
        if args:
            message = message % args
        asyncio.create_task(self._publish(EventType.LOG_WARNING, message, "WARNING", **extra_data))

    async def error(self, message: str, *args, **extra_data):
        """ERROR сообщение."""
        if args:
            message = message % args
        await self._publish(EventType.LOG_ERROR, message, "ERROR", **extra_data)

    def error_sync(self, message: str, *args, **extra_data):
        """ERROR сообщение (синхронная версия)."""
        if args:
            message = message % args
        asyncio.create_task(self._publish(EventType.LOG_ERROR, message, "ERROR", **extra_data))

    async def exception(self, message: str, exc: Exception, **extra_data):
        """ERROR сообщение с исключением."""
        await self._publish(
            EventType.LOG_ERROR,
            f"{message}: {exc}",
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
    
    if event_bus is not None:
        _global_event_bus = event_bus
    else:
        from core.infrastructure.event_bus.unified_event_bus import get_event_bus
        _global_event_bus = get_event_bus()
    
    _default_logger = EventBusLogger(_global_event_bus, session_id, agent_id, 'system')
    
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

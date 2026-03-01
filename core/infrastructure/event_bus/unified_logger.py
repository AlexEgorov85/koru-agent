"""
Unified EventBusLogger — единый API для логирования через EventBus.

ЗАМЕНЯЕТ:
- logging.info/debug/warning/error
- SessionLogger
- EventBusLogger (старый)
- logging_to_event_bus
- init_logging_system/shutdown_logging_system

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
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from core.infrastructure.event_bus.event_bus_concurrent import EventBus, EventType, shutdown_event_bus


class EventBusLogger:
    """
    Универсальный логгер через EventBus.
    
    Все сообщения публикуются как события LOG_INFO/DEBUG/WARNING/ERROR
    и обрабатываются подписчиками (DevConsole, UserConsole, Archive).
    """

    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        agent_id: str,
        component: str = "unknown"
    ):
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
        self.component = component

    async def info(self, message: str, **extra_data):
        """INFO сообщение."""
        await self._publish(EventType.LOG_INFO, message, "INFO", **extra_data)

    async def debug(self, message: str, **extra_data):
        """DEBUG сообщение."""
        await self._publish(EventType.LOG_DEBUG, message, "DEBUG", **extra_data)

    async def warning(self, message: str, **extra_data):
        """WARNING сообщение."""
        await self._publish(EventType.LOG_WARNING, message, "WARNING", **extra_data)

    async def error(self, message: str, **extra_data):
        """ERROR сообщение."""
        await self._publish(EventType.LOG_ERROR, message, "ERROR", **extra_data)

    async def exception(self, message: str, exc: Exception, **extra_data):
        """ERROR сообщение с исключением."""
        await self._publish(
            EventType.LOG_ERROR,
            f"{message}: {exc}",
            "ERROR",
            exception_type=type(exc).__name__,
            **extra_data
        )

    async def log_llm_prompt(self, component: str, phase: str, system_prompt: str, user_prompt: str, **kwargs):
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

    async def log_llm_response(self, component: str, phase: str, response: Any, tokens: Optional[int] = None, latency_ms: Optional[float] = None, **kwargs):
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
        """Публикация события."""
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

    # Синхронные версии для backward compatibility
    def info_sync(self, message: str, **extra_data):
        asyncio.create_task(self.info(message, **extra_data))

    def debug_sync(self, message: str, **extra_data):
        asyncio.create_task(self.debug(message, **extra_data))

    def warning_sync(self, message: str, **extra_data):
        asyncio.create_task(self.warning(message, **extra_data))

    def error_sync(self, message: str, **extra_data):
        asyncio.create_task(self.error(message, **extra_data))


# =============================================================================
# FACTORY
# =============================================================================

def create_logger(
    event_bus: EventBus,
    session_id: str,
    agent_id: str,
    component: str = "unknown"
) -> EventBusLogger:
    """Создание логгера."""
    return EventBusLogger(event_bus, session_id, agent_id, component)


# =============================================================================
# BACKWARD COMPATIBILITY — ЗАМЕНА legacy logging
# =============================================================================

_global_event_bus: Optional[EventBus] = None
_default_session_id: str = "system"
_default_agent_id: str = "system"
_default_logger: Optional[EventBusLogger] = None


async def init_logging_system(config: Optional[Dict] = None, **kwargs):
    """
    ЗАМЕНА: core.infrastructure.logging.init_logging_system
    
    Инициализация системы логирования через EventBus.
    """
    global _global_event_bus, _default_session_id, _default_agent_id, _default_logger
    
    # EventBus уже инициализирован в InfrastructureContext
    # Эта функция теперь просто настраивает глобальный logger
    from core.infrastructure.event_bus.event_bus_concurrent import get_event_bus
    
    _global_event_bus = get_event_bus()
    _default_session_id = kwargs.get('session_id', 'system')
    _default_agent_id = kwargs.get('agent_id', 'system')
    _default_logger = EventBusLogger(_global_event_bus, _default_session_id, _default_agent_id, 'legacy')
    
    return _global_event_bus


async def shutdown_logging_system(timeout: float = 30.0):
    """
    ЗАМЕНА: core.infrastructure.logging.shutdown_logging_system
    
    Корректное завершение системы логирования.
    """
    global _global_event_bus, _default_logger
    
    if _global_event_bus:
        await shutdown_event_bus(timeout=timeout)
        _global_event_bus = None
        _default_logger = None


def get_session_logger(session_id: str, agent_id: str = "unknown") -> EventBusLogger:
    """
    ЗАМЕНА: core.infrastructure.logging.get_session_logger
    
    Получение логгера для сессии.
    """
    if _global_event_bus is None:
        from core.infrastructure.event_bus.event_bus_concurrent import get_event_bus
        _global_event_bus = get_event_bus()
    
    return EventBusLogger(_global_event_bus, session_id, agent_id, 'session')


def get_log_manager():
    """Заглушка для обратной совместимости."""
    return None


def get_log_manager():
    """Заглушка для обратной совместимости."""
    class FakeLogManager:
        is_initialized = False
        async def shutdown(self): pass
    return FakeLogManager()

"""
Unified EventBusLogger — единый API для логирования через EventBus.

ЗАМЕНЯЕТ:
- logging.info/debug/warning/error
- SessionLogger
- EventBusLogger (старый)
- logging_to_event_bus

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

from core.infrastructure.event_bus.event_bus_concurrent import EventBus, EventType


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
# BACKWARD COMPATIBILITY
# =============================================================================

# Для кода который использует logging.info() напрямую
# Перенаправляем на EventBusLogger через глобальный event_bus

_global_event_bus: Optional[EventBus] = None
_default_session_id: str = "system"
_default_agent_id: str = "system"


def setup_global_logger(event_bus: EventBus, session_id: str, agent_id: str):
    """Настройка глобального логгера для legacy кода."""
    global _global_event_bus, _default_session_id, _default_agent_id
    _global_event_bus = event_bus
    _default_session_id = session_id
    _default_agent_id = agent_id


def legacy_info(message: str, **kwargs):
    """Legacy logging.info replacement."""
    if _global_event_bus:
        logger = EventBusLogger(_global_event_bus, _default_session_id, _default_agent_id, "legacy")
        logger.info_sync(message, **kwargs)


def legacy_debug(message: str, **kwargs):
    """Legacy logging.debug replacement."""
    if _global_event_bus:
        logger = EventBusLogger(_global_event_bus, _default_session_id, _default_agent_id, "legacy")
        logger.debug_sync(message, **kwargs)


def legacy_warning(message: str, **kwargs):
    """Legacy logging.warning replacement."""
    if _global_event_bus:
        logger = EventBusLogger(_global_event_bus, _default_session_id, _default_agent_id, "legacy")
        logger.warning_sync(message, **kwargs)


def legacy_error(message: str, **kwargs):
    """Legacy logging.error replacement."""
    if _global_event_bus:
        logger = EventBusLogger(_global_event_bus, _default_session_id, _default_agent_id, "legacy")
        logger.error_sync(message, **kwargs)

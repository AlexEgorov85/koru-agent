"""
Типы событий для системы логирования.

АРХИТЕКТУРА:
- LogEventType — DEPRECATED алиас на EventType для обратной совместимости
- Используйте напрямую EventType из core.infrastructure.event_bus.unified_event_bus
- Для проверки на логируемость: event_type.is_loggable

USAGE:
```python
# НОВЫЙ СПОСОБ (рекомендуется)
from core.infrastructure.event_bus.unified_event_bus import EventType

log.info("Поиск информации...", extra={"event_type": EventType.USER_PROGRESS})

# СТАРЫЙ СПОСОБ (DEPRECATED, будет удалён)
from core.infrastructure.event_bus.unified_event_bus import EventType

log.info("Поиск информации...", extra={"event_type": EventType.USER_PROGRESS})
```
"""
from enum import Enum


# =============================================================================
# DEPRECATED: LogEventType — алиас на EventType для обратной совместимости
# =============================================================================
# Этот класс будет удалён в следующей мажорной версии.
# Используйте напрямую EventType из core.infrastructure.event_bus.unified_event_bus


class LogEventType(str, Enum):
    """
    DEPRECATED: Использовать EventType из unified_event_bus.
    
    Этот класс оставлен только для обратной совместимости.
    Все новые компоненты должны использовать EventType.
    """

    # === Пользовательский интерфейс ===
    USER_PROGRESS = "USER_PROGRESS"
    USER_RESULT = "USER_RESULT"
    USER_MESSAGE = "USER_MESSAGE"
    USER_QUESTION = "USER_QUESTION"

    # === Агент ===
    AGENT_START = "AGENT_START"
    AGENT_STOP = "AGENT_STOP"
    AGENT_THINKING = "AGENT_THINKING"
    AGENT_DECISION = "AGENT_DECISION"
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_UPDATED = "PLAN_UPDATED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_TIMEOUT = "STEP_TIMEOUT"
    STEP_ERROR = "STEP_ERROR"
    STEP_FALLBACK_TRIGGERED = "STEP_FALLBACK_TRIGGERED"
    STEP_FALLBACK_SUCCESS = "STEP_FALLBACK_SUCCESS"
    STEP_FALLBACK_FAILED = "STEP_FALLBACK_FAILED"
    STEP_EXHAUSTED = "STEP_EXHAUSTED"

    # === Инструменты ===
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    TOOL_ERROR = "TOOL_ERROR"

    # === LLM ===
    LLM_CALL = "LLM_CALL"
    LLM_CALL_REQUEST = "LLM_CALL_REQUEST"
    LLM_CALL_RESPONSE = "LLM_CALL_RESPONSE"
    LLM_CALL_START = "LLM_CALL_START"
    LLM_CALL_END = "LLM_CALL_END"
    LLM_RESPONSE = "LLM_RESPONSE"
    LLM_ERROR = "LLM_ERROR"

    # === Базы данных ===
    DB_QUERY = "DB_QUERY"
    DB_RESULT = "DB_RESULT"
    DB_ERROR = "DB_ERROR"

    # === Инфраструктура ===
    SYSTEM_INIT = "SYSTEM_INIT"
    SYSTEM_READY = "SYSTEM_READY"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_ERROR = "SYSTEM_ERROR"

    # === Стандартные уровни (как event_type) ===
    INFO = "INFO"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def to_event_type(cls, log_event_type: "LogEventType") -> "EventType":
        """
        Конвертация LogEventType в EventType.
        
        DEPRECATED: Используйте напрямую EventType
        """
        from core.infrastructure.event_bus.unified_event_bus import EventType
        
        return EventType.from_log_event_type(log_event_type.name)

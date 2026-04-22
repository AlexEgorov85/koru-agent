"""
Типы событий для системы логирования.

АРХИТЕКТУРА:
- ОТДЕЛЬНЫЙ enum от EventType (EventBus) — логирование не зависит от шины
- Используется через extra={"event_type": LogEventType.XXX} в logging вызовах
- Фильтруется EventTypeFilter в StreamHandler (консоль/UI)

USAGE:
```python
import logging
from core.infrastructure.logging.event_types import LogEventType

log = logging.getLogger(__name__)
log.info("Поиск информации...", extra={"event_type": LogEventType.USER_PROGRESS})
```
"""
from enum import Enum


class LogEventType(str, Enum):
    """
    Типы событий для логирования.

    КАТЕГОРИИ:
    - USER_* — вывод в UI/терминал для пользователя
    - AGENT_* — действия агента
    - TOOL_* — вызовы инструментов
    - LLM_* — LLM вызовы
    - DB_* — запросы к БД
    - SYSTEM_* — системные события
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

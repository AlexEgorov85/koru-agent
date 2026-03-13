"""
Structured Logging для Agent_v5.

ИНТЕГРАЦИЯ С STRUCTLOG:
```python
from core.infrastructure.logging.structured import get_structured_logger

logger = get_structured_logger("my_component")
logger.info("user_action", user_id=123, action="login")
```

ПРЕИМУЩЕСТВА:
- Автоматическое добавление timestamp, level, logger
- JSON формат для легкого парсинга
- Совместимость с ELK/Loki/Grafana
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from contextlib import contextmanager


# ============================================================
# STRUCTURED LOGGING MIXIN
# ============================================================

class StructuredLoggerMixin:
    """
    Миксин для структурированного логирования.
    
    FEATURES:
    - JSON форматирование
    - Автоматические поля (timestamp, level, logger)
    - Поддержка extra данных
    """
    
    def _format_structured(
        self,
        message: str,
        level: str,
        logger_name: str = "unknown",
        **extra
    ) -> str:
        """
        Форматирование сообщения в структурированном формате.
        
        ARGS:
        - message: Сообщение
        - level: Уровень логирования
        - logger_name: Имя логгера
        - **extra: Дополнительные данные
        
        RETURNS:
        - JSON строка
        """
        log_entry = {
            "timestamp": datetime.now().isoformat() + 'Z',
            "level": level,
            "logger": logger_name,
            "message": message,
            **extra
        }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)
    
    def log_structured(
        self,
        event_type: str,
        message: str,
        **data
    ):
        """
        Логирование структурированного события.
        
        ARGS:
        - event_type: Тип события
        - message: Сообщение
        - **data: Данные события
        """
        structured = self._format_structured(
            message,
            "INFO",
            getattr(self, 'component', 'unknown'),
            event_type=event_type,
            **data
        )
        
        # Публикация через EventBus если доступен
        event_bus = getattr(self, 'event_bus', None)
        if event_bus:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            asyncio.create_task(event_bus.publish(
                EventType.LOG_INFO,
                {"message": structured, "structured": True},
                source=getattr(self, 'component', 'unknown')
            ))
        else:
            # Fallback на stdout
            print(structured, flush=True)


# ============================================================
# CONTEXT VARIABLES
# ============================================================

import contextvars

# Контекстные переменные для логирования
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'session_id',
    default='system'
)
agent_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'agent_id',
    default='system'
)
step_number_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    'step_number',
    default=0
)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id',
    default=None
)


# ============================================================
# CONTEXT MANAGER
# ============================================================

@contextmanager
def log_context(
    session_id: str = None,
    agent_id: str = None,
    step_number: int = None,
    correlation_id: str = None
):
    """
    Контекстный менеджер для установки контекста логирования.
    
    USAGE:
    ```python
    with log_context(session_id="sess_123", agent_id="agent_001"):
        logger.info("Action in context")
    ```
    
    ARGS:
    - session_id: ID сессии
    - agent_id: ID агента
    - step_number: Номер шага
    - correlation_id: ID корреляции
    """
    tokens = {}
    
    if session_id is not None:
        tokens['session'] = session_id_var.set(session_id)
    if agent_id is not None:
        tokens['agent'] = agent_id_var.set(agent_id)
    if step_number is not None:
        tokens['step'] = step_number_var.set(step_number)
    if correlation_id is not None:
        tokens['correlation'] = correlation_id_var.set(correlation_id)
    
    try:
        yield
    finally:
        # Восстановление контекста
        if 'session' in tokens:
            session_id_var.reset(tokens['session'])
        if 'agent' in tokens:
            agent_id_var.reset(tokens['agent'])
        if 'step' in tokens:
            step_number_var.reset(tokens['step'])
        if 'correlation' in tokens:
            correlation_id_var.reset(tokens['correlation'])


# ============================================================
# CONTEXTUAL LOGGER
# ============================================================

class ContextualLoggerMixin:
    """
    Миксин для контекстного логирования.
    
    FEATURES:
    - Автоматическое добавление контекста (session_id, agent_id, step)
    - Не нужно передавать контекст в каждый вызов
    - Легкая трассировка по сессиям
    """
    
    def _get_context(self) -> Dict[str, Any]:
        """
        Получение текущего контекста логирования.
        
        RETURNS:
        - Dict с контекстными данными
        """
        return {
            "session_id": session_id_var.get(),
            "agent_id": agent_id_var.get(),
            "step_number": step_number_var.get(),
            "correlation_id": correlation_id_var.get(),
        }
    
    def _add_context_to_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Добавление контекста к данным.
        
        ARGS:
        - data: Исходные данные
        
        RETURNS:
        - Данные с контекстом
        """
        context = self._get_context()
        
        # Фильтруем None значения
        context = {k: v for k, v in context.items() if v is not None}
        
        return {**context, **data}


# ============================================================
# HEALTH CHECK
# ============================================================

import asyncio
import time

class LoggingHealthCheck:
    """
    Проверка здоровья системы логирования.
    
    FEATURES:
    - Мониторинг дискового пространства
    - Проверка возраста логов
    - Измерение задержки записи
    - Интеграция с Prometheus/Grafana
    """
    
    def __init__(self, logs_dir: Path = None):
        self.logs_dir = logs_dir or Path("logs")
    
    async def check(self) -> Dict[str, Any]:
        """
        Проверка здоровья.
        
        RETURNS:
        - Dict со статусом и метриками
        """
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat() + 'Z',
            "metrics": {}
        }
        
        # Проверка дискового пространства
        disk_usage = self._get_disk_usage()
        result["metrics"]["disk_usage_mb"] = disk_usage
        
        if disk_usage > 10000:  # > 10 GB
            result["status"] = "warning"
            result["metrics"]["disk_warning"] = "High disk usage"
        
        # Проверка возраста логов
        oldest_age = self._get_oldest_log_age()
        result["metrics"]["oldest_log_age_days"] = oldest_age
        
        # Измерение задержки записи
        write_latency = await self._measure_write_latency()
        result["metrics"]["write_latency_ms"] = write_latency
        
        if write_latency > 1000:  # > 1 second
            result["status"] = "warning"
            result["metrics"]["latency_warning"] = "High write latency"
        
        return result
    
    def _get_disk_usage(self) -> float:
        """Получение использования диска (MB)."""
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.logs_dir)
            return used / (1024 * 1024)
        except OSError:
            return 0.0
    
    def _get_oldest_log_age(self) -> int:
        """Получение возраста старейшего лога (дни)."""
        try:
            oldest = None
            for log_file in self.logs_dir.rglob("*.log"):
                mtime = log_file.stat().st_mtime
                if oldest is None or mtime < oldest:
                    oldest = mtime
            
            if oldest:
                age_seconds = time.time() - oldest
                return int(age_seconds / (24 * 3600))
            return 0
        except OSError:
            return 0
    
    async def _measure_write_latency(self) -> float:
        """Измерение задержки записи (ms)."""
        try:
            test_file = self.logs_dir / ".health_check_test"
            
            start = time.perf_counter()
            test_file.write_text("health check\n", encoding='utf-8')
            test_file.unlink()
            end = time.perf_counter()
            
            return (end - start) * 1000  # ms
        except OSError:
            return float('inf')
    
    def get_metrics_for_prometheus(self) -> str:
        """
        Получение метрик для Prometheus.
        
        RETURNS:
        - Строка в формате Prometheus
        """
        import asyncio
        
        result = asyncio.run(self.check())
        
        lines = []
        lines.append(f"# HELP logging_disk_usage_mb Disk usage in MB")
        lines.append(f"# TYPE logging_disk_usage_mb gauge")
        lines.append(f"logging_disk_usage_mb {result['metrics'].get('disk_usage_mb', 0)}")
        
        lines.append(f"# HELP logging_oldest_log_age_days Oldest log age in days")
        lines.append(f"# TYPE logging_oldest_log_age_days gauge")
        lines.append(f"logging_oldest_log_age_days {result['metrics'].get('oldest_log_age_days', 0)}")
        
        lines.append(f"# HELP logging_write_latency_ms Write latency in ms")
        lines.append(f"# TYPE logging_write_latency_ms gauge")
        lines.append(f"logging_write_latency_ms {result['metrics'].get('write_latency_ms', 0)}")
        
        lines.append(f"# HELP logging_health_status Health status (0=healthy, 1=warning, 2=critical)")
        lines.append(f"# TYPE logging_health_status gauge")
        status_map = {"healthy": 0, "warning": 1, "critical": 2}
        lines.append(f"logging_health_status {status_map.get(result['status'], 0)}")
        
        return "\n".join(lines)


# ============================================================
# INTEGRATION WITH EVENTBUSLOGGER
# ============================================================

def patch_event_bus_logger():
    """
    Добавление structured/contextual logging в EventBusLogger.
    
    USAGE:
    ```python
    from core.infrastructure.logging.structured import patch_event_bus_logger
    patch_event_bus_logger()
    ```
    """
    from core.infrastructure.logging.logger import EventBusLogger
    
    # Добавляем миксины
    if StructuredLoggerMixin not in EventBusLogger.__bases__:
        EventBusLogger.__bases__ = (
            StructuredLoggerMixin,
            ContextualLoggerMixin,
        ) + EventBusLogger.__bases__
    
    # Добавляем методы
    if not hasattr(EventBusLogger, 'log_structured'):
        EventBusLogger.log_structured = StructuredLoggerMixin.log_structured
    
    if not hasattr(EventBusLogger, '_get_context'):
        EventBusLogger._get_context = ContextualLoggerMixin._get_context
    
    if not hasattr(EventBusLogger, '_add_context_to_data'):
        EventBusLogger._add_context_to_data = ContextualLoggerMixin._add_context_to_data


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    # Mixins
    'StructuredLoggerMixin',
    'ContextualLoggerMixin',
    
    # Context
    'session_id_var',
    'agent_id_var',
    'step_number_var',
    'correlation_id_var',
    'log_context',
    
    # Health Check
    'LoggingHealthCheck',
    
    # Integration
    'patch_event_bus_logger',
]

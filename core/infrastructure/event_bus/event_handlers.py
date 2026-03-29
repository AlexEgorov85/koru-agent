"""
Обработчики событий для системы агентов.
ОСОБЕННОСТИ:
- Обработчики для замены логирования
- Поддержка различных способов обработки событий
"""
import json
import os
from datetime import datetime
from typing import Dict, Any
from core.infrastructure.event_bus.unified_event_bus import Event, EventType


AUDIT_EVENT_TYPES = {
    EventType.CAPABILITY_SELECTED,
    EventType.SKILL_EXECUTED,
    EventType.ACTION_PERFORMED,
    EventType.LLM_CALL_STARTED,
    EventType.LLM_CALL_COMPLETED,
    EventType.ERROR_OCCURRED,
    EventType.SYSTEM_ERROR,
    EventType.PLAN_CREATED,
    EventType.AGENT_COMPLETED
}


class MetricsEventHandler:
    """
    Обработчик событий для сбора метрик.
    
    FEATURES:
    - Сбор статистики по типам событий
    - Отслеживание производительности
    - Подсчет количества событий
    """
    
    def __init__(self):
        self.metrics: Dict[str, int] = {}
        self.start_times: Dict[str, datetime] = {}
    
    async def handle(self, event: Event):
        """Обработка события - обновление метрик."""
        event_type_str = event.type if isinstance(event.type, str) else event.type.value
        
        if event_type_str not in self.metrics:
            self.metrics[event_type_str] = 0
        self.metrics[event_type_str] += 1
        
        if event.type == EventType.LLM_CALL_STARTED:
            if event.correlation_id:
                self.start_times[event.correlation_id] = event.timestamp
        
        elif event.type == EventType.LLM_CALL_COMPLETED:
            if event.correlation_id and event.correlation_id in self.start_times:
                duration = (event.timestamp - self.start_times[event.correlation_id]).total_seconds()
                del self.start_times[event.correlation_id]


class AuditEventHandler:
    """
    Обработчик событий для аудита безопасности.
    
    FEATURES:
    - Отслеживание критических действий
    - Логирование попыток выполнения опасных операций
    - Мониторинг аномального поведения
    """
    
    def __init__(self, audit_log_dir: str = "logs/audit"):
        self.audit_log_dir = audit_log_dir
        os.makedirs(audit_log_dir, exist_ok=True)

    async def handle(self, event: Event):
        """Обработка события - запись в аудит."""
        event_type_value = event.type.value if hasattr(event.type, 'value') else event.type
        
        if event_type_value in {e.value for e in AUDIT_EVENT_TYPES}:
            timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            audit_entry = {
                "timestamp": timestamp,
                "event_type": event_type_value,
                "source": event.source,
                "correlation_id": event.correlation_id,
                "data": event.data
            }

            date_suffix = datetime.now().strftime("%Y%m%d")
            audit_filename = f"audit_{date_suffix}.log"
            audit_filepath = os.path.join(self.audit_log_dir, audit_filename)

            with open(audit_filepath, "a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
                audit_file.flush()
                os.fsync(audit_file.fileno())


class DebuggingEventHandler:
    """
    Обработчик событий для отладки.
    
    FEATURES:
    - Подробная информация о каждом событии
    - Возможность фильтрации по источникам
    - Поддержка трассировки цепочек событий
    """
    
    def __init__(self, debug_log_dir: str = "logs/debug", sources_filter: list = None):
        self.debug_log_dir = debug_log_dir
        self.sources_filter = sources_filter or []
        os.makedirs(debug_log_dir, exist_ok=True)
    
    async def handle(self, event: Event):
        """Обработка события - запись в отладочный лог."""
        if self.sources_filter and event.source not in self.sources_filter:
            return
        
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        event_type_value = event.type.value if hasattr(event.type, 'value') else event.type
        debug_entry = {
            "timestamp": timestamp,
            "event_type": event_type_value,
            "source": event.source,
            "correlation_id": event.correlation_id,
            "data": event.data
        }
        
        date_suffix = datetime.now().strftime("%Y%m%d_%H")
        debug_filename = f"debug_{date_suffix}.log"
        debug_filepath = os.path.join(self.debug_log_dir, debug_filename)
        
        with open(debug_filepath, "a", encoding="utf-8") as debug_file:
            debug_file.write(json.dumps(debug_entry, ensure_ascii=False, indent=2) + "\n\n")


class LoggingEventHandler:
    """
    Обработчик событий для логирования.
    
    FEATURES:
    - Обработка LOG_INFO, LOG_DEBUG, LOG_WARNING, LOG_ERROR событий
    - Вывод в stdout/stderr
    """
    
    def __init__(self, min_level: str = "DEBUG"):
        self.min_level = min_level
        self.levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    
    async def handle(self, event: Event):
        """Обработка события логирования."""
        event_type_value = event.type.value if hasattr(event.type, 'value') else event.type
        
        if event_type_value not in {"log.info", "log.debug", "log.warning", "log.error"}:
            return
        
        level = event.data.get("level", "INFO").upper()
        message = event.data.get("message", "")
        
        if self.levels.get(level, 0) < self.levels.get(self.min_level, 0):
            return
        
        output = f"[{level}] {message}"
        if level == "ERROR":
            print(output, file=sys.stderr)
        else:
            print(output)


import sys
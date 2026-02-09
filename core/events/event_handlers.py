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
from core.events.event_bus import Event, EventType


class LoggingEventHandler:
    """
    Обработчик событий, который заменяет традиционное логирование.
    
    FEATURES:
    - Запись событий в файлы
    - Форматирование событий в читаемом виде
    - Поддержка различных уровней важности
    """
    
    def __init__(self, log_dir: str = "logs", log_file_prefix: str = "agent_events"):
        """
        Инициализация обработчика событий.
        
        ARGS:
        - log_dir: директория для логов
        - log_file_prefix: префикс для файлов логов
        """
        self.log_dir = log_dir
        self.log_file_prefix = log_file_prefix
        os.makedirs(log_dir, exist_ok=True)
        
        # Определяем уровень важности для каждого типа события
        self.event_severity = {
            EventType.SYSTEM_ERROR: "ERROR",
            EventType.AGENT_FAILED: "ERROR",
            EventType.LLM_CALL_FAILED: "ERROR",
            EventType.ERROR_OCCURRED: "ERROR",
            
            EventType.RETRY_ATTEMPT: "WARNING",
            
            EventType.SYSTEM_INITIALIZED: "INFO",
            EventType.AGENT_CREATED: "INFO",
            EventType.AGENT_STARTED: "INFO",
            EventType.CAPABILITY_SELECTED: "INFO",
            EventType.SKILL_EXECUTED: "INFO",
            EventType.ACTION_PERFORMED: "INFO",
            EventType.CONTEXT_ITEM_ADDED: "INFO",
            EventType.PLAN_CREATED: "INFO",
            EventType.PROVIDER_REGISTERED: "INFO",
            
            EventType.SYSTEM_SHUTDOWN: "DEBUG",
            EventType.AGENT_COMPLETED: "DEBUG",
            EventType.STEP_REGISTERED: "DEBUG",
            EventType.LLM_CALL_STARTED: "DEBUG",
            EventType.LLM_CALL_COMPLETED: "DEBUG",
        }
    
    def handle_event(self, event: Event):
        """
        Обработка события - запись в лог.
        
        ARGS:
        - event: событие для обработки
        """
        # Определяем уровень важности
        severity = self.event_severity.get(event.event_type, "INFO")
        
        # Форматируем сообщение
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        formatted_message = (
            f"{timestamp} - {severity} - {event.source} - "
            f"{event.event_type} - {json.dumps(event.data, ensure_ascii=False, default=str)}"
        )
        
        # Определяем имя файла лога
        date_suffix = datetime.now().strftime("%Y%m%d")
        log_filename = f"{self.log_file_prefix}_{date_suffix}.log"
        log_filepath = os.path.join(self.log_dir, log_filename)
        
        # Записываем в файл
        with open(log_filepath, "a", encoding="utf-8") as log_file:
            log_file.write(formatted_message + "\n")


class MetricsEventHandler:
    """
    Обработчик событий для сбора метрик.
    
    FEATURES:
    - Сбор статистики по типам событий
    - Отслеживание производительности
    - Подсчет количества событий
    """
    
    def __init__(self):
        """
        Инициализация обработчика метрик.
        """
        self.metrics = {}
        self.start_times = {}  # Для отслеживания времени выполнения
    
    def handle_event(self, event: Event):
        """
        Обработка события - обновление метрик.
        
        ARGS:
        - event: событие для обработки
        """
        # Увеличиваем счетчик для типа события
        event_type = str(event.event_type)
        if event_type not in self.metrics:
            self.metrics[event_type] = 0
        self.metrics[event_type] += 1
        
        # Обработка специфичных для метрик событий
        if event.event_type == EventType.LLM_CALL_STARTED:
            # Сохраняем время начала вызова LLM
            correlation_id = event.correlation_id
            if correlation_id:
                self.start_times[correlation_id] = event.timestamp
        
        elif event.event_type == EventType.LLM_CALL_COMPLETED:
            # Рассчитываем время выполнения вызова LLM
            correlation_id = event.correlation_id
            if correlation_id and correlation_id in self.start_times:
                duration = (event.timestamp - self.start_times[correlation_id]).total_seconds()
                # Здесь можно добавить логику для сохранения метрики производительности
                del self.start_times[correlation_id]


class AuditEventHandler:
    """
    Обработчик событий для аудита безопасности.
    
    FEATURES:
    - Отслеживание критических действий
    - Логирование попыток выполнения опасных операций
    - Мониторинг аномального поведения
    """
    
    def __init__(self, audit_log_dir: str = "logs/audit"):
        """
        Инициализация обработчика аудита.
        
        ARGS:
        - audit_log_dir: директория для логов аудита
        """
        self.audit_log_dir = audit_log_dir
        os.makedirs(audit_log_dir, exist_ok=True)
        
        # Определяем события, требующие аудита
        self.audit_events = {
            EventType.CAPABILITY_SELECTED,
            EventType.SKILL_EXECUTED,
            EventType.ACTION_PERFORMED,
            EventType.LLM_CALL_STARTED,
            EventType.LLM_CALL_COMPLETED,
            EventType.ERROR_OCCURRED,
            EventType.SYSTEM_ERROR
        }
    
    def handle_event(self, event: Event):
        """
        Обработка события - запись в аудит.
        
        ARGS:
        - event: событие для обработки
        """
        if event.event_type in self.audit_events:
            # Форматируем сообщение аудита
            timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            audit_entry = {
                "timestamp": timestamp,
                "event_type": str(event.event_type),
                "source": event.source,
                "correlation_id": event.correlation_id,
                "data": event.data
            }
            
            # Определяем имя файла аудита
            date_suffix = datetime.now().strftime("%Y%m%d")
            audit_filename = f"audit_{date_suffix}.log"
            audit_filepath = os.path.join(self.audit_log_dir, audit_filename)
            
            # Записываем в файл аудита
            with open(audit_filepath, "a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")


class DebuggingEventHandler:
    """
    Обработчик событий для отладки.
    
    FEATURES:
    - Подробная информация о каждом событии
    - Возможность фильтрации по источникам
    - Поддержка трассировки цепочек событий
    """
    
    def __init__(self, debug_log_dir: str = "logs/debug", sources_filter: list = None):
        """
        Инициализация обработчика отладки.
        
        ARGS:
        - debug_log_dir: директория для логов отладки
        - sources_filter: список источников для фильтрации (None = все источники)
        """
        self.debug_log_dir = debug_log_dir
        self.sources_filter = sources_filter or []
        os.makedirs(debug_log_dir, exist_ok=True)
    
    def handle_event(self, event: Event):
        """
        Обработка события - запись в отладочный лог.
        
        ARGS:
        - event: событие для обработки
        """
        # Фильтрация по источникам, если задан фильтр
        if self.sources_filter and event.source not in self.sources_filter:
            return
        
        # Форматируем подробное сообщение отладки
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        debug_entry = {
            "timestamp": timestamp,
            "event_type": str(event.event_type),
            "source": event.source,
            "correlation_id": event.correlation_id,
            "data": event.data
        }
        
        # Определяем имя файла отладки
        date_suffix = datetime.now().strftime("%Y%m%d_%H")
        debug_filename = f"debug_{date_suffix}.log"
        debug_filepath = os.path.join(self.debug_log_dir, debug_filename)
        
        # Записываем в файл отладки
        with open(debug_filepath, "a", encoding="utf-8") as debug_file:
            debug_file.write(json.dumps(debug_entry, ensure_ascii=False, indent=2) + "\n\n")
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
from core.infrastructure.event_bus.event_bus import Event, EventType


# Определяем события, требующие аудита
AUDIT_EVENTS = {
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

    def handle_event(self, event: Event):
        """
        Обработка события - запись в аудит.

        ARGS:
        - event: событие для обработки
        """
        if event.event_type in AUDIT_EVENTS:
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

            # Записываем в файл аудита с синхронной записью
            with open(audit_filepath, "a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
                audit_file.flush()  # Сброс буфера
                os.fsync(audit_file.fileno())  # Синхронная запись на диск


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
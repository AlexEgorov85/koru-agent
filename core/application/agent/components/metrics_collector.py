"""
MetricsCollector — сборщик метрик выполнения агента.

АРХИТЕКТУРА:
- Собирает метрики выполнения шагов
- Публикует метрики через EventBus
- Агрегирует статистику по сессии
- Минимальная реализация без внешних зависимостей

ОТВЕТСТВЕННОСТЬ:
- Запись времени выполнения шагов
- Подсчёт успешных/неуспешных шагов
- Агрегация статистики
- Публикация событий с метриками
"""
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StepMetrics:
    """Метрики одного шага."""
    step_number: int
    capability: str
    status: str  # "completed", "failed", "aborted"
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    error_type: Optional[str] = None
    retry_count: int = 0


@dataclass
class SessionMetrics:
    """Агрегированные метрики сессии."""
    session_id: str
    goal: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    total_execution_time_ms: float = 0.0
    avg_step_time_ms: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    capabilities_used: Dict[str, int] = field(default_factory=dict)
    pattern_switches: int = 0
    
    def add_step(self, step_metrics: StepMetrics):
        """Добавить метрики шага."""
        self.total_steps += 1
        
        if step_metrics.status == "completed":
            self.successful_steps += 1
        else:
            self.failed_steps += 1
            if step_metrics.error_type:
                self.errors_by_type[step_metrics.error_type] = \
                    self.errors_by_type.get(step_metrics.error_type, 0) + 1
        
        # Обновление времени
        self.total_execution_time_ms += step_metrics.execution_time_ms
        self.avg_step_time_ms = self.total_execution_time_ms / self.total_steps
        
        # Обновление статистики capability
        self.capabilities_used[step_metrics.capability] = \
            self.capabilities_used.get(step_metrics.capability, 0) + 1
    
    def add_pattern_switch(self):
        """Записать переключение паттерна."""
        self.pattern_switches += 1
    
    def finalize(self):
        """Завершить сессию."""
        self.end_time = datetime.now()
    
    def get_success_rate(self) -> float:
        """Получить процент успешных шагов."""
        if self.total_steps == 0:
            return 0.0
        return self.successful_steps / self.total_steps
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": (self.end_time - self.start_time).total_seconds() * 1000 if self.end_time else 0,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "success_rate": self.get_success_rate(),
            "total_execution_time_ms": self.total_execution_time_ms,
            "avg_step_time_ms": self.avg_step_time_ms,
            "errors_by_type": self.errors_by_type,
            "capabilities_used": self.capabilities_used,
            "pattern_switches": self.pattern_switches
        }


class MetricsCollector:
    """
    Сборщик метрик выполнения агента.
    
    ПРИНЦИПЫ:
    - Минимальные накладные расходы
    - Публикация метрик через EventBus
    - Агрегация статистики по сессии
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    collector = MetricsCollector(session_id="123", event_bus=event_bus)
    collector.start_session(goal="Найти книги Пушкина")
    
    collector.record_step(
        step_number=1,
        capability="book_library.execute_script",
        status="completed",
        execution_time_ms=150.5
    )
    
    collector.end_session()
    metrics = collector.get_session_metrics()
    """
    
    def __init__(self, session_id: str, event_bus=None):
        """
        Инициализация сборщика метрик.
        
        ПАРАМЕТРЫ:
        - session_id: ID сессии
        - event_bus: EventBus для публикации метрик (опционально)
        """
        self.session_id = session_id
        self.event_bus = event_bus
        self.session_metrics: Optional[SessionMetrics] = None
        self.step_history: List[StepMetrics] = []
    
    def start_session(self, goal: str):
        """
        Начать новую сессию.
        
        ПАРАМЕТРЫ:
        - goal: цель сессии
        """
        self.session_metrics = SessionMetrics(
            session_id=self.session_id,
            goal=goal
        )
        self.step_history = []
        
        # Публикация события начала сессии
        if self.event_bus:
            self._publish_event("session_started", {
                "session_id": self.session_id,
                "goal": goal
            })
    
    def record_step(
        self,
        step_number: int,
        capability: str,
        status: str,
        execution_time_ms: float,
        error_type: Optional[str] = None,
        retry_count: int = 0
    ):
        """
        Записать метрики шага.
        
        ПАРАМЕТРЫ:
        - step_number: номер шага
        - capability: имя выполненной capability
        - status: статус выполнения (completed/failed/aborted)
        - execution_time_ms: время выполнения в мс
        - error_type: тип ошибки (если была)
        - retry_count: количество попыток
        """
        step_metrics = StepMetrics(
            step_number=step_number,
            capability=capability,
            status=status,
            execution_time_ms=execution_time_ms,
            error_type=error_type,
            retry_count=retry_count
        )
        
        self.step_history.append(step_metrics)
        
        if self.session_metrics:
            self.session_metrics.add_step(step_metrics)
        
        # Публикация события шага
        if self.event_bus:
            self._publish_event("step_completed", {
                "session_id": self.session_id,
                "step_number": step_number,
                "capability": capability,
                "status": status,
                "execution_time_ms": execution_time_ms
            })
    
    def record_pattern_switch(self, from_pattern: str, to_pattern: str, reason: str):
        """
        Записать переключение паттерна.
        
        ПАРАМЕТРЫ:
        - from_pattern: предыдущий паттерн
        - to_pattern: новый паттерн
        - reason: причина переключения
        """
        if self.session_metrics:
            self.session_metrics.add_pattern_switch()
        
        # Публикация события переключения
        if self.event_bus:
            self._publish_event("pattern_switched", {
                "session_id": self.session_id,
                "from_pattern": from_pattern,
                "to_pattern": to_pattern,
                "reason": reason
            })
    
    def end_session(self, final_status: str = "completed"):
        """
        Завершить сессию.
        
        ПАРАМЕТРЫ:
        - final_status: финальный статус сессии
        """
        if self.session_metrics:
            self.session_metrics.finalize()
        
        # Публикация события завершения сессии
        if self.event_bus:
            event_data = {
                "session_id": self.session_id,
                "final_status": final_status
            }
            if self.session_metrics:
                event_data.update(self.session_metrics.to_dict())
            self._publish_event("session_completed", event_data)
    
    def get_session_metrics(self) -> Optional[SessionMetrics]:
        """
        Получить метрики сессии.
        
        ВОЗВРАЩАЕТ:
        - SessionMetrics или None если сессия не начата
        """
        return self.session_metrics
    
    def get_step_history(self) -> List[StepMetrics]:
        """
        Получить историю шагов.
        
        ВОЗВРАЩАЕТ:
        - List[StepMetrics]: история всех шагов
        """
        return self.step_history.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Получить краткую сводку метрик.
        
        ВОЗВРАЩАЕТ:
        - Dict: сводка метрик
        """
        if not self.session_metrics:
            return {}
        
        return {
            "session_id": self.session_id,
            "total_steps": self.session_metrics.total_steps,
            "success_rate": self.session_metrics.get_success_rate(),
            "avg_step_time_ms": self.session_metrics.avg_step_time_ms,
            "pattern_switches": self.session_metrics.pattern_switches
        }
    
    def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """
        Опубликовать событие через EventBus.
        
        ПАРАМЕТРЫ:
        - event_type: тип события
        - data: данные события
        """
        if not self.event_bus:
            return
        
        try:
            self.event_bus.publish(
                event_type=f"metrics.{event_type}",
                data=data,
                source="MetricsCollector"
            )
        except Exception:
            # Игнорируем ошибки публикации метрик
            pass

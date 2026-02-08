from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4


class ComposablePatternStatus(str, Enum):
    """
    Статусы выполнения композиционного паттерна
    """
    INITIALIZING = "initializing"      # Инициализация
    ACTIVE = "active"                  # Активен, выполняет действия
    WAITING_FOR_INPUT = "waiting_for_input"  # Ожидает ввода от пользователя
    PAUSED = "paused"                  # Приостановлен
    COMPLETED = "completed"            # Завершен успешно
    FAILED = "failed"                  # Завершен с ошибкой
    STOPPED = "stopped"                # Остановлен пользователем
    TERMINATED = "terminated"          # Принудительно завершен


class ComposablePatternState(BaseModel):
    """
    Состояние композиционного паттерна для ReAct (Reasoning and Acting)
    
    Служит для отслеживания прогресса выполнения паттерна, включая:
    - текущее состояние выполнения
    - историю действий
    - метрики прогресса
    - информацию о текущем цикле ReAct
    """
    
    # Идентификация
    id: str = Field(default_factory=lambda: f"pattern_state_{uuid4().hex[:12]}")
    pattern_name: str = ""  # Название паттерна (например, "ReAct")
    session_id: str = ""    # ID сессии, к которой относится состояние
    
    # Статус и жизненный цикл
    status: ComposablePatternStatus = ComposablePatternStatus.INITIALIZING
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    
    # Счетчики и прогресс
    step_count: int = 0                    # Общее количество шагов
    iteration_count: int = 0               # Количество итераций ReAct
    error_count: int = 0                   # Количество ошибок
    no_progress_iterations: int = 0        # Количество итераций без прогресса
    
    # Информация о текущем состоянии ReAct
    current_thought: Optional[str] = None  # Текущее мышление
    current_action: Optional[Dict[str, Any]] = None  # Текущее действие
    current_observation: Optional[str] = None        # Текущее наблюдение
    
    # История выполнения
    action_history: List[Dict[str, Any]] = Field(default_factory=list)  # История действий
    thought_history: List[str] = Field(default_factory=list)           # История мышления
    observation_history: List[str] = Field(default_factory=list)       # История наблюдений
    
    # Метрики и прогресс
    progress_percentage: float = 0.0       # Процент выполнения задачи
    last_progress_update: Optional[datetime] = None  # Время последнего прогресса
    
    # Дополнительные данные
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Дополнительные метаданные
    error_details: Optional[Dict[str, Any]] = None         # Детали последней ошибки
    
    # Управление выполнением
    max_iterations: int = 50              # Максимальное количество итераций
    max_no_progress_iterations: int = 3   # Максимум итераций без прогресса
    finished: bool = False                # Флаг завершения выполнения
    
    # Стек отмены (для поддержки undo операций)
    undo_stack: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
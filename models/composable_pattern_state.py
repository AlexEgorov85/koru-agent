from enum import Enum
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime


class ComposablePatternStatus(str, Enum):
    """Статус выполнения композиционного паттерна."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    ACTIVE = "active"
    EXECUTING_ACTION = "executing_action"
    WAITING_FOR_INPUT = "waiting_for_input"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class ComposablePatternState(BaseModel):
    """
    Явное состояние композиционного паттерна.
    Не содержит логики — только данные.
    """

    # Основные параметры состояния
    step: int = 0
    action_index: int = 0  # Индекс текущего выполняемого действия в паттерне
    error_count: int = 0
    no_progress_steps: int = 0
    finished: bool = False
    
    # Информация о паттерне
    pattern_name: str = ""
    pattern_description: str = ""
    
    # Статус выполнения
    status: ComposablePatternStatus = ComposablePatternStatus.INITIALIZING
    
    # Метрики выполнения
    metrics: Dict[str, Any] = {}
    action_history: List[Dict[str, Any]] = []  # История выполненных действий
    history: List[str] = []
    
    # Текущий план и шаги
    current_plan_step: Optional[str] = None
    current_action_name: Optional[str] = None  # Имя текущего выполняемого действия
    
    # Временные метки
    started_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None

    def register_error(self):
        """Регистрирует ошибку выполнении."""
        self.error_count += 1
        self.status = ComposablePatternStatus.ERROR

    def register_progress(self, progressed: bool):
        """Регистрирует прогресс выполнения."""
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1

    def complete(self):
        """Отмечает паттерн как завершивший выполнение."""
        self.finished = True
        self.status = ComposablePatternStatus.COMPLETED

    def pause(self):
        """Приостанавливает выполнение паттерна."""
        self.status = ComposablePatternStatus.PAUSED

    def resume(self):
        """Возобновляет выполнение паттерна."""
        self.status = ComposablePatternStatus.ACTIVE

    def start_execution(self, pattern_name: str, pattern_description: str = ""):
        """Инициализирует выполнение паттерна."""
        self.pattern_name = pattern_name
        self.pattern_description = pattern_description
        self.status = ComposablePatternStatus.ACTIVE
        self.started_at = datetime.now()

    def start_action_execution(self, action_name: str):
        """Инициализирует выполнение действия внутри паттерна."""
        self.current_action_name = action_name
        self.status = ComposablePatternStatus.EXECUTING_ACTION
        self.last_action_at = datetime.now()

    def finish_action_execution(self, action_result: Dict[str, Any]):
        """Завершает выполнение действия внутри паттерна."""
        self.action_index += 1
        self.status = ComposablePatternStatus.ACTIVE
        
        # Сохраняем информацию о выполненном действии
        action_record = {
            "action_name": self.current_action_name,
            "result": action_result,
            "completed_at": datetime.now(),
            "step_number": self.step
        }
        self.action_history.append(action_record)
        self.current_action_name = None

    def waiting_for_input(self):
        """Отмечает, что паттерн ожидает ввода."""
        self.status = ComposablePatternStatus.WAITING_FOR_INPUT
from enum import Enum
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional


class ExecutionStatus(str, Enum):
    """Статус выполнения."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class ExecutionState(BaseModel):
    """
    Явное состояние выполнения.
    Не содержит логики — только данные.
    """

    step: int = 0
    error_count: int = 0
    no_progress_steps: int = 0
    finished: bool = False
    metrics: Dict[str, Any] = {}
    history: List[str] = []
    current_plan_step: Optional[str] = None

    def register_error(self):
        self.error_count += 1

    def register_progress(self, progressed: bool):
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1

    def complete(self):
        """Отмечает выполнение как завершившееся."""
        self.finished = True
"""
Состояние агента для новой архитектуры
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class AgentState:
    """
    Явное состояние агента.
    Не содержит логики — только данные.
    """

    step: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    no_progress_steps: int = 0
    finished: bool = False

    history: List[str] = field(default_factory=list)

    def register_error(self):
        self.error_count += 1
        self.consecutive_errors += 1

    def reset_consecutive_errors(self):
        """Сброс счетчика последовательных ошибок"""
        self.consecutive_errors = 0

    def register_progress(self, progressed: bool):
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1
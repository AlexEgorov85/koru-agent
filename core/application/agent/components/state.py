"""
Состояние агента для новой архитектуры
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


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

    def snapshot(self) -> Dict[str, Any]:
        """
        Возвращает снимок состояния для сравнения.
        
        Используется для детекции зацикливания и отсутствия прогресса.
        """
        return {
            'step': self.step,
            'error_count': self.error_count,
            'consecutive_errors': self.consecutive_errors,
            'no_progress_steps': self.no_progress_steps,
            'finished': self.finished,
            'history_length': len(self.history),
            'last_history_item': self.history[-1] if self.history else None
        }

    def __eq__(self, other):
        """Сравнение состояний по snapshot."""
        if not isinstance(other, AgentState):
            return False
        return self.snapshot() == other.snapshot()
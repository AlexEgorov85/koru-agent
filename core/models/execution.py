"""
Модели для выполнения задач.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional


class ExecutionStatus(Enum):
    """
    Статусы выполнения задачи.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """
    Результат выполнения задачи.

    ATTRIBUTES:
    - status: статус выполнения
    - result: результат выполнения
    - error: ошибка (если была)
    - metadata: дополнительные метаданные
    """
    status: ExecutionStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
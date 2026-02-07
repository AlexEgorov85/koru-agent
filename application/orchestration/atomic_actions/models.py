"""
Модели результатов для атомарных действий.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AtomicActionResult:
    """
    Базовый класс результата атомарного действия
    """
    success: bool
    action_type: str
    error_message: Optional[str] = None
    context_update: Optional[Dict[str, Any]] = None
    result_data: Optional[Dict[str, Any]] = None


@dataclass
class ThinkActionResult(AtomicActionResult):
    """
    Результат действия мышления
    """
    thought: str = ""
    next_action_type: str = "THINK"


@dataclass
class ActActionResult(AtomicActionResult):
    """
    Результат действия выполнения
    """
    executed_action: str = ""
    action_result: str = ""
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class ObserveActionResult(AtomicActionResult):
    """
    Результат действия наблюдения
    """
    observation: str = ""
    processed_result: str = ""


@dataclass
class FileOperationActionResult(AtomicActionResult):
    """
    Результат действия файловой операции
    """
    operation_type: str = ""
    file_path: str = ""
    result: str = ""
    error_message: str = ""
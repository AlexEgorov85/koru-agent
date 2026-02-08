"""
Модель состояния для ReAct цикла.
Содержит информацию о текущем состоянии выполнения ReAct паттерна:
- история рассуждений
- история действий
- история наблюдений
- прогресс выполнения задачи
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ActionType(Enum):
    """Типы действий в ReAct цикле"""
    THOUGHT = "THOUGHT"
    ACTION = "ACTION"
    OBSERVATION = "OBSERVATION"
    REASONING = "REASONING"


@dataclass
class ReActStep:
    """Один шаг в ReAct цикле"""
    step_number: int
    action_type: ActionType
    content: str
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ReActState:
    """Состояние ReAct цикла"""
    # Основная цель задачи
    goal: str
    
    # История выполнения
    steps: List[ReActStep]
    
    # Текущий прогресс
    current_step: int = 0
    
    # Информация о завершении
    is_completed: bool = False
    completion_reason: Optional[str] = None
    
    # Дополнительные данные
    context: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    

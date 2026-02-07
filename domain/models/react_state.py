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
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
        if self.context is None:
            self.context = {}
        if self.metrics is None:
            self.metrics = {
                "total_steps": 0,
                "thought_count": 0,
                "action_count": 0,
                "observation_count": 0,
                "execution_time": 0.0
            }
    
    def add_step(self, action_type: ActionType, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Добавить шаг в историю"""
        step = ReActStep(
            step_number=len(self.steps),
            action_type=action_type,
            content=content,
            metadata=metadata
        )
        self.steps.append(step)
        
        # Обновить метрики
        self.metrics["total_steps"] += 1
        if action_type == ActionType.THOUGHT or action_type == ActionType.REASONING:
            self.metrics["thought_count"] += 1
        elif action_type == ActionType.ACTION:
            self.metrics["action_count"] += 1
        elif action_type == ActionType.OBSERVATION:
            self.metrics["observation_count"] += 1
            
        return step
    
    def get_recent_thoughts(self, count: int = 1) -> List[ReActStep]:
        """Получить последние рассуждения"""
        thoughts = [step for step in self.steps 
                   if step.action_type in [ActionType.THOUGHT, ActionType.REASONING]]
        return thoughts[-count:]
    
    def get_recent_actions(self, count: int = 1) -> List[ReActStep]:
        """Получить последние действия"""
        actions = [step for step in self.steps if step.action_type == ActionType.ACTION]
        return actions[-count:]
    
    def get_recent_observations(self, count: int = 1) -> List[ReActStep]:
        """Получить последние наблюдения"""
        observations = [step for step in self.steps if step.action_type == ActionType.OBSERVATION]
        return observations[-count:]
    
    def mark_completed(self, reason: str = "Цель достигнута"):
        """Отметить выполнение задачи как завершенное"""
        self.is_completed = True
        self.completion_reason = reason
        
    def get_context_summary(self) -> Dict[str, Any]:
        """Получить сводку по контексту выполнения"""
        return {
            "goal": self.goal,
            "current_step": self.current_step,
            "total_steps": len(self.steps),
            "is_completed": self.is_completed,
            "completion_reason": self.completion_reason,
            "metrics": self.metrics
        }
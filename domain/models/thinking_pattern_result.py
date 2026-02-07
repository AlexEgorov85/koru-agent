from dataclasses import dataclass
from typing import Any, Optional, Dict, List
from domain.models.execution.execution_status import ExecutionStatus
from datetime import datetime

@dataclass
class ThinkingPatternStep:
    """
    Один шаг выполнения паттерна мышления
    """
    # Общие поля для всех паттернов
    thought: str  # Что думал агент
    action: Optional[Dict[str, Any]] = None  # Совершенное действие
    action_input: Optional[Dict[str, Any]] = None  # Входные данные действия
    observation: Optional[str] = None  # Результат наблюдения
    success: bool = True  # Успешно ли выполнено
    timestamp: datetime = None  # Время выполнения шага
    metadata: Optional[Dict[str, Any]] = None  # Дополнительные метаданные

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ThinkingPatternResult:
    """
    Универсальный результат выполнения паттерна мышления
    Подходит для всех типов паттернов: ReAct, Planning, Analysis и т.д.
    """
    # Обязательные поля
    status: ExecutionStatus  # Статус выполнения (SUCCESS, FAILED, etc.)
    stop_reason: str  # Причина остановки (goal_reached, step_limit, etc.)
    confidence: float  # Уверенность в результате (0.0 - 1.0)
    
    # Опциональные поля
    output: Optional[Any] = None  # Основной результат выполнения
    error: Optional[str] = None  # Сообщение об ошибке (если была)
    
    # Метаданные
    meta: Optional[Dict[str, Any]] = None  # Дополнительные метаданные
    
    # Специфичные для трассировки поля
    trace: Optional[List[ThinkingPatternStep]] = None  # История шагов
    steps_taken: int = 0  # Количество выполненных шагов
    tool_errors: int = 0  # Количество ошибок инструментов
    total_execution_time: float = 0.0  # Общее время выполнения
    final_context: Optional[Dict[str, Any]] = None  # Финальное состояние контекста
    pattern_specific_data: Optional[Dict[str, Any]] = None  # Данные, специфичные для паттерна
    
    def __post_init__(self):
        if self.meta is None:
            self.meta = {}
        if self.trace is None:
            self.trace = []
        if self.final_context is None:
            self.final_context = {}
        if self.pattern_specific_data is None:
            self.pattern_specific_data = {}

    @classmethod
    def success(
        cls, 
        output: Any = None, 
        stop_reason: str = "goal_reached", 
        confidence: float = 1.0,
        **kwargs
    ) -> 'ThinkingPatternResult':
        """Создать успешный результат"""
        return cls(
            status=ExecutionStatus.SUCCESS,
            output=output,
            stop_reason=stop_reason,
            confidence=confidence,
            **kwargs
        )

    @classmethod
    def failed(
        cls, 
        error: str, 
        stop_reason: str = "execution_failed", 
        confidence: float = 0.0,
        **kwargs
    ) -> 'ThinkingPatternResult':
        """Создать результат с ошибкой"""
        return cls(
            status=ExecutionStatus.FAILED,
            error=error,
            stop_reason=stop_reason,
            confidence=confidence,
            **kwargs
        )

    @classmethod
    def interrupted(
        cls, 
        stop_reason: str, 
        confidence: float = 0.5,
        **kwargs
    ) -> 'ThinkingPatternResult':
        """Создать результат с прерыванием"""
        return cls(
            status=ExecutionStatus.STOPPED,
            stop_reason=stop_reason,
            confidence=confidence,
            **kwargs
        )
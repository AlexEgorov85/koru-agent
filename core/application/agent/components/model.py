"""
Модели решений агента для новой архитектуры
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type


class StrategyDecisionType(Enum):
    """
    Типы решений, которые может вернуть паттерн поведения.
    """
    ACT = "act"          # Выполнить действие
    STOP = "stop"        # Завершить выполнение агента
    SWITCH = "switch"    # Переключить паттерн
    RETRY = "retry"      # Повторить предыдущий шаг


@dataclass
class StrategyDecision:
    """
    Формализованное решение паттерна поведения.
    ОБНОВЛЕНО:
    - Добавлено поле parameters_class для класса Pydantic-модели параметров
    - Это позволяет валидировать параметры до выполнения capability
    """
    action: StrategyDecisionType
    capability: Optional[Any] = None
    parameters_class: Optional[Type] = None  # Класс Pydantic-модели для валидации
    payload: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    next_strategy: Optional[str] = None  # Устаревшее поле, будет удалено

    def __post_init__(self):
        """Валидация после инициализации."""
        if self.action == StrategyDecisionType.ACT and not self.capability:
            raise ValueError("Для действия ACT необходимо указать capability")
        if self.action == StrategyDecisionType.SWITCH and not self.next_strategy:
            raise ValueError("Для действия SWITCH необходимо указать next_strategy")
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type


class StrategyDecisionType(Enum):
    """
    Типы решений, которые может вернуть стратегия.
    """
    ACT = "act"          # Выполнить действие
    STOP = "stop"        # Завершить выполнение агента
    SWITCH = "switch"    # Переключить стратегию
    RETRY = "retry"      # Повторить предыдущий шаг
    
    def is_terminal(self) -> bool:
        """Проверяет, является ли действие терминальным."""
        return self in [StrategyDecisionType.STOP, StrategyDecisionType.SWITCH]


@dataclass
class StrategyDecision:
    """
    Формализованное решение стратегии.
    ОБНОВЛЕНО:
    - Добавлено поле parameters_class для класса Pydantic-модели параметров
    - Это позволяет валидировать параметры до выполнения capability
    """
    action: StrategyDecisionType
    capability: Optional[Any] = None
    parameters_class: Optional[Type] = None  # Класс Pydantic-модели для валидации
    payload: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    next_strategy: Optional[str] = None
    
    def __post_init__(self):
        """Валидация после инициализации."""
        if self.action == StrategyDecisionType.ACT and not self.capability:
            raise ValueError("Для действия ACT необходимо указать capability")
        if self.action == StrategyDecisionType.SWITCH and not self.next_strategy:
            raise ValueError("Для действия SWITCH необходимо указать next_strategy")

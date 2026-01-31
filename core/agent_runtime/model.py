from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

# Используем TYPE_CHECKING для предотвращения циклических импортов
if TYPE_CHECKING:
    from core.atomic_actions.base import AtomicActionType
    from core.composable_patterns.base import ComposablePattern
    from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface

from models.capability import Capability


class StrategyDecisionType(Enum):
    """
    Типы решений, которые может вернуть стратегия в новой архитектуре.
    """
    ACT = "act"              # Выполнить действие
    STOP = "stop"            # Завершить выполнение агента
    SWITCH = "switch"        # Переключить стратегию
    RETRY = "retry"          # Повторить предыдущий шаг
    CONTINUE = "continue"    # Продолжить выполнение текущей стратегии
    EVALUATE = "evaluate"    # Оценить прогресс и принять решение
    
    def is_terminal(self) -> bool:
        """Проверяет, является ли действие терминальным."""
        return self in [StrategyDecisionType.STOP]


@dataclass
class StrategyDecision:
    """
    Формализованное решение стратегии в новой архитектуре.
    ОБНОВЛЕНО:
    - Поддержка компонуемых паттернов
    - Поддержка атомарных действий
    - Расширенная информация о принятом решении
    """
    action: StrategyDecisionType
    capability: Optional[Capability] = None
    parameters_class: Optional[Type] = None  # Класс Pydantic-модели для валидации
    payload: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    next_strategy: Optional[str] = None
    atomic_action: Optional[str] = None      # Тип атомарного действия (например, "THINK", "ACT", "OBSERVE")
    composable_pattern: Optional['ComposablePattern'] = None  # Компонуемый паттерн, если используется (используем строковую аннотацию для предотвращения циклического импорта)
    domain_context: Optional[Dict[str, Any]] = None  # Контекст домена задачи
    
    def __post_init__(self):
        """Валидация после инициализации."""
        if self.action == StrategyDecisionType.ACT and not self.capability:
            raise ValueError("Для действия ACT необходимо указать capability")
        if self.action == StrategyDecisionType.SWITCH and not self.next_strategy:
            raise ValueError("Для действия SWITCH необходимо указать next_strategy")
        if self.action == StrategyDecisionType.EVALUATE and not self.payload:
            # Для EVALUATE может быть полезно иметь payload с информацией для оценки
            self.payload = {} if self.payload is None else self.payload

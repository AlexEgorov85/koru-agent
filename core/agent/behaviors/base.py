from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class DecisionType(Enum):
    """Типы решений Pattern."""
    ACT = "act"                    # Выполнить действие
    FINISH = "finish"              # Завершить успешно
    FAIL = "fail"                  # Завершить с ошибкой
    SWITCH_STRATEGY = "switch"     # Переключить стратегию
    # RETRY удалён — это ACT с тем же действием


@dataclass
class Decision:
    """
    Решение Pattern.
    
    ЕДИНСТВЕННЫЙ способ принятия решений в системе.
    """
    type: DecisionType
    
    # Для ACT
    action: Optional[str] = None           # capability_name
    parameters: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    
    # Для FINISH
    result: Optional[Any] = None
    
    # Для SWITCH_STRATEGY
    next_pattern: Optional[str] = None
    
    # Для FAIL
    error: Optional[str] = None
    
    # Мета
    confidence: float = 1.0
    is_final: bool = False  # ← Помечает финальный шаг
    
    # ← НОВОЕ: capability_name как алиас на action (для обратной совместимости)
    @property
    def capability_name(self) -> Optional[str]:
        return self.action
    
    @capability_name.setter
    def capability_name(self, value: Optional[str]):
        self.action = value


class BehaviorPatternInterface(ABC):
    """
    Интерфейс Pattern — ЕДИНСТВЕННОЕ место принятия решений.
    
    Pattern отвечает за:
    - анализ контекста
    - принятие решений (ACT/FINISH/FAIL/SWITCH_STRATEGY)
    - выбор стратегии
    """
    pattern_id: str  # e.g., "react_pattern"
    
    @abstractmethod
    async def decide(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability']
    ) -> Decision:
        """
        ЕДИНСТВЕННОЕ место принятия решений.
        
        ПАРАМЕТРЫ:
        - session_context: контекст сессии
        - available_capabilities: доступные capability
        
        ВОЗВРАЩАЕТ:
        - Decision с типом и параметрами
        
        ОТВЕЧАЕТ ЗА:
        - что делать (ACT)
        - завершить успешно (FINISH)
        - завершить с ошибкой (FAIL)
        - сменить стратегию (SWITCH_STRATEGY)
        """
        pass
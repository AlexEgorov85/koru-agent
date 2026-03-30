from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
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


# ============================================================================
# DEPRECATED: старые имена для обратной совместимости (удалить в Этапе 8)
# ============================================================================

BehaviorDecisionType = DecisionType  # TODO: удалить после миграции
BehaviorDecision = Decision  # TODO: удалить после миграции


# ============================================================================
# КЛАССЫ ВХОДА/ВЫХОДА ДЛЯ ПАТТЕРНОВ (для совместимости с тестами)
# ============================================================================

class BehaviorInput:
    """Базовый класс для входных данных поведенческого паттерна."""
    pass


class BehaviorOutput:
    """Базовый класс для выходных данных поведенческого паттерна."""
    pass


class ReActInput(BehaviorInput):
    """Входные данные для ReAct паттерна."""
    def __init__(self, goal: str, context: Dict[str, Any] = None, history: list = None, available_tools: list = None):
        self.goal = goal
        self.context = context or {}
        self.history = history or []
        self.available_tools = available_tools or []


class ReActOutput(BehaviorOutput):
    """Выходные данные для ReAct паттерна."""
    def __init__(self, thought: str = None, action: Dict[str, Any] = None, observation: str = None, is_final: bool = False, updated_context: Dict[str, Any] = None):
        self.thought = thought
        self.action = action
        self.observation = observation
        self.is_final = is_final
        self.updated_context = updated_context or {}


class PlanningInput(BehaviorInput):
    """Входные данные для Planning паттерна."""
    def __init__(self, goal: str, context: Dict[str, Any] = None, available_tools: list = None, constraints: list = None):
        self.goal = goal
        self.context = context or {}
        self.available_tools = available_tools or []
        self.constraints = constraints or []


class PlanningOutput(BehaviorOutput):
    """Выходные данные для Planning паттерна."""
    def __init__(self, plan: list = None, decomposition_reasoning: str = None, sequence_reasoning: str = None, is_complete: bool = False):
        self.plan = plan or []
        self.decomposition_reasoning = decomposition_reasoning
        self.sequence_reasoning = sequence_reasoning
        self.is_complete = is_complete


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
    
    # ========================================================================
    # DEPRECATED: старые методы (удалить после миграции)
    # ========================================================================
    
    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability'],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """⚠️ DEPRECATED: использовать напрямую decide()."""
        # Для обратной совместимости
        return context_analysis or {}
    
    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability'],
        context_analysis: Dict[str, Any]
    ) -> Decision:
        """⚠️ DEPRECATED: использовать напрямую decide()."""
        # Для обратной совместимости — делегирование decide()
        return await self.decide(session_context, available_capabilities)
    
    def _filter_capabilities(
        self,
        capabilities: List['Capability']
    ) -> List['Capability']:
        """
        Фильтрация capability по supported_strategies.

        Разрешает capability, если:
        1. Pattern (react/planning/etc) указан в supported_strategies capability
        2. ИЛИ это инструмент (tool)
        """
        # pattern_id может быть "react_pattern" или "react.v1.0.0"
        # Нам нужно извлечь "react" для сравнения со supported_strategies
        pattern_prefix = self.pattern_id.split('.')[0]  # "react_pattern" или "react"
        # Если pattern_prefix содержит "_pattern", извлекаем часть до "_"
        if "_pattern" in pattern_prefix:
            pattern_prefix = pattern_prefix.replace("_pattern", "")  # "react"

        filtered = [
            cap for cap in capabilities
            if (
                # Pattern должен быть в supported_strategies
                pattern_prefix.lower() in [s.lower() for s in (cap.supported_strategies or [])]
            )
        ]

        return filtered
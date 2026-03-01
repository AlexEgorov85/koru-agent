from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class BehaviorDecisionType(Enum):
    ACT = "act"      # Выполнить действие
    STOP = "stop"    # Завершить выполнение
    SWITCH = "switch"  # Переключить паттерн
    RETRY = "retry"  # Повторить шаг


@dataclass
class BehaviorDecision:
    action: BehaviorDecisionType
    capability_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    next_pattern: Optional[str] = None  # Для SWITCH
    reason: str = ""
    confidence: float = 1.0


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
    pattern_id: str  # e.g., "react.v1.0.0"
    
    @abstractmethod
    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability'],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        pass
    
    @abstractmethod
    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability'],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """Генерация решения на основе анализа"""
        pass
    
    def _filter_capabilities(
        self,
        capabilities: List['Capability'],
        required_skills: List[str]
    ) -> List['Capability']:
        """Единая точка фильтрации (устраняет дублирование)"""
        import logging
        logger = logging.getLogger(__name__)
        
        # pattern_id может быть "react_pattern" или "react.v1.0.0"
        # Нам нужно извлечь "react" для сравнения со supported_strategies
        pattern_prefix = self.pattern_id.split('.')[0]  # "react_pattern" или "react"
        # Если pattern_prefix содержит "_pattern", извлекаем часть до "_"
        if "_pattern" in pattern_prefix:
            pattern_prefix = pattern_prefix.replace("_pattern", "")  # "react"
        
        filtered = [
            cap for cap in capabilities
            if (
                # Разрешаем capability от указанных навыков ИЛИ от инструментов (у них skill_name содержит "tool")
                cap.skill_name in required_skills 
                or "tool" in cap.skill_name.lower()
                or any(s.lower() == "tool" for s in cap.supported_strategies or [])
            )
            and (
                # Pattern должен быть в supported_strategies
                pattern_prefix.lower() in [s.lower() for s in (cap.supported_strategies or [])]
            )
        ]
        
        self.event_bus_logger.info(f"_filter_capabilities: pattern_id={self.pattern_id}, pattern_prefix={pattern_prefix}, required_skills={required_skills}")
        self.event_bus_logger.info(f"_filter_capabilities: входные capability={[c.name for c in capabilities]}")
        self.event_bus_logger.info(f"_filter_capabilities: отфильтрованные capability={[c.name for c in filtered]}")
        
        return filtered
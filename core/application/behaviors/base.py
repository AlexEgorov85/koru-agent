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
        return [
            cap for cap in capabilities
            if cap.skill_name in required_skills
            and self.pattern_id.split('.')[0] in (cap.supported_strategies or [])
        ]
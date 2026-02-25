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
        
        logger.info(f"_filter_capabilities: pattern_id={self.pattern_id}, pattern_prefix={pattern_prefix}, required_skills={required_skills}")
        logger.info(f"_filter_capabilities: входные capability={[c.name for c in capabilities]}")
        logger.info(f"_filter_capabilities: отфильтрованные capability={[c.name for c in filtered]}")
        
        return filtered
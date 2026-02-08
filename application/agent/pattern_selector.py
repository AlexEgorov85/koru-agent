# application/agent/pattern_selector.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.domain_type import DomainType

class IPatternSelector(ABC):
    """Порт для выбора паттерна мышления на основе задачи и домена"""
    
    @abstractmethod
    async def select_pattern(
        self,
        task_description: str,
        domain: DomainType,
        available_patterns: List[IThinkingPattern]
    ) -> IThinkingPattern:
        """Выбрать наиболее подходящий паттерн для задачи"""
        pass
    
    @abstractmethod
    def get_available_patterns(self) -> List[IThinkingPattern]:
        """Получить список доступных паттернов"""
        pass


class SimplePatternSelector(IPatternSelector):
    """
    Простой селектор паттернов на основе правил.
    Для продакшена заменить на мета-когнитивную модель через LLM.
    """
    
    def __init__(self, patterns: Dict[str, IThinkingPattern]):
        self.patterns = patterns
    
    async def select_pattern(
        self,
        task_description: str,
        domain: DomainType,
        available_patterns: List[IThinkingPattern]
    ) -> IThinkingPattern:
        task_lower = task_description.lower()
        
        # Правила выбора паттерна
        if domain == DomainType.CODE_ANALYSIS:
            if any(kw in task_lower for kw in ["анализ", "анализировать", "проверить", "проверка"]):
                return self.patterns.get("react", available_patterns[0])
            elif any(kw in task_lower for kw in ["план", "планирование", "этап"]):
                return self.patterns.get("plan_and_execute", available_patterns[0])
        
        elif domain == DomainType.PLANNING:
            return self.patterns.get("plan_and_execute", available_patterns[0])
        
        # По умолчанию — ReAct
        return self.patterns.get("react", available_patterns[0])
    
    def get_available_patterns(self) -> List[IThinkingPattern]:
        return list(self.patterns.values())
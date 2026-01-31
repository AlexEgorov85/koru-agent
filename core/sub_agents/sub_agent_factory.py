"""
Фабрика для создания субагентов.
"""

import logging
from typing import Dict, Type, Any

from core.sub_agents.base_sub_agent import BaseSubAgent


logger = logging.getLogger(__name__)


class SubAgentFactory:
    """
    Фабрика для создания различных типов субагентов.
    
    ПРИНЦИПЫ:
    1. Централизованное создание субагентов
    2. Регистрация новых типов субагентов
    3. Стандартизированный процесс создания
    """
    
    def __init__(self):
        self._subagent_types: Dict[str, Type[BaseSubAgent]] = {}
        self._initialize_default_subagents()
    
    def _initialize_default_subagents(self):
        """
        Инициализация стандартных типов субагентов.
        """
        from .code_analysis_sub_agent import CodeAnalysisSubAgent
        from .research_sub_agent import ResearchSubAgent
        from .planning_sub_agent import PlanningSubAgent
        from .execution_sub_agent import ExecutionSubAgent
        
        # Регистрация стандартных типов субагентов
        self.register_subagent_type('code_analyzer', CodeAnalysisSubAgent)
        self.register_subagent_type('researcher', ResearchSubAgent)
        self.register_subagent_type('planner', PlanningSubAgent)
        self.register_subagent_type('executor', ExecutionSubAgent)
        
        logger.info("SubAgentFactory initialized with default types")
    
    def register_subagent_type(self, name: str, subagent_class: Type[BaseSubAgent]):
        """
        Регистрация нового типа субагента.
        
        ПАРАМЕТРЫ:
        - name: Название типа субагента
        - subagent_class: Класс субагента
        """
        if not issubclass(subagent_class, BaseSubAgent):
            raise TypeError(f"Class {subagent_class.__name__} must inherit from BaseSubAgent")
        
        self._subagent_types[name] = subagent_class
        logger.info(f"Registered subagent type: {name}")
    
    def create_subagent(self, subagent_type: str, name: str, description: str = "", **kwargs) -> BaseSubAgent:
        """
        Создание экземпляра субагента.
        
        ПАРАМЕТРЫ:
        - subagent_type: Тип субагента (например, 'code_analyzer', 'researcher')
        - name: Название экземпляра субагента
        - description: Описание субагента
        - **kwargs: Дополнительные параметры для инициализации
        
        ВОЗВРАЩАЕТ:
        - Экземпляр субагента
        """
        if subagent_type not in self._subagent_types:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
        
        subagent_class = self._subagent_types[subagent_type]
        subagent = subagent_class(name=name, description=description, **kwargs)
        
        logger.info(f"Created subagent of type {subagent_type}: {name}")
        return subagent
    
    def get_available_types(self) -> list:
        """
        Получение списка доступных типов субагентов.
        
        ВОЗВРАЩАЕТ:
        - Список названий доступных типов субагентов
        """
        return list(self._subagent_types.keys())
    
    def is_valid_type(self, subagent_type: str) -> bool:
        """
        Проверка, является ли тип субагента допустимым.
        
        ПАРАМЕТРЫ:
        - subagent_type: Тип субагента для проверки
        
        ВОЗВРАЩАЕТ:
        - True если тип допустим, иначе False
        """
        return subagent_type in self._subagent_types
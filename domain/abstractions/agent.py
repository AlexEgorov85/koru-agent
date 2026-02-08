from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from domain.models.agent.agent_state import AgentState

class IAgent(ABC):
    """ЕДИНСТВЕННЫЙ интерфейс агента системы"""
    
    @property
    @abstractmethod
    def state(self) -> AgentState:
        """Текущее состояние агента"""
        pass
    
    @abstractmethod
    async def execute_task(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ЕДИНСТВЕННАЯ точка входа для выполнения задачи.
        
        Агент сам:
        - Определяет домен задачи
        - Выбирает подходящий паттерн мышления
        - Адаптирует паттерн к домену (загружает промты)
        - Выполняет задачу через паттерн
        - Возвращает результат
        
        Пользователю не нужно знать о внутренней архитектуре.
        """
        pass
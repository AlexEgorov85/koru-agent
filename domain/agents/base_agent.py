from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from domain.models.agent_state import AgentState


class BaseAgent(ABC):
    """
    Базовый абстрактный класс для всех агентов в системе.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для всех агентов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class ComposableAgent(BaseAgent):
        async def execute(self, task: str, context: Dict[str, Any]) -> AgentState:
            # Реализация агента
            pass
    ```
    """
    
    @abstractmethod
    async def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentState:
        """
        Асинхронное выполнение задачи агентом с заданным контекстом.
        
        Args:
            task: Задача для выполнения
            context: Необязательный контекст выполнения
        
        Returns:
            AgentState: Состояние агента после выполнения задачи
        """
        pass
    
    @abstractmethod
    def get_state(self) -> AgentState:
        """
        Получение текущего состояния агента.
        
        Returns:
            AgentState: Текущее состояние агента
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """
        Сброс состояния агента к начальному.
        """
        pass
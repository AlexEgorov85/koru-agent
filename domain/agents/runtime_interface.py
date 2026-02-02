from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from domain.models.agent_state import AgentState


class AgentRuntimeInterface(ABC):
    """
    Базовый абстрактный интерфейс для рантайма агентов.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для рантайма агентов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class RuntimeImplementation(AgentRuntimeInterface):
        async def execute_step(self, agent_id: str, step_data: Dict[str, Any]) -> AgentState:
            # Реализация выполнения шага
            pass
    ```
    """
    
    @abstractmethod
    async def execute_step(self, agent_id: str, step_data: Dict[str, Any]) -> AgentState:
        """
        Асинхронное выполнение одного шага агента.
        
        Args:
            agent_id: Идентификатор агента
            step_data: Данные шага для выполнения
            
        Returns:
            AgentState: Состояние агента после выполнения шага
        """
        pass
    
    @abstractmethod
    async def get_agent_state(self, agent_id: str) -> AgentState:
        """
        Получение текущего состояния агента.
        
        Args:
            agent_id: Идентификатор агента
            
        Returns:
            AgentState: Текущее состояние агента
        """
        pass
    
    @abstractmethod
    async def register_agent(self, agent_config: Dict[str, Any]) -> str:
        """
        Регистрация нового агента в рантайме.
        
        Args:
            agent_config: Конфигурация агента
            
        Returns:
            str: Идентификатор зарегистрированного агента
        """
        pass
    
    @abstractmethod
    async def update_agent_state(self, agent_id: str, state: AgentState) -> None:
        """
        Обновление состояния агента.
        
        Args:
            agent_id: Идентификатор агента
            state: Новое состояние агента
        """
        pass
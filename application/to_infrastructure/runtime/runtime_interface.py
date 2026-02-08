# Интерфейс взаимодействия рантайма агента
"""
AgentRuntimeInterface(ABC) — контракт рантайма
"""

from abc import ABC, abstractmethod


class AgentRuntimeInterface(ABC):
    """
    Абстрактный интерфейс для рантайма агента
    """
    
    @abstractmethod
    def start(self):
        """
        Запустить рантайм агента
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Остановить рантайм агента
        """
        pass
    
    @abstractmethod
    def execute_step(self, step_data):
        """
        Выполнить один шаг в рантайме
        
        Args:
            step_data: Данные для выполнения шага
            
        Returns:
            Результат выполнения шага
        """
        pass
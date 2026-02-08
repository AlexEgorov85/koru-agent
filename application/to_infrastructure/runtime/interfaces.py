# Интерфейс взаимодействия компонуемых агентов
"""
ComposableAgentInterface(ABC) — контракт агента
"""

from abc import ABC, abstractmethod


class ComposableAgentInterface(ABC):
    """
    Абстрактный интерфейс для компонуемых агентов
    """
    
    @abstractmethod
    def execute_task(self, task):
        """
        Выполнить задачу
        
        Args:
            task: Задача для выполнения
            
        Returns:
            Результат выполнения задачи
        """
        pass
    
    @abstractmethod
    def get_capabilities(self):
        """
        Получить возможности агента
        
        Returns:
            Список возможностей агента
        """
        pass
# Базовый класс для компонуемых паттернов
"""
ComposablePattern(ABC) — базовый контракт
"""

from abc import ABC, abstractmethod


class ComposablePattern(ABC):
    """
    Абстрактный базовый класс для компонуемых паттернов
    """
    
    @abstractmethod
    def execute(self, context):
        """
        Выполнить компонуемый паттерн
        
        Args:
            context: Контекст выполнения паттерна
            
        Returns:
            Результат выполнения паттерна
        """
        pass
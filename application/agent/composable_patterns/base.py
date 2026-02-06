"""
Базовый класс для компонуемых паттернов.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class ComposablePattern(ABC):
    """
    Абстрактный базовый класс для компонуемых паттернов
    """
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]):
        """
        Выполнить компонуемый паттерн
        
        Args:
            context: Контекст выполнения паттерна
            
        Returns:
            Результат выполнения паттерна
        """
        pass
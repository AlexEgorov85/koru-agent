# Базовый класс для атомарных действий
"""
AtomicAction(ABC) — базовый контракт
"""

from abc import ABC, abstractmethod


class AtomicAction(ABC):
    """
    Абстрактный базовый класс для атомарных действий
    """
    
    @abstractmethod
    def execute(self, context):
        """
        Выполнить атомарное действие
        
        Args:
            context: Контекст выполнения действия
            
        Returns:
            Результат выполнения действия
        """
        pass
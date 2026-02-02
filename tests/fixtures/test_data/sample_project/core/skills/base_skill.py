"""Пример базового навыка для тестов"""
from abc import ABC, abstractmethod


class BaseSkill(ABC):
    """Абстрактный базовый класс для навыков"""
    
    def __init__(self, name: str, description: str = ""):
        """
        Инициализирует навык
        
        Args:
            name: Название навыка
            description: Описание навыка
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Абстрактный метод выполнения навыка
        
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения навыка
        """
        pass
    
    def __str__(self):
        """Строковое представление навыка"""
        return f"BaseSkill({self.name})"
    
    def __repr__(self):
        """Подробное строковое представление навыка"""
        return f"BaseSkill(name={self.name}, description={self.description})"
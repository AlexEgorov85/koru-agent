"""
Базовый класс для DB провайдеров.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseDBProvider(ABC):
    """
    Абстрактный базовый класс для всех DB провайдеров.
    """
    
    @abstractmethod
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Выполнить SQL-запрос.
        
        Args:
            query: SQL-запрос
            params: Параметры запроса
            
        Returns:
            Результаты запроса в виде списка словарей
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить состояние провайдера.
        
        Returns:
            True если провайдер здоров
        """
        pass
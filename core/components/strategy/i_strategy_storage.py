"""
Интерфейс для хранилища стратегий.

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Единый контракт для всех реализаций хранилищ стратегий
- Поддержка CRUD операций для стратегий
- Типизированные методы для обеспечения безопасности типов
"""
from abc import ABC, abstractmethod
from typing import Protocol, Dict, Any, Optional, List
from models.capability import Capability


class IStrategyStorage(Protocol):
    """
    Интерфейс хранилища стратегий, определяющий контракт для работы с данными стратегий.
    
    Методы:
    - save_strategy: Сохранение стратегии
    - load_strategy: Загрузка стратегии по ID
    - delete_strategy: Удаление стратегии по ID
    - list_strategies: Получение списка всех стратегий
    - update_strategy: Обновление существующей стратегии
    """
    
    @abstractmethod
    async def save_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        Сохраняет стратегию в хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy_data: Данные стратегии в формате словаря
            
        Returns:
            bool: True если сохранение прошло успешно, иначе False
        """
        pass
    
    @abstractmethod
    async def load_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Загружает стратегию из хранилища по ID.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            
        Returns:
            Optional[Dict[str, Any]]: Данные стратегии или None если не найдена
        """
        pass
    
    @abstractmethod
    async def delete_strategy(self, strategy_id: str) -> bool:
        """
        Удаляет стратегию из хранилища по ID.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            
        Returns:
            bool: True если удаление прошло успешно, иначе False
        """
        pass
    
    @abstractmethod
    async def list_strategies(self) -> List[str]:
        """
        Возвращает список идентификаторов всех доступных стратегий.
        
        Returns:
            List[str]: Список ID стратегий
        """
        pass
    
    @abstractmethod
    async def update_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        Обновляет существующую стратегию в хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy_data: Новые данные стратегии
            
        Returns:
            bool: True если обновление прошло успешно, иначе False
        """
        pass
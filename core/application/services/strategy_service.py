"""
Сервис для работы со стратегиями.

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Интеграция с базовой системой компонентов
- Использование хранилища стратегий через интерфейс IStrategyStorage
- Поддержка асинхронных операций
- Централизованное управление стратегиями
"""
from typing import Dict, Any, Optional, List
import logging

from core.application.components.service import BaseService
from core.components.strategy.i_strategy_storage import IStrategyStorage
from core.components.strategy.strategy_storage import StrategyStorage
from core.config.component_config import ComponentConfig
from core.application.context.application_context import ApplicationContext
from models.capability import Capability


class StrategyService(BaseService):
    """
    Сервис для управления стратегиями.
    
    Этот сервис предоставляет централизованный доступ к операциям со стратегиями,
    используя хранилище стратегий для фактического хранения данных.
    
    Attributes:
        strategy_storage: Хранилище стратегий, реализующее IStrategyStorage
    """
    
    def __init__(
        self, 
        name: str, 
        application_context: ApplicationContext, 
        component_config: ComponentConfig,
        strategy_storage: Optional[IStrategyStorage] = None
    ):
        """
        Инициализирует сервис стратегий.
        
        Args:
            name: Имя сервиса
            application_context: Контекст приложения
            component_config: Конфигурация компонента
            strategy_storage: Опциональное хранилище стратегий (если не указано, будет создано по умолчанию)
        """
        super().__init__(name, application_context, component_config)
        
        # Инициализируем хранилище стратегий
        self.strategy_storage = strategy_storage or StrategyStorage()
        
        # Настройка логгера
        self.logger = logging.getLogger(__name__)
    
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any):
        """
        Выполняет операцию над стратегией в зависимости от capability.
        
        Args:
            capability: Операция, которую нужно выполнить
            parameters: Параметры операции
            context: Контекст выполнения
            
        Returns:
            Результат выполнения операции
        """
        self._ensure_initialized()
        
        operation = capability.name
        
        if operation == "save_strategy":
            strategy_id = parameters.get("strategy_id")
            strategy_data = parameters.get("strategy_data")
            return await self.save_strategy(strategy_id, strategy_data)
        
        elif operation == "load_strategy":
            strategy_id = parameters.get("strategy_id")
            return await self.load_strategy(strategy_id)
        
        elif operation == "delete_strategy":
            strategy_id = parameters.get("strategy_id")
            return await self.delete_strategy(strategy_id)
        
        elif operation == "list_strategies":
            return await self.list_strategies()
        
        elif operation == "update_strategy":
            strategy_id = parameters.get("strategy_id")
            strategy_data = parameters.get("strategy_data")
            return await self.update_strategy(strategy_id, strategy_data)
        
        else:
            raise ValueError(f"Неизвестная операция стратегии: {operation}")
    
    async def save_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        Сохраняет стратегию через хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy_data: Данные стратегии
            
        Returns:
            bool: True если сохранение прошло успешно, иначе False
        """
        self.logger.info(f"Сохранение стратегии '{strategy_id}' через StrategyService")
        return await self.strategy_storage.save_strategy(strategy_id, strategy_data)
    
    async def load_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Загружает стратегию через хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            
        Returns:
            Optional[Dict[str, Any]]: Данные стратегии или None если не найдена
        """
        self.logger.info(f"Загрузка стратегии '{strategy_id}' через StrategyService")
        return await self.strategy_storage.load_strategy(strategy_id)
    
    async def delete_strategy(self, strategy_id: str) -> bool:
        """
        Удаляет стратегию через хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            
        Returns:
            bool: True если удаление прошло успешно, иначе False
        """
        self.logger.info(f"Удаление стратегии '{strategy_id}' через StrategyService")
        return await self.strategy_storage.delete_strategy(strategy_id)
    
    async def list_strategies(self) -> List[str]:
        """
        Возвращает список всех стратегий.
        
        Returns:
            List[str]: Список ID стратегий
        """
        self.logger.info("Получение списка стратегий через StrategyService")
        return await self.strategy_storage.list_strategies()
    
    async def update_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        Обновляет стратегию через хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy_data: Новые данные стратегии
            
        Returns:
            bool: True если обновление прошло успешно, иначе False
        """
        self.logger.info(f"Обновление стратегии '{strategy_id}' через StrategyService")
        return await self.strategy_storage.update_strategy(strategy_id, strategy_data)
    
    async def get_strategy_by_capability(self, capability_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает стратегию по названию capability.
        
        Args:
            capability_name: Название capability для поиска стратегии
            
        Returns:
            Optional[Dict[str, Any]]: Данные стратегии или None если не найдена
        """
        # Ищем стратегию, соответствующую данному capability
        strategies = await self.list_strategies()
        
        for strategy_id in strategies:
            strategy_data = await self.load_strategy(strategy_id)
            if strategy_data and strategy_data.get('capability') == capability_name:
                return strategy_data
        
        self.logger.info(f"Стратегия для capability '{capability_name}' не найдена")
        return None
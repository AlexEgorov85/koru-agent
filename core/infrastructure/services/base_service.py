from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.system_context.base_system_contex import BaseSystemContext


class BaseService(ABC):
    """Базовый класс для всех сервисов системы.
    
    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    - Сервисы предоставляют определенную функциональность через методы
    - Сервисы могут иметь внутреннее состояние
    - Сервисы могут зависеть от других сервисов
    - Сервисы должны инициализироваться и корректно завершать работу
    - Сервисы регистрируются в SystemContext с типом ResourceType.SERVICE
    
    ОТЛИЧИЕ ОТ ИНСТРУМЕНТОВ:
    - Не обязательно имеет метод execute()
    - Может предоставлять несколько методов для использования
    - Может хранить состояние между вызовами
    - Предназначен для инфраструктурной функциональности
    """

    def __init__(self, name: str, system_context: Optional[BaseSystemContext] = None, **kwargs):
        """Инициализация сервиса.
        
        Args:
            name: Уникальное имя сервиса
            system_context: Системный контекст для доступа к другим ресурсам
            **kwargs: Дополнительные параметры конфигурации
        """
        self.name = name
        self.system_context = system_context
        self.config = kwargs
        self.is_initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Асинхронная инициализация сервиса.
        
        Должен выполнять:
        - Загрузку конфигурации
        - Установку соединений с внешними ресурсами
        - Проверку работоспособности
        - Подготовку внутренних структур данных
        
        Returns:
            bool: True при успешной инициализации, False при ошибке
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы сервиса.
        
        Должен выполнять:
        - Закрытие соединений
        - Очистку ресурсов
        - Сохранение состояния при необходимости
        """
        pass

    def get_config(self) -> Dict[str, Any]:
        """Получение конфигурации сервиса.
        
        Returns:
            Dict[str, Any]: Конфигурация сервиса
        """
        return self.config

    def set_config(self, config: Dict[str, Any]) -> None:
        """Установка конфигурации сервиса.
        
        Args:
            config: Новая конфигурация
        """
        self.config = config
        if hasattr(self, '_update_config'):
            self._update_config(config)

    def get_system_context(self) -> Optional[BaseSystemContext]:
        """Получение системного контекста.
        
        Returns:
            Optional[BaseSystemContext]: Системный контекст или None
        """
        return self.system_context

    def set_system_context(self, system_context: BaseSystemContext) -> None:
        """Установка системного контекста.
        
        Args:
            system_context: Новый системный контекст
        """
        self.system_context = system_context
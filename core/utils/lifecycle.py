"""
Утилиты для устранения дублирования кода.
"""
import logging
import asyncio
from typing import Any, Dict, List, Optional, TypeVar, Generic
from abc import ABC, abstractmethod
from core.infrastructure.logging.event_bus_log_handler import EventBusLogger


T = TypeVar('T')


class LifecycleManager:
    """
    Универсальный менеджер жизненного цикла для компонентов.

    Устраняет дублирование кода инициализации/завершения в:
    - BaseService
    - BaseSkill
    - BaseTool
    - Behavior patterns
    """

    def __init__(self, name: str, logger: Optional[logging.Logger] = None, event_bus=None):
        self.name = name
        self.logger = logger or logging.getLogger(name)
        self._initialized = False
        
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        if event_bus:
            self.event_bus_logger = EventBusLogger(event_bus, source=self.__class__.__name__)

    async def initialize(self, custom_init_func=None) -> bool:
        """
        Универсальный метод инициализации.

        ARGS:
        - custom_init_func: опциональная функция для кастомной инициализации

        RETURNS:
        - True если инициализация успешна
        """
        if self._initialized:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Компонент '{self.name}' уже инициализирован")
            else:
                self.logger.warning(f"Компонент '{self.name}' уже инициализирован")
            return True

        try:
            # Вызов кастомной инициализации если предоставлена
            if custom_init_func:
                result = await custom_init_func()
                if not result:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"Кастомная инициализация '{self.name}' не удалась")
                    else:
                        self.logger.error(f"Кастомная инициализация '{self.name}' не удалась")
                    return False

            self._initialized = True
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Компонент '{self.name}' инициализирован")
            else:
                self.logger.info(f"Компонент '{self.name}' инициализирован")
            return True

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка инициализации '{self.name}': {e}")
            else:
                self.logger.exception(f"Ошибка инициализации '{self.name}': {e}")
            return False

    async def shutdown(self, custom_shutdown_func=None) -> None:
        """
        Универсальный метод завершения.

        ARGS:
        - custom_shutdown_func: опциональная функция для кастомного завершения
        """
        if not self._initialized:
            return

        try:
            # Вызов кастомного завершения если предоставлено
            if custom_shutdown_func:
                await custom_shutdown_func()

            self._initialized = False
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Компонент '{self.name}' завершен")
            else:
                self.logger.info(f"Компонент '{self.name}' завершен")

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка завершения '{self.name}': {e}")
            else:
                self.logger.exception(f"Ошибка завершения '{self.name}': {e}")
    
    @property
    def is_initialized(self) -> bool:
        """Проверка состояния инициализации."""
        return self._initialized


class DependencyResolver:
    """
    Универсальный резолвер зависимостей для компонентов.

    Устраняет дублирование кода загрузки зависимостей в сервисах.
    """

    def __init__(self, component_name: str, get_dependency_func, logger: Optional[logging.Logger] = None, event_bus=None):
        self.component_name = component_name
        self._get_dependency = get_dependency_func
        self.logger = logger or logging.getLogger(f"{component_name}.deps")
        self._dependencies: Dict[str, Any] = {}
        
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        if event_bus:
            self.event_bus_logger = EventBusLogger(event_bus, source=self.__class__.__name__)

    async def resolve(self, dependency_names: List[str], required: bool = False) -> bool:
        """
        Разрешение списка зависимостей.

        ARGS:
        - dependency_names: список имен зависимостей
        - required: если True, все зависимости должны быть найдены

        RETURNS:
        - True если все зависимости разрешены (или не required)
        """
        if not dependency_names:
            return True

        missing = []

        for dep_name in dependency_names:
            dep = self._get_dependency(dep_name)

            if dep:
                self._dependencies[dep_name] = dep
                if self.event_bus_logger:
                    await self.event_bus_logger.debug(f"Зависимость '{dep_name}' найдена")
                else:
                    self.logger.debug(f"Зависимость '{dep_name}' найдена")
            else:
                missing.append(dep_name)
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(f"Зависимость '{dep_name}' не найдена")
                else:
                    self.logger.warning(f"Зависимость '{dep_name}' не найдена")

        if missing:
            if required:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Отсутствуют обязательные зависимости: {missing}")
                else:
                    self.logger.error(f"Отсутствуют обязательные зависимости: {missing}")
                return False
            else:
                if self.event_bus_logger:
                    await self.event_bus_logger.info(f"Некритичные зависимости отсутствуют: {missing}")
                else:
                    self.logger.info(f"Некритичные зависимости отсутствуют: {missing}")

        return True
    
    def get(self, name: str) -> Optional[Any]:
        """Получение зависимости по имени."""
        return self._dependencies.get(name)
    
    def clear(self) -> None:
        """Очистка кэша зависимостей."""
        self._dependencies.clear()


class InputValidator:
    """
    Универсальный валидатор входных данных.
    
    Устраняет дублирование кода валидации в сервисах и инструментах.
    """
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str], component_name: str) -> bool:
        """
        Проверка обязательных полей.
        
        ARGS:
        - data: входные данные
        - required_fields: список обязательных полей
        - component_name: имя компонента для логирования
        
        RETURNS:
        - True если все обязательные поля присутствуют
        """
        logger = logging.getLogger(f"{component_name}.validator")
        
        for field in required_fields:
            if field not in data or data[field] is None:
                logger.error(f"Отсутствует обязательное поле: {field}")
                return False
        
        return True
    
    @staticmethod
    def sanitize_string(data: str, dangerous_chars: Optional[List[str]] = None) -> str:
        """
        Санитизация строки от опасных символов.
        
        ARGS:
        - data: строка для санитизации
        - dangerous_chars: список опасных символов (по умолчанию SQL injection)
        
        RETURNS:
        - Очищенная строка
        """
        if dangerous_chars is None:
            dangerous_chars = [';', '--', '/*', '*/', "'", '"']
        
        sanitized = data
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        if sanitized != data:
            logging.getLogger("validator").warning("Обнаружены потенциально опасные символы")
        
        return sanitized


class RestartableComponent(ABC):
    """
    Миксин для компонентов с поддержкой перезапуска.

    Устраняет дублирование кода перезапуска в сервисах.
    """

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass

    async def restart(self) -> bool:
        """
        Перезапуск компонента.

        RETURNS:
        - True если перезапуск успешен
        """
        try:
            await self.shutdown()
            return await self.initialize()
        except Exception as e:
            # Пытаемся использовать event_bus_logger если доступен
            if hasattr(self, 'event_bus_logger') and self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка перезапуска: {e}")
            else:
                logging.getLogger(self.__class__.__name__).error(f"Ошибка перезапуска: {e}")
            return False

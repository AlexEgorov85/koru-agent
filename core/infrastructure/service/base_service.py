"""
Базовый класс для инфраструктурных сервисов.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.system_context.base_system_contex import BaseSystemContext


class ServiceInput(ABC):
    """Абстрактный класс для входных данных сервиса."""
    pass


class ServiceOutput(ABC):
    """Абстрактный класс для выходных данных сервиса."""
    pass


class BaseService(ABC):
    """
    Абстрактный базовый класс для всех инфраструктурных сервисов.

    ОСОБЕННОСТИ:
    - Обеспечивает единый интерфейс для всех сервисов
    - Предоставляет базовую функциональность логирования
    - Обеспечивает доступ к системному и сессионному контексту
    - Определяет общую структуру инициализации и жизненного цикла
    - Включает четкие контракты для входных и выходных данных
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Описание назначения сервиса.
        """
        pass

    def __init__(self, system_context: BaseSystemContext, name: Optional[str] = None):
        """
        Инициализация базового сервиса.

        ARGS:
        - system_context: системный контекст для доступа к ресурсам
        - name: опциональное имя сервиса (по умолчанию используется имя класса)
        """
        self.system_context = system_context
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

        self.logger.info(f"Инициализирован сервис: {self.name}")

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Инициализация сервиса.

        RETURNS:
        - True если инициализация прошла успешно, иначе False
        """
        pass

    @abstractmethod
    async def execute(self, input_data: ServiceInput) -> ServiceOutput:
        """
        Выполнение сервиса с четким контрактом входа/выхода.

        ARGS:
        - input_data: входные данные для сервиса

        RETURNS:
        - ServiceOutput: выходные данные сервиса
        """
        pass

    async def restart(self) -> bool:
        """
        Перезапуск сервиса без полной перезагрузки системного контекста.
        
        ВОЗВРАЩАЕТ:
        - bool: True если перезапуск прошел успешно, иначе False
        """
        try:
            # Сначала останавливаем текущий экземпляр
            await self.shutdown()
            
            # Затем инициализируем заново
            return await self.initialize()
        except Exception as e:
            self.logger.error(f"Ошибка перезапуска сервиса {self.name}: {str(e)}")
            return False

    async def restart_with_module_reload(self):
        """
        Перезапуск сервиса с перезагрузкой модуля Python.
        ВНИМАНИЕ: Использовать с осторожностью!
        
        ВОЗВРАЩАЕТ:
        - Новый экземпляр сервиса из перезагруженного модуля
        """
        from core.infrastructure.utils.module_reloader import safe_reload_component_with_module_reload
        self.logger.warning(f"Выполняется перезапуск с перезагрузкой модуля для сервиса {self.name}")
        return safe_reload_component_with_module_reload(self)

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Завершение работы сервиса.
        """
        pass

    def _validate_input(self, data: Dict[str, Any], required_fields: list) -> bool:
        """
        Валидация входных данных.

        ARGS:
        - data: словарь с входными данными
        - required_fields: список обязательных полей

        RETURNS:
        - True если все обязательные поля присутствуют, иначе False
        """
        for field in required_fields:
            if field not in data or data[field] is None:
                self.logger.error(f"Отсутствует обязательное поле: {field}")
                return False
        return True

    def _sanitize_input(self, data: str) -> str:
        """
        Санитизация входных данных для предотвращения инъекций.

        ARGS:
        - data: строка для санитизации

        RETURNS:
        - Очищенная строка
        """
        # Простая санитизация - удаление потенциально опасных символов
        # В реальном приложении может потребоваться более сложная логика
        sanitized = data.replace(';', '').replace('--', '').replace('/*', '').replace('*/', '')
        if sanitized != data:
            self.logger.warning("Обнаружены потенциально опасные символы во входных данных, выполнена санитизация")
        return sanitized
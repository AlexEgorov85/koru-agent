"""
Базовый класс для инфраструктурных сервисов.
"""
import logging
import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, ClassVar, List
from core.system_context.base_system_contex import BaseSystemContext
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent
from core.errors.architecture_violation import ArchitectureViolationError


class ServiceInput(ABC):
    """Абстрактный класс для входных данных сервиса."""
    pass


class ServiceOutput(ABC):
    """Абстрактный класс для выходных данных сервиса."""
    pass


class BaseService(BaseComponent):
    """
    Абстрактный базовый класс для всех инфраструктурных сервисов.

    ОСОБЕННОСТИ:
    - Обеспечивает единый интерфейс для всех сервисов
    - Предоставляет базовую функциональность логирования
    - Обеспечивает доступ к системному и сессионному контексту
    - Определяет общую структуру инициализации и жизненного цикла
    - Включает четкие контракты для входных и выходных данных
    - Поддерживает декларацию зависимостей через DEPENDENCIES
    """
    
    # Явная декларация зависимостей на уровне КЛАССА
    DEPENDENCIES: ClassVar[List[str]] = []

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Описание назначения сервиса.
        """
        pass

    def __init__(self, name: str, system_context: BaseSystemContext, component_config: Optional[ComponentConfig] = None):
        """
        Инициализация базового сервиса.

        ARGS:
        - name: имя сервиса
        - system_context: системный контекст для доступа к ресурсам
        - component_config: конфигурация компонента
        """
        # ЗАПРЕТ загрузки зависимостей в __init__
        if not hasattr(self.__class__, '_dependency_check_disabled'):
            frame = inspect.currentframe().f_back
            if frame.f_code.co_name == '__init__':
                raise ArchitectureViolationError(
                    f"Сервис '{name}' пытается загружать зависимости в __init__! "
                    "Загрузка зависимостей разрешена ТОЛЬКО в методе initialize()."
                )
        
        # Вызов конструктора родительского класса
        super().__init__(name, system_context, component_config)
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        
        self._dependencies: Dict[str, Any] = {}  # Кэш загруженных зависимостей
        self._initialized = False

        self.logger.info(f"Инициализирован сервис: {self.name}")

    async def initialize(self) -> bool:
        """
        Единая точка входа для инициализации с разрешением зависимостей.
        """
        if self._initialized:
            self.logger.warning(f"Сервис '{self.name}' уже инициализирован")
            return True
        
        # 1. Загрузка зависимостей
        if not await self._resolve_dependencies():
            return False
        
        # 2. Специфичная инициализация потомка
        try:
            if not await self._custom_initialize():
                self.logger.error(f"Пользовательская инициализация '{self.name}' не удалась")
                return False
        except Exception as e:
            self.logger.exception(f"Исключение в _custom_initialize() для '{self.name}': {e}")
            return False
        
        # 3. Финальная проверка
        if not await self._verify_readiness():
            self.logger.error(f"Проверка готовности '{self.name}' не пройдена")
            return False
        
        self._initialized = True
        self.logger.info(
            f"Сервис '{self.name}' инициализирован. "
            f"Зависимости: {list(self._dependencies.keys()) or 'отсутствуют'}"
        )
        return True

    async def _resolve_dependencies(self) -> bool:
        """
        Загрузка всех декларированных зависимостей.
        """
        for dep_name in self.DEPENDENCIES:
            dependency = await self.system_context.get_service(dep_name)
            if not dependency:
                self.logger.error(
                    f"Зависимость '{dep_name}' для сервиса '{self.name}' не найдена. "
                    f"Возможные причины:\n"
                    f"  1. Циклическая зависимость в графе сервисов\n"
                    f"  2. Сервис '{dep_name}' отключён в конфигурации\n"
                    f"  3. Ошибка в декларации зависимостей"
                )
                return False
            
            # Проверка инициализации зависимости
            if not getattr(dependency, '_initialized', False):
                self.logger.warning(
                    f"Зависимость '{dep_name}' для '{self.name}' ещё не инициализирована. "
                    "Это допустимо при топологической сортировке, но требует осторожности."
                )
            
            self._dependencies[dep_name] = dependency
            setattr(self, f"{dep_name}_instance", dependency)  # Удобный доступ через атрибут
        
        return True

    async def _custom_initialize(self) -> bool:
        """
        Специфичная логика инициализации для каждого сервиса.
        """
        # Вызов родительской инициализации
        return await super().initialize()

    async def _verify_readiness(self) -> bool:
        """
        Финальная проверка готовности сервиса к работе.
        """
        # Базовая проверка: все зависимости загружены
        for dep_name in self.DEPENDENCIES:
            if dep_name not in self._dependencies:
                return False
        return True

    def get_dependency(self, name: str) -> Optional[Any]:
        """
        Безопасное получение зависимости по имени.
        """
        return self._dependencies.get(name)

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
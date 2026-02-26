"""
Базовый класс для инфраструктурных сервисов.
"""
import logging
import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, ClassVar, List
from core.config.app_config import AppConfig
from core.components.base_component import BaseComponent
from core.models.errors.architecture_violation import ArchitectureViolationError
from core.models.enums.common_enums import ComponentType


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

    def __init__(self, name: str, application_context: 'ApplicationContext', app_config: Optional['AppConfig'] = None, executor=None, component_config: Optional['ComponentConfig'] = None):
        """
        Инициализация базового сервиса.

        ARGS:
        - name: имя сервиса
        - application_context: прикладной контекст для доступа к ресурсам
        - app_config: конфигурация приложения (AppConfig) [устаревший параметр]
        - executor: ActionExecutor для взаимодействия между компонентами
        - component_config: конфигурация компонента (ComponentConfig) [новый параметр]
        """
        # Для обратной совместимости с существующими сервисами,
        # преобразуем AppConfig в ComponentConfig
        from core.config.component_config import ComponentConfig
        
        # Новый путь: используем переданный component_config напрямую
        if component_config is not None and isinstance(component_config, ComponentConfig):
            # Используем существующий component_config (новый путь)
            pass
        elif app_config is not None:
            # Создаем ComponentConfig из AppConfig (старый путь)
            component_config = ComponentConfig(
                variant_id=getattr(app_config, 'config_id', f"service_{name}"),
                prompt_versions=getattr(app_config, 'prompt_versions', {}),
                input_contract_versions=getattr(app_config, 'input_contract_versions', {}),
                output_contract_versions=getattr(app_config, 'output_contract_versions', {}),
                side_effects_enabled=getattr(app_config, 'side_effects_enabled', True),
                detailed_metrics=getattr(app_config, 'detailed_metrics', False)
            )
        else:
            # Если app_config None, создаем пустой ComponentConfig
            component_config = ComponentConfig(
                variant_id=f"service_{name}",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={},
                side_effects_enabled=True,
                detailed_metrics=False
            )

        # Вызов конструктора родительского класса с ComponentConfig и executor
        super().__init__(name, application_context, component_config=component_config, executor=executor)

        # Устанавливаем атрибут component_config для обратной совместимости с существующими сервисами
        self.component_config = component_config

        # Сохраняем executor как атрибут
        self.executor = executor

        self._dependencies: Dict[str, Any] = {}  # Кэш загруженных зависимостей

        # Логгер уже инициализирован в базовом классе
        self.logger.info(f"Инициализирован сервис: {self.name}")

    async def initialize(self) -> bool:
        """
        Единая точка входа для инициализации с разрешением зависимостей.
        """
        self.logger.info(f"BaseService.initialize: начало инициализации для {self.name}")
        if getattr(self, '_initialized', False):
            self.logger.warning(f"Сервис '{self.name}' уже инициализирован")
            return True

        # 1. Загрузка зависимостей
        if not await self._resolve_dependencies():
            self.logger.error(f"Загрузка зависимостей не удалась для {self.name}")
            return False

        # 2. Вызов родительской инициализации (BaseComponent)
        try:
            self.logger.info(f"BaseService.initialize: вызов super().initialize() для {self.name}")
            base_result = await super().initialize()
            self.logger.info(f"BaseService.initialize: super().initialize() вернул {base_result} для {self.name}")
            if not base_result:
                self.logger.error(f"Инициализация BaseComponent для '{self.name}' не удалась")
                return False
        except Exception as e:
            self.logger.exception(f"Исключение в базовой инициализации для '{self.name}': {e}")
            return False

        # 3. Специфичная инициализация потомка
        try:
            if not await self._custom_initialize():
                self.logger.error(f"Пользовательская инициализация '{self.name}' не удалась")
                return False
        except Exception as e:
            self.logger.exception(f"Исключение в _custom_initialize() для '{self.name}': {e}")
            return False

        # 4. Финальная проверка
        if not await self._verify_readiness():
            self.logger.error(f"Проверка готовности '{self.name}' не пройдена")
            return False

        # Устанавливаем флаг инициализации
        self._initialized = True
        self.logger.info(
            f"Сервис '{self.name}' инициализирован. "
            f"Зависимости: {list(self._dependencies.keys()) or 'отсутствуют'}, "
            f"_initialized flag set to: {self._initialized}"
        )
        return True

    async def _resolve_dependencies(self) -> bool:
        """
        Загрузка всех декларированных зависимостей.
        """
        self.logger.info(f"_resolve_dependencies: начата обработка зависимостей для сервиса '{self.name}': {self.DEPENDENCIES}")
        
        missing_deps = []
        for dep_name in self.DEPENDENCIES:
            self.logger.debug(f"_resolve_dependencies: ищем зависимость '{dep_name}' для сервиса '{self.name}'")
            dependency = self.get_dependency(dep_name)
            if not dependency:
                self.logger.warning(
                    f"Зависимость '{dep_name}' для сервиса '{self.name}' не найдена. "
                    f"Возможные причины:\n"
                    f"  1. Зависимость еще не инициализирована\n"
                    f"  2. Циклическая зависимость в графе сервисов\n"
                    f"  3. Сервис '{dep_name}' отключён в конфигурации\n"
                    f"  4. Ошибка в декларации зависимостей"
                )
                self.logger.debug(f"_resolve_dependencies: список всех сервисов в контексте: {list(self.application_context.components._components.get(ComponentType.SERVICE, {}).keys())}")
                missing_deps.append(dep_name)
                # Continue instead of returning False immediately
                continue
            else:
                self.logger.info(f"_resolve_dependencies: зависимость '{dep_name}' найдена для сервиса '{self.name}'")

            # Проверка инициализации зависимости
            if not getattr(dependency, '_initialized', False):
                self.logger.warning(
                    f"Зависимость '{dep_name}' для '{self.name}' ещё не инициализирована. "
                    "Это допустимо при топологической сортировке, но требует осторожности."
                )
            else:
                self.logger.debug(f"_resolve_dependencies: зависимость '{dep_name}' для '{self.name}' уже инициализирована")

            self._dependencies[dep_name] = dependency
            setattr(self, f"{dep_name}_instance", dependency)  # Удобный доступ через атрибут

        # Return False only if ALL dependencies are missing
        if len(missing_deps) == len(self.DEPENDENCIES) and self.DEPENDENCIES:
            self.logger.error(f"Все зависимости для сервиса '{self.name}' отсутствуют: {missing_deps}")
            return False

        # Log warning if some dependencies are missing
        if missing_deps:
            self.logger.info(f"Некоторые зависимости для сервиса '{self.name}' будут загружены позже: {missing_deps}")
        else:
            self.logger.info(f"Все зависимости для сервиса '{self.name}' успешно разрешены")

        return True

    async def _custom_initialize(self) -> bool:
        """
        Специфичная логика инициализации для каждого сервиса.
        """
        # Вызов родительской инициализации
        return True  # BaseComponent.initialize() теперь вызывается в основном initialize()

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
        Сначала ищем в локальном кэше, затем в прикладном контексте.
        """
        self.logger.debug(f"get_dependency: ищем зависимость '{name}' для компонента '{self.name}'")
        
        # Сначала ищем в локальном кэше
        if name in self._dependencies:
            self.logger.debug(f"get_dependency: зависимость '{name}' найдена в локальном кэше компонента '{self.name}'")
            return self._dependencies[name]

        # Затем ищем в прикладном контексте
        if self.application_context:
            # Пытаемся получить сервис из прикладного контекста
            service = self.application_context.get_service(name)
            if service:
                self.logger.debug(f"get_dependency: сервис '{name}' найден в прикладном контексте для компонента '{self.name}'")
                return service
            else:
                self.logger.debug(f"get_dependency: сервис '{name}' НЕ НАЙДЕН в прикладном контексте для компонента '{self.name}'")
                # Дополнительная диагностика - проверим, что есть в компонентах
                all_services = list(self.application_context.components.all_of_type(ComponentType.SERVICE))
                self.logger.debug(f"get_dependency: все зарегистрированные сервисы: {[s.name for s in all_services]}")

            # Если не сервис, пробуем другие типы компонентов
            skill = self.application_context.get_skill(name)
            if skill:
                self.logger.debug(f"get_dependency: навык '{name}' найден в прикладном контексте для компонента '{self.name}'")
                return skill
            else:
                self.logger.debug(f"get_dependency: навык '{name}' НЕ НАЙДЕН в прикладном контексте для компонента '{self.name}'")

            tool = self.application_context.get_tool(name)
            if tool:
                self.logger.debug(f"get_dependency: инструмент '{name}' найден в прикладном контексте для компонента '{self.name}'")
                return tool
            else:
                self.logger.debug(f"get_dependency: инструмент '{name}' НЕ НАЙДЕН в прикладном контексте для компонента '{self.name}'")

        else:
            self.logger.error(f"get_dependency: application_context отсутствует для компонента '{self.name}'")

        self.logger.debug(f"get_dependency: зависимость '{name}' НЕ НАЙДЕНА для компонента '{self.name}'")
        return None

    def _convert_params_to_input(self, parameters: Dict[str, Any]) -> ServiceInput:
        """
        Преобразование параметров нового интерфейса в ServiceInput старого интерфейса.
        """
        raise NotImplementedError("_convert_params_to_input должен быть реализован в подклассе")

    async def execute(self, capability: 'Capability' = None, parameters: Dict[str, Any] = None, execution_context: 'ExecutionContext' = None, input_data: ServiceInput = None):
        """
        Универсальный метод выполнения, поддерживающий оба интерфейса.
        """
        # Если вызов происходит с новым интерфейсом (Capability, parameters, context)
        if capability is not None or parameters is not None or execution_context is not None:
            # Пытаемся преобразовать вызов к старому интерфейсу
            input_data = self._convert_params_to_input(parameters or {})
            return await self.execute_specific(input_data)
        elif input_data is not None:
            # Это вызов старого интерфейса
            return await self.execute_specific(input_data)
        else:
            # Это вызов с явным input_data (старый интерфейс)
            raise NotImplementedError("Метод execute_specific должен быть реализован в подклассе")
    
    async def execute_specific(self, input_data: ServiceInput) -> ServiceOutput:
        """
        Специфичный метод выполнения для конкретных сервисов.
        """
        raise NotImplementedError("Метод execute_specific должен быть реализован в подклассе")

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
        from core.utils.module_reloader import safe_reload_component_with_module_reload
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

    def _get_component_type(self) -> str:
        """Возвращает тип компонента для манифеста."""
        return "service"
    
    async def _validate_loaded_resources(self) -> bool:
        """Расширенная валидация для сервисов."""
        if not await super()._validate_loaded_resources():
            return False

        # ← НОВОЕ: Валидация методов сервиса
        if hasattr(self, 'methods'):
            for method_name in self.methods:
                cap_name = f"{self.name}.{method_name}"

                # Проверка наличия контрактов для метода
                if cap_name not in self.input_contracts:
                    self.logger.warning(
                        f"{self.name}: Метод '{method_name}' не имеет input контракта"
                    )

                if cap_name not in self.output_contracts:
                    self.logger.warning(
                        f"{self.name}: Метод '{method_name}' не имеет output контракта"
                    )

        return True
    
    def get_timeout_seconds(self) -> int:
        """Возвращает timeout из манифеста."""
        if self.component_config and self.component_config.constraints:
            return self.component_config.constraints.get('timeout_seconds', 30)
        return 30
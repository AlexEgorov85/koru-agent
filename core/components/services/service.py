"""
Упрощённый базовый класс для сервисов (Services).

ARCHITECTURE:
- Тонкая оболочка над Component
- Содержит только специфичную логику сервисов
- Поддержка зависимостей через DEPENDENCIES
- Устранено дублирование с BaseSkill/BaseTool
- Логирование через стандартный logging (НЕ через event_bus)

USAGE:
```python
class MyService(Service):
    DEPENDENCIES = ["database", "cache"]

    def __init__(self, name, config, executor):
        super().__init__(
            name=name,
            component_config=config,
            executor=executor
        )

    async def _custom_initialize(self) -> bool:
        # Специфичная инициализация сервиса
        return True

    async def _execute_impl(self, capability, parameters, context):
        # Бизнес-логика сервиса
        return {"result": "done"}
```
"""
from typing import List, Any, Optional, Dict, ClassVar
from abc import abstractmethod

from core.config.component_config import ComponentConfig
from core.agent.components.component import Component


class Service(Component):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ИНФРАСТРУКТУРНЫХ СЕРВИСОВ.

    ОСОБЕННОСТИ:
    - Обеспечивает единый интерфейс для всех сервисов
    - Предоставляет базовую функциональность логирования
    - Поддерживает декларацию зависимостей через DEPENDENCIES
    - Определяет общую структуру инициализации и жизненного цикла
    """

    # Явная декларация зависимостей на уровне КЛАССА
    DEPENDENCIES: ClassVar[List[str]] = []

    @property
    @abstractmethod
    def description(self) -> str:
        """Описание назначения сервиса."""
        pass

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: Any,
        application_context: Optional[Any] = None
    ):
        """
        Инициализация сервиса.

        ARGS:
        - name: Имя сервиса
        - component_config: Конфигурация компонента
        - executor: ActionExecutor для взаимодействия
        - application_context: ApplicationContext (опционально)
        """
        super().__init__(
            name=name,
            component_type="service",
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
        
        # Кэш загруженных зависимостей
        self._dependencies: Dict[str, Any] = {}
    
    async def initialize(self) -> bool:
        """
        Единая точка входа для инициализации с разрешением зависимостей.
        """
        # Логирование начала инициализации
        self._log_sync("info", "Начало инициализации сервиса")
        
        # 1. Загрузка зависимостей
        if not await self._resolve_dependencies():
            self._log_sync("error", "Загрузка зависимостей не удалась")
            return False
        
        # 2. Вызов родительской инициализации (Component)
        try:
            base_result = await super().initialize()
            if not base_result:
                self._log_sync("error", "Инициализация Component не удалась")
                return False
        except Exception as e:
            self._log_sync("error", f"Исключение в базовой инициализации: {e}", exception=e)
            return False
        
        # 3. Специфичная инициализация потомка
        try:
            if not await self._custom_initialize():
                self._log_sync("error", "Пользовательская инициализация не удалась")
                return False
        except Exception as e:
            self._log_sync("error", f"Исключение в _custom_initialize(): {e}", exception=e)
            return False
        
        # 4. Финальная проверка
        if not await self._verify_readiness():
            self._log_sync("error", "Проверка готовности не пройдена")
            return False
        
        return True
    
    async def _resolve_dependencies(self) -> bool:
        """
        Загрузка всех декларированных зависимостей.
        """
        if not self.DEPENDENCIES:
            return True
        
        self._log_sync("info", f"Загрузка зависимостей: {self.DEPENDENCIES}")
        
        missing_deps = []
        for dep_name in self.DEPENDENCIES:
            dependency = self.get_dependency(dep_name)
            
            if not dependency:
                self._log_sync("warning", f"Зависимость '{dep_name}' не найдена")
                missing_deps.append(dep_name)
                continue
            
            # Проверка инициализации зависимости
            if hasattr(dependency, '_initialized') and not dependency._initialized:
                self._log_sync("warning", f"Зависимость '{dep_name}' ещё не инициализирована")
            
            self._dependencies[dep_name] = dependency
        
        # Возвращаем False только если ВСЕ зависимости отсутствуют
        if len(missing_deps) == len(self.DEPENDENCIES) and self.DEPENDENCIES:
            self._log_sync("error", f"Все зависимости отсутствуют: {missing_deps}")
            return False
        
        # Логирование предупреждения если некоторые зависимости отсутствуют
        if missing_deps:
            self._log_sync("info", f"Некоторые зависимости будут загружены позже: {missing_deps}")
        
        return True
    
    async def _custom_initialize(self) -> bool:
        """
        Специфичная логика инициализации для каждого сервиса.
        
        Переопределяется в наследниках.
        """
        return True
    
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
        Сначала ищем в локальном кэше, затем в registry компонентов.
        """
        # Сначала ищем в локальном кэше
        if name in self._dependencies:
            return self._dependencies[name]
        
        # Затем ищем в registry компонентов
        if self._application_context and hasattr(self._application_context, 'components'):
            from core.models.enums.common_enums import ComponentType
            dependency = self._application_context.components.get_component(
                ComponentType.SERVICE,
                name
            )
            if dependency:
                self._dependencies[name] = dependency
                return dependency
        
        return None
    
    async def shutdown(self):
        """Завершение работы сервиса."""
        await super().shutdown()

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.application_context.application_context import ApplicationContext
from core.agent.components.action_executor import ExecutionContext


from core.config.component_config import ComponentConfig
from core.agent.components.base_component import BaseComponent

# =============================================================================
# БАЗОВЫЕ КЛАССЫ
# =============================================================================

class ToolInput(ABC):
    """Абстрактный класс для входных данных инструмента."""
    pass

class ToolOutput(ABC):
    """Абстрактный класс для выходных данных инструмента."""
    pass

class BaseTool(BaseComponent):
    """
    Базовый класс для инструментов с инверсией зависимостей.
    
    ЖИЗНЕННЫЙ ЦИКЛ:
    - Наследует LifecycleMixin через BaseComponent
    - Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """Описание назначения инструмента."""
        pass

    def __init__(
        self,
        name: str,
        application_context: ApplicationContext,
        component_config: Optional[ComponentConfig] = None,
        executor=None,
        event_bus = None,  # ← Только для логирования
        **kwargs
    ):
        # Вызов конструктора родительского класса
        # event_bus передаётся от ComponentFactory для логирования
        super().__init__(
            name,
            application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )
        self.config = kwargs
        self.executor = executor  # Сохраняем executor как атрибут

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения инструмента."""
        # Для инструментов нет специального события, используем общее
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.ACTION_PERFORMED

    async def execute(self, capability: 'Capability' = None, parameters: Dict[str, Any] = None, execution_context: ExecutionContext = None, input_data: ToolInput = None):
        """
        Универсальный метод выполнения, поддерживающий оба интерфейса.
        """
        # Если вызов происходит с новым интерфейсом (Capability, parameters, context)
        if capability is not None or parameters is not None or execution_context is not None:
            # Используем универсальный шаблон выполнения из BaseComponent
            if capability is None:
                # Создаём capability по умолчанию для инструмента
                from core.models.data.capability import Capability
                capability = Capability(
                    name=f"{self.name}.default",
                    description=f"Операция инструмента {self.name}",
                    skill_name=self.name
                )
            
            return await super().execute(capability, parameters or {}, execution_context)
        
        elif input_data is not None:
            # Это вызов старого интерфейса - преобразуем в новый
            from core.models.data.capability import Capability
            from core.agent.components.action_executor import ExecutionContext
            
            capability = Capability(
                name=f"{self.name}.default",
                description=f"Операция инструмента {self.name}",
                skill_name=self.name
            )
            
            # Преобразуем ToolInput в parameters
            parameters = {}
            if hasattr(input_data, '__dict__'):
                parameters = input_data.__dict__
            
            return await super().execute(capability, parameters, ExecutionContext())
        
        else:
            # Это вызов с явным input_data (старый интерфейс)
            raise NotImplementedError("Метод execute_specific должен быть реализован в подклассе")

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики инструмента (СИНХРОННАЯ).

        Преобразует параметры в ToolInput и вызывает execute_specific.
        """
        input_data = self._convert_params_to_input(parameters)
        result = self.execute_specific(input_data)

        # Преобразуем результат в словарь
        if hasattr(result, '__dict__'):
            return result.__dict__
        return {'result': result}

    def execute_specific(self, input_data: ToolInput) -> ToolOutput:
        """
        Специфичный метод выполнения для конкретных инструментов (СИНХРОННЫЙ).
        """
        raise NotImplementedError("Метод execute_specific должен быть реализован в подклассе")

    def _convert_params_to_input(self, parameters: Dict[str, Any]) -> ToolInput:
        """
        Преобразование параметров нового интерфейса в ToolInput старого интерфейса.
        """
        raise NotImplementedError("_convert_params_to_input должен быть реализован в подклассе")

    def _get_component_type(self) -> str:
        """Возвращает тип компонента для манифеста."""
        return "tool"
    
    async def _validate_loaded_resources(self) -> bool:
        """Расширенная валидация для инструментов."""
        if not await super()._validate_loaded_resources():
            return False

        # ← НОВОЕ: Валидация операций инструмента
        if hasattr(self, 'operations'):
            for op_name in self.operations:
                cap_name = f"{self.name}.{op_name}"

                # Проверка наличия контрактов для операции
                if cap_name not in self.input_contracts:
                    self.logger.error(
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        f"{self.name}: Операция '{op_name}' не имеет input контракта"
                    )
                    return False

                if cap_name not in self.output_contracts:
                    self.logger.error(
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                        f"{self.name}: Операция '{op_name}' не имеет output контракта"
                    )
                    return False

        return True
    
    def get_allowed_operations(self) -> List[str]:
        """Возвращает список allowed operations из манифеста."""
        if self.component_config and self.component_config.constraints:
            return self.component_config.constraints.get('allowed_operations', [])
        return []
    
    def is_side_effects_enabled(self) -> bool:
        """Проверяет, разрешены ли side effects из манифеста."""
        if self.component_config and self.component_config.constraints:
            return self.component_config.constraints.get('side_effects_enabled', False)
        return False

    def get_capabilities(self) -> List['Capability']:
        """
        Возвращает список возможностей, которые предоставляет инструмент.

        ВОЗВРАЩАЕТ:
        - List[Capability]: Список capability для каждой операции инструмента

        ПРИМЕЧАНИЕ:
        - Использует компонент_config для получения списка операций
        - Каждая операция становится отдельным capability
        """
        from core.models.data.capability import Capability

        capabilities = []

        # Получаем список операций из конфигурации
        allowed_operations = self.get_allowed_operations()
        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"Инструмент {self.name}: allowed_operations={allowed_operations}")

        if not allowed_operations and self.component_config:
            # Если operations не указаны явно, извлекаем из input_contract_versions
            if hasattr(self.component_config, 'input_contract_versions'):
                # Извлекаем имена операций из ключей input_contract_versions
                for cap_name in self.component_config.input_contract_versions.keys():
                    # Проверяем, что capability принадлежит этому инструменту
                    # Например, для vector_books_tool: vector_books.search, vector_books.get_document
                    # Для file_tool: file_tool.read_write
                    if cap_name.startswith(f"{self.name}.") or cap_name.startswith(self.name.replace("_tool", ".")):
                        allowed_operations.append(cap_name)
                if self.event_bus_logger:
                    self.event_bus_logger.debug_sync(f"Инструмент {self.name}: извлечено operations из input_contract_versions: {allowed_operations}")

        # Создаём capability для каждой операции
        for op_name in allowed_operations:
            # Формируем полное имя capability
            cap_full_name = op_name if '.' in op_name else f"{self.name}.{op_name}"

            capabilities.append(Capability(
                name=cap_full_name,
                description=f"Операция '{op_name}' инструмента {self.name}",
                skill_name=self.name,
                supported_strategies=["react"],  # Инструменты поддерживают react стратегию
                visiable=True,
                meta={
                    "tool": self.name,
                    "operation": op_name,
                    "contract_version": self.component_config.input_contract_versions.get(cap_full_name, "v1.0.0") if self.component_config else "v1.0.0"
                }
            ))

        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"Инструмент {self.name} вернул {len(capabilities)} capability: {[c.name for c in capabilities]}")
        return capabilities

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы."""
        pass
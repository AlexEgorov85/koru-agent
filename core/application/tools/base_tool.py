from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING, List

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.models.capability import Capability
    from core.models.execution_context import ExecutionContext
    from core.models.action_result import ActionResult

from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent

class ToolInput(ABC):
    """Абстрактный класс для входных данных инструмента."""
    pass

class ToolOutput(ABC):
    """Абстрактный класс для выходных данных инструмента."""
    pass

class BaseTool(BaseComponent):
    """Базовый класс для инструментов с инверсией зависимостей."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Описание назначения инструмента."""
        pass

    def __init__(self, name: str, application_context: 'ApplicationContext', component_config: Optional[ComponentConfig] = None, executor=None, **kwargs):
        # Вызов конструктора родительского класса
        super().__init__(name, application_context, component_config, executor)
        self.config = kwargs
        self.executor = executor  # Сохраняем executor как атрибут

    async def execute(self, capability: 'Capability' = None, parameters: Dict[str, Any] = None, execution_context: 'ExecutionContext' = None, input_data: ToolInput = None):
        """
        Универсальный метод выполнения, поддерживающий оба интерфейса.
        """
        # Если вызов происходит с новым интерфейсом (Capability, parameters, context)
        if capability is not None or parameters is not None or execution_context is not None:
            # Пытаемся преобразовать вызов к старому интерфейсу
            input_data = self._convert_params_to_input(parameters or {})
            result = await self.execute_specific(input_data)

            # Преобразуем результат в ActionResult для нового интерфейса
            from core.models.action_result import ActionResult
            return ActionResult(
                success=True,
                data=result.__dict__ if hasattr(result, '__dict__') else {'result': result},
                metadata={'tool': self.name}
            )
        elif input_data is not None:
            # Это вызов старого интерфейса
            return await self.execute_specific(input_data)
        else:
            # Это вызов с явным input_data (старый интерфейс)
            raise NotImplementedError("Метод execute_specific должен быть реализован в подклассе")

    async def execute_specific(self, input_data: ToolInput) -> ToolOutput:
        """
        Специфичный метод выполнения для конкретных инструментов.
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
                if cap_name not in self._cached_input_contracts:
                    self.logger.error(
                        f"{self.name}: Операция '{op_name}' не имеет input контракта"
                    )
                    return False
                
                if cap_name not in self._cached_output_contracts:
                    self.logger.error(
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

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы."""
        pass
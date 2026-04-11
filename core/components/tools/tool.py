"""
Упрощённый базовый класс для инструментов (Tools).

ARCHITECTURE:
- Тонкая оболочка над Component
- Содержит только специфичную логику инструментов
- Поддержка операций через operations
- Устранено дублирование с BaseSkill/BaseService
- Логирование через стандартный logging (НЕ через event_bus)

USAGE:
```python
class MyTool(Tool):
    def __init__(self, name, config, executor):
        super().__init__(
            name=name,
            component_config=config,
            executor=executor
        )

    async def _execute_impl(self, capability, parameters, context):
        # Бизнес-логика инструмента
        return {"result": "done"}
```
"""
from typing import List, Any, Optional, Dict
from abc import ABC, abstractmethod

from core.models.data.capability import Capability
from core.config.component_config import ComponentConfig
from core.agent.components.component import Component


# =============================================================================
# БАЗОВЫЕ КЛАССЫ ДЛЯ ИНСТРУМЕНТОВ
# =============================================================================

class ToolInput(ABC):
    """Абстрактный класс для входных данных инструмента."""
    pass

class ToolOutput(ABC):
    """Абстрактный класс для выходных данных инструмента."""
    pass


class Tool(Component):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ИНСТРУМЕНТОВ.

    ОСОБЕННОСТИ:
    - Обеспечивает единый интерфейс для всех инструментов
    - Предоставляет базовую функциональность логирования
    - Поддерживает операции через operations
    - Определяет общую структуру инициализации и жизненного цикла
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """Описание назначения инструмента."""
        pass

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: Any,
        application_context: Optional[Any] = None
    ):
        """
        Инициализация инструмента.

        ARGS:
        - name: Имя инструмента
        - component_config: Конфигурация компонента
        - executor: ActionExecutor для взаимодействия
        - application_context: ApplicationContext (опционально)
        """
        super().__init__(
            name=name,
            component_type="tool",
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
    
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
    
    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список возможностей, которые предоставляет инструмент.
        
        ВОЗВРАЩАЕТ:
        - List[Capability]: Список capability для каждой операции инструмента
        
        ПРИМЕЧАНИЕ:
        - Использует компонент_config для получения списка операций
        - Каждая операция становится отдельным capability
        """
        capabilities = []
        
        # Получаем список операций из конфигурации
        allowed_operations = self.get_allowed_operations()
        
        if not allowed_operations and self.component_config:
            # Если operations не указаны явно, извлекаем из input_contract_versions
            if hasattr(self.component_config, 'input_contract_versions'):
                for cap_name in self.component_config.input_contract_versions.keys():
                    # Проверяем, что capability принадлежит этому инструменту
                    if cap_name.startswith(f"{self.name}.") or cap_name.startswith(self.name.replace("_tool", ".")):
                        allowed_operations.append(cap_name)
        
        # Создаём capability для каждой операции
        for op_name in allowed_operations:
            # Формируем полное имя capability
            cap_full_name = op_name if '.' in op_name else f"{self.name}.{op_name}"
            
            capabilities.append(Capability(
                name=cap_full_name,
                description=f"Операция '{op_name}' инструмента {self.name}",
                skill_name=self.name,
                supported_strategies=["react"],
                visiable=True,
                meta={
                    "tool": self.name,
                    "operation": op_name,
                    "contract_version": self.component_config.input_contract_versions.get(cap_full_name, "v1.0.0") if self.component_config else "v1.0.0"
                }
            ))
        
        return capabilities
    
    async def shutdown(self):
        """Завершение работы инструмента."""
        await super().shutdown()

"""
Упрощённый базовый класс для навыков (Skills).

ARCHITECTURE:
- Тонкая оболочка над Component
- Содержит только специфичную логику навыков
- Устранено дублирование с BaseService/BaseTool
- Логирование через стандартный logging (НЕ через event_bus)

USAGE:
```python
class MySkill(Skill):
    def __init__(self, name, config, executor):
        super().__init__(
            name=name,
            component_config=config,
            executor=executor
        )

    def get_capabilities(self) -> List[Capability]:
        return [...]

    async def _execute_impl(self, capability, parameters, context):
        # Бизнес-логика навыка
        return {"result": "done"}
```
"""
from typing import List, Any, Optional, Dict
from abc import abstractmethod

from core.models.data.capability import Capability
from core.config.component_config import ComponentConfig
from core.components.component import Component


class Skill(Component):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ НАВЫКОВ.

    АРХИТЕКТУРНАЯ РОЛЬ:
    - Skill = "как думать и что делать"
    - Capability = "что именно можно сделать"

    Один Skill может иметь несколько Capability.
    """

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: Any,
        application_context: Optional[Any] = None
    ):
        """
        Инициализация навыка.

        ARGS:
        - name: Имя навыка
        - component_config: Конфигурация компонента
        - executor: ActionExecutor для взаимодействия
        - application_context: ApplicationContext (опционально)
        """
        super().__init__(
            name=name,
            component_type="skill",
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
    
    @property
    def description(self) -> str:
        """Описание навыка."""
        return f"Навык {self.name}"
    
    @abstractmethod
    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список возможностей, которые предоставляет навык.
        
        Пример:
        PlanningSkill:
            - planning.create_plan
            - planning.update_plan
        
        ВАЖНО:
        - Метод должен быть реализован в дочерних классах
        - Возвращаемые capability должны быть валидными для системы
        - Имена capability должны быть уникальными в рамках системы
        """
        pass
    
    def get_capability_names(self) -> List[str]:
        """Возвращает список capability, поддерживаемых навыком."""
        capabilities = self.get_capabilities()
        return [cap.name for cap in capabilities]
    
    def get_capability_by_name(self, capability_name: str) -> Capability:
        """
        Поиск capability по имени.
        
        ПАРАМЕТРЫ:
        - capability_name: Имя capability для поиска
        
        ВОЗВРАЩАЕТ:
        - Capability объект если найден
        
        ИСКЛЮЧЕНИЯ:
        - ValueError если capability не найдена
        
        ОСОБЕННОСТИ:
        - Регистронезависимый поиск
        - Быстрый поиск через итерацию списка
        """
        for cap in self.get_capabilities():
            if cap.name.lower() == capability_name.lower():
                return cap
        raise ValueError(f"Capability '{capability_name}' не найдена в skill '{self.name}'")
    
    def get_required_capabilities(self) -> List[str]:
        """Возвращает список required capabilities из манифеста."""
        if self.component_config and self.component_config.constraints:
            return self.component_config.constraints.get('required_capabilities', [])
        return []
    
    async def shutdown(self):
        """Завершение работы навыка."""
        await super().shutdown()

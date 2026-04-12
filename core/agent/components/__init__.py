"""
Модуль компонентов.

КОМПОНЕНТЫ:
- component: универсальный базовый класс для всех компонентов
- action_executor: исполнитель действий
- component_factory: фабрика создания компонентов
- component_discovery: автоматическое обнаружение компонентов

USAGE:
```python
from core.agent.components import Component
```
"""
from .component import Component
from .action_executor import ActionExecutor, ExecutionContext
from .component_factory import ComponentFactory
from .component_discovery import ComponentDiscovery
from .lifecycle import ComponentLifecycle
from core.models.enums.component_status import ComponentStatus

__all__ = [
    'Component',
    'ActionExecutor',
    'ExecutionContext',
    'ComponentFactory',
    'ComponentDiscovery',
    'ComponentLifecycle',
    'ComponentStatus',
]

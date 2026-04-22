"""
core.components - базовые классы и инфраструктура компонентов.

КОМПОНЕНТЫ:
- component: базовый класс Component
- lifecycle: управление жизненным циклом
- action_executor: исполнитель действий
- component_factory: фабрика создания компонентов
- component_discovery: обнаружение компонентов

USAGE:
```python
from core.components import Component
from core.components.action_executor import ActionExecutor, ExecutionContext
```
"""
from .component import Component
from .lifecycle import ComponentLifecycle
from .action_executor import ActionExecutor, ExecutionContext
from .component_factory import ComponentFactory
from .component_discovery import ComponentDiscovery

__all__ = [
    'Component',
    'ComponentLifecycle',
    'ActionExecutor',
    'ExecutionContext',
    'ComponentFactory',
    'ComponentDiscovery',
]
"""
Модуль компонентов.

КОМПОНЕНТЫ:
- base_component: базовый класс для всех компонентов
- component_discovery: динамическое обнаружение компонентов

USAGE:
```python
from core.components import (
    BaseComponent,
    ComponentDiscovery,
    ComponentInfo,
    get_component_discovery,
)

# Обнаружение компонентов
discovery = get_component_discovery()
components = await discovery.discover()

# Получение компонента
component_info = discovery.get_component("planning")
```
"""
from .base_component import BaseComponent
from .component_discovery import (
    ComponentDiscovery,
    ComponentInfo,
    ComponentStatus,
    ComponentNotFoundError,
    ComponentLoadError,
    get_component_discovery,
    create_component_discovery,
    reset_component_discovery,
)

__all__ = [
    # Base components
    'BaseComponent',
    
    # Component discovery
    'ComponentDiscovery',
    'ComponentInfo',
    'ComponentStatus',
    'ComponentNotFoundError',
    'ComponentLoadError',
    'get_component_discovery',
    'create_component_discovery',
    'reset_component_discovery',
]

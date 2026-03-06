"""
Модуль внедрения зависимостей (Dependency Injection).

USAGE:
```python
from core.di import DependencyContainer, inject

container = DependencyContainer()
container.register_singleton(DatabaseInterface, db_provider)

@inject
def create_service(db: DatabaseInterface):
    return MyService(db=db)

service = create_service(container)
```
"""

from core.di.container import DependencyContainer, ServiceLifetime, ServiceDescriptor
from core.di.inject import inject, inject_field, resolve_dependencies

__all__ = [
    "DependencyContainer",
    "ServiceLifetime",
    "ServiceDescriptor",
    "inject",
    "inject_field",
    "resolve_dependencies",
]

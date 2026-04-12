"""
Enum статусов компонента.

Вынесен в отдельный модуль для предотвращения циклических импортов.
Цепочка была: infrastructure_context → lifecycle_manager → components.lifecycle → __init__.py → component_factory → infrastructure_context

USAGE:
```python
from core.models.enums.component_status import ComponentStatus
```
"""
from enum import Enum


class ComponentStatus(Enum):
    """
    Статусы жизненного цикла компонента/ресурса.

    DIAGRAM:
    CREATED → INITIALIZING → READY → SHUTDOWN
                ↓
              FAILED (при ошибке)

    PENDING — используется только в ResourceRecord (LifecycleManager).
    """
    CREATED = "created"           # Экземпляр создан, не инициализирован
    PENDING = "pending"           # Зарегистрирован, ждёт инициализации (LifecycleManager)
    INITIALIZING = "initializing" # В процессе инициализации
    READY = "ready"               # Готов к работе
    FAILED = "failed"             # Ошибка инициализации
    SHUTDOWN = "shutdown"         # Завершён

    @property
    def is_ready_state(self) -> bool:
        """Готов к работе."""
        return self == ComponentStatus.READY

    @property
    def is_terminal(self) -> bool:
        """Терминальное состояние (нельзя перейти в другое)."""
        return self in (ComponentStatus.READY, ComponentStatus.FAILED, ComponentStatus.SHUTDOWN)

    def __str__(self) -> str:
        return self.value

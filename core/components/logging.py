"""
LoggingMixin для BaseComponent.

ПЕРЕИСПОЛЬЗУЕТ существующий EventBusLogger вместо создания нового функционала.

USAGE:
```python
class BaseComponent(LifecycleMixin, LoggingMixin, ABC):
    pass
```
"""
from typing import Optional, Callable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
    from core.interfaces.event_bus import EventBusInterface


class LoggingMixin:
    """
    Миксин логирования для компонентов.

    ПЕРЕИСПОЛЬЗУЕТ:
    - EventBusLogger для асинхронного логирования
    - SyncLoggerMixin методы через event_bus_logger.*_sync()

    АТРИБУТЫ:
    - event_bus_logger: EventBusLogger экземпляр
    - _event_bus: EventBusInterface для создания логгера
    """

    def __init__(
        self,
        event_bus: Optional['EventBusInterface'] = None,
        component_name: str = "unknown",
        get_init_state_callback: Optional[Callable] = None,
        require_event_bus: bool = True  # ← НОВОЕ: требовать event_bus по умолчанию
    ):
        """
        Инициализация логгера.

        ARGS:
        - event_bus: EventBusInterface для создания логгера
        - component_name: Имя компонента для логирования
        - get_init_state_callback: Callback для получения состояния инициализации
        - require_event_bus: Требовать event_bus (True по умолчанию для безопасности)
        
        RAISES:
        - ValueError: если require_event_bus=True и event_bus=None
        """
        self._event_bus = event_bus
        self._get_init_state_callback = get_init_state_callback
        self.event_bus_logger = None

        if event_bus is not None:
            self._init_event_bus_logger(component_name)
        elif require_event_bus:
            # ← НОВОЕ: Запрещаем инициализацию без event_bus
            raise ValueError(
                f"Component '{component_name}' requires event_bus for logging. "
                "Pass event_bus parameter or set require_event_bus=False for testing."
            )

    def _init_event_bus_logger(self, component_name: str = "unknown"):
        """
        Инициализация EventBusLogger.

        ПЕРЕИСПОЛЬЗУЕТ существующий класс EventBusLogger.

        ARGS:
        - component_name: Имя компонента
        """
        from core.infrastructure.logging import EventBusLogger
        
        # Получаем session_id и agent_id из компонента если есть
        session_id = getattr(self, 'session_id', 'system')
        agent_id = getattr(self, 'agent_id', 'system')
        
        # Создаём EventBusLogger с callback если есть
        if self._get_init_state_callback:
            self.event_bus_logger = EventBusLogger(
                event_bus=self._event_bus,
                session_id=session_id,
                agent_id=agent_id,
                component=component_name,
                get_init_state_callback=self._get_init_state_callback
            )
        else:
            self.event_bus_logger = EventBusLogger(
                event_bus=self._event_bus,
                session_id=session_id,
                agent_id=agent_id,
                component=component_name
            )

    def _safe_log_sync(self, level: str, message: str, *args, **kwargs):
        """
        Безопасное синхронное логирование.

        ПЕРЕИСПОЛЬЗУЕТ методы EventBusLogger.

        ARGS:
        - level: Уровень логирования (info, debug, warning, error)
        - message: Сообщение
        - *args: Аргументы для форматирования
        - **kwargs: Дополнительные данные
        """
        if self.event_bus_logger and hasattr(self.event_bus_logger, f'{level}_sync'):
            try:
                getattr(self.event_bus_logger, f'{level}_sync')(message, *args, **kwargs)
            except Exception:
                # Fallback на print если логгер недоступен
                print(f"[{level.upper()}] {message}", flush=True)

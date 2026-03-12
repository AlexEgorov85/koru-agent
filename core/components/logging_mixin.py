"""
Миксин логирования для компонентов.

СОДЕРЖИТ:
- LoggingMixin: миксин для универсального логирования через EventBus
"""
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.infrastructure.logging import EventBusLogger
    from core.infrastructure.event_bus.unified_event_bus import EventBusInterface


class LoggingMixin:
    """
    Миксин для управления логированием компонентов.

    FEATURES:
    - Интеграция с EventBusLogger
    - Поддержка синхронного и асинхронного логирования
    - Автоматическое переключение режимов (init → ready)
    - Dummy-логгер для компонентов без event_bus

    USAGE:
    ```python
    class MyComponent(LoggingMixin):
        def __init__(self, event_bus: Optional[EventBusInterface] = None):
            self._event_bus = event_bus
            self._init_event_bus_logger()
        
        async def initialize(self):
            self.event_bus_logger._set_initializing()
            self._safe_log_sync("info", "Инициализация...")
            # ...
            self.event_bus_logger._set_ready()
        
        def some_method(self):
            self._safe_log_sync("debug", "Отладочное сообщение")
    ```
    """

    def __init__(
        self,
        event_bus: Optional['EventBusInterface'] = None,
        application_context=None,  # DEPRECATED: для обратной совместимости
        component_name: str = "component"
    ):
        """
        Инициализация миксина логирования.

        ARGS:
        - event_bus: EventBusInterface для логирования
        - application_context: контекст приложения (DEPRECATED)
        - component_name: имя компонента для логирования
        """
        self._event_bus = event_bus
        self._application_context = application_context
        # component_name будет установлен в BaseComponent через name
        self.event_bus_logger: Optional['EventBusLogger'] = None

    def _init_event_bus_logger(self, component_name: str = "component"):
        """
        Инициализация EventBusLogger для асинхронного логирования.
        
        ARGS:
        - component_name: имя компонента для логирования
        """
        from core.infrastructure.logging import EventBusLogger

        # Сначала пробуем внедрённый event_bus
        if self._event_bus is not None:
            self.event_bus_logger = EventBusLogger(
                self._event_bus,
                session_id="system",
                agent_id="system",
                component=component_name,
                get_init_state_callback=getattr(self, '_get_logger_init_state', None)
            )
        # Fallback на application_context для обратной совместимости
        elif self._application_context is not None:
            if hasattr(self._application_context, 'infrastructure_context'):
                event_bus = getattr(self._application_context.infrastructure_context, 'event_bus', None)
                if event_bus:
                    self.event_bus_logger = EventBusLogger(
                        event_bus,
                        session_id="system",
                        agent_id="system",
                        component=component_name,
                        get_init_state_callback=getattr(self, '_get_logger_init_state', None)
                    )
        # Fallback на dummy-логгер если ничего не доступно
        else:
            self.event_bus_logger = self._create_dummy_logger()

    def _create_dummy_logger(self):
        """Создаёт dummy-логгер для компонентов без event_bus."""
        class DummyLogger:
            info = debug = warning = error = exception = lambda s, *a, **k: None
            info_sync = debug_sync = warning_sync = error_sync = lambda s, *a, **k: None
        return DummyLogger()

    def _safe_log_sync(self, level: str, message: str, **kwargs):
        """
        Безопасный синхронный логгер — проверяет event_bus_logger на None.

        ПАРАМЕТРЫ:
        - level: уровень логирования ('info', 'debug', 'warning', 'error')
        - message: сообщение
        - **kwargs: дополнительные аргументы для логгера
        """
        if hasattr(self, 'event_bus_logger') and self.event_bus_logger is not None:
            log_method = getattr(self.event_bus_logger, f'{level}_sync', None)
            if log_method:
                log_method(message, **kwargs)

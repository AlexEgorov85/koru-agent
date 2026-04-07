"""
Telemetry Collector — единая точка сбора телеметрии.

АРХИТЕКТУРА:
┌─────────────────────────────────────────────────────────────┐
│                    TelemetryCollector                       │
│  (подписка на события EventBus)                             │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ TerminalHandler │  │ SessionHandler  │  │ MetricsHandler  │
│ (консоль)       │  │ (файлы сессий)  │  │ (метрики)       │
└─────────────────┘  └─────────────────┘  └─────────────────┘

USAGE:
```python
telemetry = TelemetryCollector(event_bus, storage)
await telemetry.initialize()
```
"""
from typing import Optional
from pathlib import Path

from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.telemetry.handlers.terminal_handler import TerminalLogHandler
from core.infrastructure.telemetry.handlers.session_handler import SessionLogHandler
from core.infrastructure.telemetry.storage.metrics_storage import FileSystemMetricsStorage
from core.components.services.metrics_publisher import MetricsPublisher
from core.infrastructure.collectors.base.base_collector import BaseEventCollector


class TelemetryCollector(BaseEventCollector):
    """
    Единый сборщик телеметрии.

    RESPONSIBILITIES:
    - Подписка на события EventBus
    - Маршрутизация событий обработчикам
    - Сбор метрик через MetricsPublisher
    - Запись логов в файлы сессий
    - Вывод в терминал

    USAGE:
    ```python
    telemetry = TelemetryCollector(
        event_bus=event_bus,
        storage_dir=Path('data'),
        log_dir=Path('logs')
    )
    await telemetry.initialize()
    ```
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        storage_dir: Path = None,
        log_dir: Path = None,
        enable_terminal: bool = True,
        enable_session_logs: bool = True,
        enable_metrics: bool = True
    ):
        """
        Инициализация телеметрии.

        ARGS:
        - event_bus: шина событий
        - storage_dir: директория для данных (метрики)
        - log_dir: директория для логов
        - enable_terminal: включить вывод в консоль
        - enable_session_logs: включить запись сессий
        - enable_metrics: включить сбор метрик
        """
        super().__init__(event_bus, component_name="TelemetryCollector")

        self.storage_dir = storage_dir or Path('data')
        self.log_dir = log_dir or Path('logs')

        # Обработчики
        self.terminal_handler: Optional[TerminalLogHandler] = None
        self.session_handler: Optional[SessionLogHandler] = None
        self.metrics_publisher: Optional[MetricsPublisher] = None

        # Флаги
        self._enable_terminal = enable_terminal
        self._enable_session_logs = enable_session_logs
        self._enable_metrics = enable_metrics

    async def initialize(self) -> None:
        """
        Инициализация телеметрии.

        Создаёт и подписывает обработчики:
        1. TerminalLogHandler — вывод в консоль
        2. SessionLogHandler — запись в файлы
        3. MetricsPublisher — сбор метрик
        4. LoggingToEventBusHandler — стандартное logging → EventBus
        """
        if self._initialized:
            await self.event_bus_logger.warning("TelemetryCollector уже инициализирован")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return

        # Отключаем стандартный logging (оставляем только TerminalLogHandler с иконками)
        import logging
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        logging.getLogger().setLevel(logging.WARNING)  # Root logger: только WARNING+
        logging.getLogger('core').setLevel(logging.WARNING)  # Наш logger: только WARNING+

        # 1. Terminal handler - только иконки
        if self._enable_terminal:
            from core.config.logging_config import LoggingConfig
            log_config = LoggingConfig()
            console_level = log_config.console.level if hasattr(log_config, 'console') else "INFO"
            self.terminal_handler = TerminalLogHandler(
                self.event_bus,
                min_level=console_level,
                icons_only=True  # ← Только сообщения с иконками
            )
            self.terminal_handler.subscribe()
            await self.event_bus_logger.info(f"TerminalLogHandler инициализирован (уровень: {console_level}, только иконки)")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # 2. Session handler
        if self._enable_session_logs:
            self.session_handler = SessionLogHandler(
                event_bus=self.event_bus,
                base_log_dir=self.log_dir / "sessions"
            )
            await self.event_bus_logger.info("SessionLogHandler инициализирован")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # 3. Metrics
        if self._enable_metrics:
            metrics_storage = FileSystemMetricsStorage(self.storage_dir / "metrics")
            self.metrics_publisher = MetricsPublisher(metrics_storage, self.event_bus)
            
            # Подписка на события метрик
            self._subscribe(EventType.SKILL_EXECUTED, self._on_skill_executed)
            self._subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
            self._subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
            self._subscribe(EventType.SESSION_STARTED, self._on_session_started)
            self._subscribe(EventType.SESSION_COMPLETED, self._on_session_completed)
            
            await self.event_bus_logger.info("MetricsPublisher инициализирован")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # 4. Отключаем LoggingToEventBusHandler (чтобы стандартный logging не шёл в EventBus и консоль)
        # self.event_bridge_handler = LoggingToEventBusHandler(self.event_bus)
        # self.event_bridge_handler.install()
        # await self.event_bus_logger.info("LoggingToEventBusHandler инициализирован")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        await super().initialize()

    async def _on_skill_executed(self, event):
        """Обработка выполнения навыка."""
        data = event.data
        if not data.get('capability'):
            return

        success = 1.0 if data.get('success', False) else 0.0
        
        await self.metrics_publisher.gauge(
            name='success',
            value=success,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            version=data.get('version'),
            timestamp=event.timestamp,
            publish_event=False
        )

        execution_time = data.get('execution_time_ms')
        if execution_time:
            await self.metrics_publisher.histogram(
                name='execution_time_ms',
                value=float(execution_time),
                agent_id=data.get('agent_id', 'unknown'),
                capability=data.get('capability'),
                session_id=data.get('session_id'),
                correlation_id=event.correlation_id,
                version=data.get('version'),
                timestamp=event.timestamp,
                publish_event=False
            )

        tokens = data.get('tokens_used')
        if tokens:
            await self.metrics_publisher.counter(
                name='tokens_used',
                value=float(tokens),
                agent_id=data.get('agent_id', 'unknown'),
                capability=data.get('capability'),
                session_id=data.get('session_id'),
                correlation_id=event.correlation_id,
                version=data.get('version'),
                timestamp=event.timestamp,
                publish_event=False
            )

    async def _on_capability_selected(self, event):
        """Обработка выбора способности."""
        data = event.data
        if not data.get('capability'):
            return

        await self.metrics_publisher.counter(
            name='selection_count',
            value=1.0,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            version=data.get('version'),
            timestamp=event.timestamp,
            publish_event=False
        )

    async def _on_error_occurred(self, event):
        """Обработка ошибки."""
        data = event.data
        if not data.get('capability'):
            return

        error_type = data.get('error_type', 'unknown')
        
        await self.metrics_publisher.gauge(
            name='success',
            value=0.0,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            tags={'error': error_type},
            publish_event=False
        )

        await self.metrics_publisher.counter(
            name='error_count',
            value=1.0,
            agent_id=data.get('agent_id', 'unknown'),
            capability=data.get('capability'),
            session_id=data.get('session_id'),
            correlation_id=event.correlation_id,
            tags={'error': error_type},
            publish_event=False
        )

    async def _on_session_started(self, event):
        """Обработка начала сессии."""
        data = event.data
        await self.event_bus_logger.debug(
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            "Сессия начата: session_id=%s, goal=%s",
            data.get('session_id'), data.get('goal')
        )

    async def _on_session_completed(self, event):
        """Обработка завершения сессии."""
        data = event.data
        steps = data.get('steps_completed', 0)
        
        await self.metrics_publisher.gauge(
            name='session_steps_completed',
            value=float(steps),
            agent_id=data.get('agent_id', 'unknown'),
            session_id=data.get('session_id'),
            tags={'final_status': data.get('final_status', 'unknown')},
            publish_event=False
        )

    async def shutdown(self) -> None:
        """Завершение телеметрии."""
        if self.session_handler:
            await self.session_handler.shutdown()

        await super().shutdown()

    # === Методы доступа для обратной совместимости ===

    def get_metrics_publisher(self) -> Optional[MetricsPublisher]:
        """Получить MetricsPublisher."""
        return self.metrics_publisher

    def get_session_handler(self) -> Optional[SessionLogHandler]:
        """Получить SessionLogHandler."""
        return self.session_handler

    def get_terminal_handler(self) -> Optional[TerminalLogHandler]:
        """Получить TerminalLogHandler."""
        return self.terminal_handler


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_telemetry: Optional[TelemetryCollector] = None


def get_telemetry() -> TelemetryCollector:
    """Получить глобальный TelemetryCollector."""
    global _telemetry
    if _telemetry is None:
        raise RuntimeError(
            "TelemetryCollector не инициализирован. "
            "Вызовите await init_telemetry() сначала."
        )
    return _telemetry


async def init_telemetry(
    event_bus: UnifiedEventBus,
    storage_dir: Path = None,
    log_dir: Path = None,
    **kwargs
) -> TelemetryCollector:
    """
    Инициализация глобального TelemetryCollector.

    ARGS:
    - event_bus: шина событий
    - storage_dir: директория для данных
    - log_dir: директория для логов
    - **kwargs: дополнительные параметры для TelemetryCollector

    RETURNS:
    - TelemetryCollector: инициализированный сборщик
    """
    global _telemetry
    _telemetry = TelemetryCollector(
        event_bus=event_bus,
        storage_dir=storage_dir,
        log_dir=log_dir,
        **kwargs
    )
    await _telemetry.initialize()
    return _telemetry


async def shutdown_telemetry():
    """Завершение работы телеметрии."""
    global _telemetry
    if _telemetry:
        await _telemetry.shutdown()
        _telemetry = None


__all__ = [
    'TelemetryCollector',
    'get_telemetry',
    'init_telemetry',
    'shutdown_telemetry',
]

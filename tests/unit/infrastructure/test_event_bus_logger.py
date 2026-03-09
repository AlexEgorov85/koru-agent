"""
Тесты для EventBusLogger.

TESTS:
- test_info_sync: Синхронное INFO логирование
- test_debug_sync: Синхронное DEBUG логирование
- test_warning_sync: Синхронное WARNING логирование
- test_error_sync: Синхронное ERROR логирование
- test_fifo_order: FIFO порядок событий
- test_auto_mode_switching: Автоматическое переключение синхронный/асинхронный режим
- test_initializing_state: Логирование в состоянии инициализации
- test_ready_state: Логирование в состоянии READY
- test_fallback_on_error: Fallback при ошибке stdout
"""
import pytest
import asyncio
from io import StringIO
from unittest.mock import patch, MagicMock

from core.infrastructure.event_bus.unified_event_bus import (
    create_event_bus,
    EventType,
)
from core.infrastructure.logging.logger import EventBusLogger, LoggerInitializationState


@pytest.fixture
async def event_bus():
    """Фикстура: новая шина для каждого теста."""
    bus = create_event_bus()
    yield bus
    await bus.shutdown(timeout=5.0)


@pytest.fixture
def logger(event_bus):
    """Фикстура: логгер для тестов."""
    return EventBusLogger(
        event_bus,
        session_id="test_session",
        agent_id="test_agent",
        component="TestLogger"
    )


@pytest.fixture
def logger_with_callback(event_bus):
    """Фикстура: логгер с callback для получения состояния."""
    state = LoggerInitializationState.INITIALIZING
    
    def get_state():
        return state
    
    logger = EventBusLogger(
        event_bus,
        session_id="test_session",
        agent_id="test_agent",
        component="TestLoggerWithCallback",
        get_init_state_callback=get_state
    )
    logger._test_set_state = lambda s: nonlocal_assign(state, s)
    logger._test_state = state
    return logger, lambda s: nonlocal_assign(state, s)


def nonlocal_assign(var, value):
    """Helper for mutable closure."""
    pass


class TestEventBusLoggerSync:
    """Тесты синхронных методов EventBusLogger (_sync методы).
    
    _sync методы теперь выводят логи напрямую в stdout/stderr,
    а не публикуют через EventBus. Это нужно для гарантии порядка
    во время инициализации компонентов.
    """

    @pytest.mark.asyncio
    async def test_info_sync_outputs_to_stdout(self, event_bus, logger, capsys):
        """Синхронное INFO логирование выводит в stdout."""
        # Синхронное логирование (выводит напрямую в stdout)
        logger.info_sync("Test info message")
        
        captured = capsys.readouterr()
        # Проверяем что сообщение выведено в stdout
        assert "[INFO]" in captured.out
        assert "Test info message" in captured.out
        assert "[TestLogger]" in captured.out

    @pytest.mark.asyncio
    async def test_debug_sync_outputs_to_stdout(self, event_bus, logger, capsys):
        """Синхронное DEBUG логирование выводит в stdout."""
        logger.debug_sync("Test debug message")
        
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out
        assert "Test debug message" in captured.out

    @pytest.mark.asyncio
    async def test_warning_sync_outputs_to_stdout(self, event_bus, logger, capsys):
        """Синхронное WARNING логирование выводит в stdout."""
        logger.warning_sync("Test warning message")
        
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out
        assert "Test warning message" in captured.out

    @pytest.mark.asyncio
    async def test_error_sync_outputs_to_stderr(self, event_bus, logger, capsys):
        """Синхронное ERROR логирование выводит в stderr."""
        logger.error_sync("Test error message")
        
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.err
        assert "Test error message" in captured.err

    @pytest.mark.asyncio
    async def test_info_sync_with_args(self, event_bus, logger, capsys):
        """Синхронное логирование с аргументами."""
        logger.info_sync("Test %s message", "info")
        
        captured = capsys.readouterr()
        assert "Test info message" in captured.out

    @pytest.mark.asyncio
    async def test_info_sync_with_extra_data_ignored(self, event_bus, logger, capsys):
        """Синхронное логирование игнорирует extra данные (упрощённый вывод)."""
        logger.info_sync("Test message", custom_field="custom_value")
        
        captured = capsys.readouterr()
        # Extra данные не выводятся в синхронном режиме
        assert "Test message" in captured.out
        assert "custom_value" not in captured.out


class TestEventBusLoggerAsync:
    """Тесты асинхронных методов EventBusLogger."""

    @pytest.mark.asyncio
    async def test_info_async(self, event_bus, logger):
        """Асинхронное INFO логирование."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Переключаем логгер в режим READY для асинхронной публикации
        logger._set_ready()

        # Асинхронное логирование
        await logger.info("Test async info message")
        await asyncio.sleep(0.05)

        assert len(events) == 1
        assert events[0].data["message"] == "Test async info message"
        assert events[0].data["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_auto_mode_initializing(self, event_bus, logger, capsys):
        """Автоматический выбор режима: в INITIALIZING выводит синхронно."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Логгер по умолчанию в состоянии NOT_INITIALIZED (как во время инициализации)
        # Не переключаем в READY

        # Асинхронный вызов, но должен пойти синхронно
        await logger.info("Initializing message")
        await asyncio.sleep(0.05)

        # Событие не опубликовано
        assert len(events) == 0
        
        # Но выведено в stdout
        captured = capsys.readouterr()
        assert "Initializing message" in captured.out

    @pytest.mark.asyncio
    async def test_auto_mode_ready(self, event_bus, logger):
        """Автоматический выбор режима: в READY публикует асинхронно."""
        events = []

        def handler(e):
            events.append(e)

        event_bus.subscribe(EventType.LOG_INFO, handler)

        # Переключаем в READY
        logger._set_ready()

        # Асинхронный вызов
        await logger.info("Ready message")
        await asyncio.sleep(0.05)

        # Событие опубликовано
        assert len(events) == 1
        assert events[0].data["message"] == "Ready message"


class TestEventBusLoggerAutoModeSwitching:
    """Тесты автоматического переключения режимов логирования."""

    @pytest.mark.asyncio
    async def test_initializing_state_sync_output(self, event_bus):
        """Логирование в состоянии INITIALIZING выводит синхронно."""
        events = []
        
        def handler(e):
            events.append(e)
        
        event_bus.subscribe(EventType.LOG_INFO, handler)
        
        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)
        
        # Логгер в состоянии INITIALIZING
        logger = EventBusLogger(
            event_bus,
            session_id="test_session",
            agent_id="test_agent",
            component="TestInitializing"
        )
        logger._set_initializing()
        
        # Лог должен пойти синхронно (не через EventBus)
        await logger.info("Initializing message")
        await asyncio.sleep(0.05)
        
        # Событие не должно быть опубликовано (синхронный вывод)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_ready_state_async_output(self, event_bus):
        """Логирование в состоянии READY публикует асинхронно."""
        events = []
        
        def handler(e):
            events.append(e)
        
        event_bus.subscribe(EventType.LOG_INFO, handler)
        
        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)
        
        # Логгер в состоянии READY
        logger = EventBusLogger(
            event_bus,
            session_id="test_session",
            agent_id="test_agent",
            component="TestReady"
        )
        logger._set_ready()
        
        # Лог должен пойти асинхронно
        await logger.info("Ready message")
        await asyncio.sleep(0.05)
        
        # Событие должно быть опубликовано
        assert len(events) == 1
        assert events[0].data["message"] == "Ready message"

    @pytest.mark.asyncio
    async def test_callback_state_switching(self, event_bus):
        """Переключение режима через callback."""
        events = []
        
        def handler(e):
            events.append(e)
        
        event_bus.subscribe(EventType.LOG_INFO, handler)
        
        # Создадим worker
        await event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={},
            session_id="test_session"
        )
        await asyncio.sleep(0.01)
        
        # Создаём изменяемое состояние
        current_state = LoggerInitializationState.INITIALIZING
        
        def get_state():
            return current_state
        
        logger = EventBusLogger(
            event_bus,
            session_id="test_session",
            agent_id="test_agent",
            component="TestCallback",
            get_init_state_callback=get_state
        )
        
        # В состоянии INITIALIZING — синхронный вывод
        await logger.info("Init message")
        await asyncio.sleep(0.05)
        assert len(events) == 0
        
        # Переключаем в READY
        current_state = LoggerInitializationState.READY
        
        # Теперь асинхронный вывод
        await logger.info("Ready message")
        await asyncio.sleep(0.05)
        assert len(events) == 1
        assert events[0].data["message"] == "Ready message"

    @pytest.mark.asyncio
    async def test_write_sync_format(self, event_bus, capsys):
        """Проверка формата синхронного вывода."""
        logger = EventBusLogger(
            event_bus,
            session_id="test_session",
            agent_id="test_agent",
            component="TestFormat"
        )
        
        # Синхронная запись
        logger._write_sync("Test message", "INFO")
        
        captured = capsys.readouterr()
        # Проверяем что сообщение содержит компоненты формата
        assert "[INFO]" in captured.out
        assert "[TestFormat]" in captured.out
        assert "Test message" in captured.out

    @pytest.mark.asyncio
    async def test_error_level_to_stderr(self, event_bus, capsys):
        """ERROR сообщения выводятся в stderr."""
        logger = EventBusLogger(
            event_bus,
            session_id="test_session",
            agent_id="test_agent",
            component="TestError"
        )
        
        # Синхронная запись ERROR
        logger._write_sync("Error message", "ERROR")
        
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.err
        assert "Error message" in captured.err

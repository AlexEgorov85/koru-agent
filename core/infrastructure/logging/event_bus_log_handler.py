"""
EventBusLogHandler - универсальный обработчик событий логирования.

ОСОБЕННОСТИ:
- Перехватывает события LOG_INFO, LOG_DEBUG, LOG_WARNING, LOG_ERROR из EventBus
- Форматирует сообщения структурированно с цветами и иконками
- Выводит в терминал через стандартный logging
- Работает централизованно для всех компонентов системы

АРХИТЕКТУРА:
- Компоненты публикуют события в EventBus (LOG_INFO, LOG_DEBUG, etc.)
- Этот обработчик подписывается на события логирования
- Форматирует и выводит сообщения в терминал
- Дополнительно публикует в LogManager для сохранения в файлы
"""
import asyncio
import logging
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass

from core.infrastructure.event_bus.event_bus import Event, EventType


class LogMessageType(Enum):
    """Типы сообщений для структурированного логирования."""
    INFO = "log.info"
    DEBUG = "log.debug"
    WARNING = "log.warning"
    ERROR = "log.error"


class LogColors:
    """ANSI цвета для форматирования вывода в терминал."""
    # Основные цвета
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Цвета по уровням
    INFO = "\033[36m"       # Cyan
    DEBUG = "\033[37m"      # White
    WARNING = "\033[33m"    # Yellow
    ERROR = "\033[31m"      # Red
    CRITICAL = "\033[35m"   # Magenta
    SUCCESS = "\033[32m"    # Green
    
    # Цвета для компонентов
    LLM = "\033[34m"        # Blue
    REASONING = "\033[38;5;39m"   # Light blue
    DECISION = "\033[38;5;208m"   # Orange
    CAPABILITY = "\033[38;5;148m" # Light green
    AGENT = "\033[38;5;27m"       # Dark blue
    
    # Фоны
    BG_HEADER = "\033[44m"   # Blue background
    BG_ERROR = "\033[41m"    # Red background
    BG_SUCCESS = "\033[42m"  # Green background
    BG_WARNING = "\033[43m"  # Yellow background


@dataclass
class StructuredLogMessage:
    """Структурированное сообщение лога."""
    level: str
    message: str
    timestamp: str
    source: str = ""
    session_id: str = "unknown"
    agent_id: str = "unknown"
    component: str = "unknown"
    phase: str = ""
    goal: str = ""
    extra_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}


class EventBusLogFormatter:
    """
    Форматировщик сообщений логирования из EventBus.
    
    Создаёт структурированный вывод с:
    - Цветами в зависимости от уровня
    - Иконками для типов сообщений
    - Разделителями между сообщениями
    - Дополнительными данными в структурированном виде
    """
    
    # Иконки для различных типов событий
    TYPE_ICONS = {
        # LLM события
        "llm.call.start": "🔄",
        "llm.call.progress": "⏳",
        "llm.call.success": "✅",
        "llm.call.retry": "🔁",
        "llm.call.timeout": "⏱️",
        "llm.call.error": "❌",
        
        # Рассуждение
        "reasoning.start": "🧠",
        "reasoning.complete": "💡",
        "reasoning.error": "🔥",
        
        # Контекст
        "context.analysis": "📊",
        "capability.register": "🔧",
        
        # Решения
        "decision.made": "🎯",
        "decision.validation": "✔️",
        
        # Агент
        "agent.start": "🤖",
        "agent.complete": "🏁",
        "agent.error": "💥",
        
        # По умолчанию для уровней логирования
        "log.info": "ℹ️",
        "log.debug": "🔍",
        "log.warning": "⚠️",
        "log.error": "❌",
    }
    
    # Цвета для типов событий
    TYPE_COLORS = {
        "llm.call.start": LogColors.LLM,
        "llm.call.progress": LogColors.LLM,
        "llm.call.success": LogColors.SUCCESS,
        "llm.call.retry": LogColors.WARNING,
        "llm.call.timeout": LogColors.ERROR,
        "llm.call.error": LogColors.ERROR,
        
        "reasoning.start": LogColors.REASONING,
        "reasoning.complete": LogColors.SUCCESS,
        "reasoning.error": LogColors.ERROR,
        
        "decision.made": LogColors.DECISION,
        "decision.validation": LogColors.DECISION,
        
        "capability.register": LogColors.CAPABILITY,
        
        "agent.start": LogColors.AGENT,
        "agent.complete": LogColors.SUCCESS,
        "agent.error": LogColors.ERROR,
    }
    
    def __init__(self, use_colors: bool = True, show_debug: bool = False):
        """
        Инициализация форматировщика.
        
        ARGS:
            use_colors: использовать ANSI цвета
            show_debug: показывать DEBUG сообщения
        """
        self.use_colors = use_colors
        self.show_debug = show_debug
        self._last_message_type = None
        self._message_count = 0
    
    def format(self, event: Event) -> Optional[str]:
        """
        Форматирует событие в строку для вывода.
        
        ARGS:
            event: событие из EventBus
            
        RETURNS:
            отформатированная строка или None если сообщение не должно выводиться
        """
        data = event.data or {}
        
        # Получаем тип сообщения
        message_type = data.get("type", event.event_type)
        
        # Пропускаем DEBUG если не включены
        if not self.show_debug and message_type == "log.debug":
            return None
        
        # Парсим данные события
        log_msg = self._parse_event_data(event, data)
        
        # Формируем вывод
        return self._format_message(log_msg, message_type)
    
    def _parse_event_data(self, event: Event, data: Dict[str, Any]) -> StructuredLogMessage:
        """Извлекает данные из события."""
        return StructuredLogMessage(
            level=data.get("level", "INFO"),
            message=data.get("message", str(data)),
            timestamp=data.get("timestamp", event.timestamp.isoformat()),
            source=data.get("source", event.source),
            session_id=data.get("session_id", "unknown"),
            agent_id=data.get("agent_id", "unknown"),
            component=data.get("component", "unknown"),
            phase=data.get("phase", ""),
            goal=data.get("goal", ""),
            extra_data={k: v for k, v in data.items() 
                       if k not in ["level", "message", "timestamp", "source", 
                                   "session_id", "agent_id", "component", "phase", "goal"]}
        )
    
    def _format_message(self, msg: StructuredLogMessage, message_type: str) -> str:
        """
        Форматирует структурированное сообщение.
        
        ФОРМАТ ВЫВОДА:
        ═══════════════════════════════════════════════════════════
        [ℹ️ log.info] Компонент/Фаза │ Сообщение
          └─ session: xxx | agent: yyy
          └─ extra_key: value
        ═══════════════════════════════════════════════════════════
        """
        c = LogColors
        
        # Определяем цвет и иконку
        icon = self.TYPE_ICONS.get(message_type, "•")
        color = self.TYPE_COLORS.get(message_type, self._get_level_color(msg.level))
        
        # Формируем время
        try:
            ts = datetime.fromisoformat(msg.timestamp.replace('Z', '+00:00'))
            time_str = ts.strftime("%H:%M:%S")
        except:
            time_str = datetime.now().strftime("%H:%M:%S")
        
        lines = []
        
        # Разделитель (не перед первым сообщением)
        if self._message_count > 0:
            lines.append(f"{c.DIM}{'─' * 65}{c.RESET}")
        
        # Заголовок с типом сообщения
        if self.use_colors:
            header = f"{color}{c.BOLD}[{icon} {message_type}]{c.RESET}"
        else:
            header = f"[{icon} {message_type}]"
        
        lines.append(f"{header}")
        
        # Основное сообщение
        lines.append(f"  {c.DIM}└─{c.RESET} {msg.message}")
        
        # Контекст (session, agent, component)
        context_parts = []
        if msg.session_id and msg.session_id != "unknown":
            context_parts.append(f"session={msg.session_id}")
        if msg.agent_id and msg.agent_id != "unknown":
            context_parts.append(f"agent={msg.agent_id}")
        if msg.component and msg.component != "unknown":
            context_parts.append(f"component={msg.component}")
        
        if context_parts:
            lines.append(f"  {c.DIM}└─{c.RESET} {c.DIM}{' | '.join(context_parts)}{c.RESET}")
        
        # Дополнительные данные
        if msg.extra_data:
            for key, value in msg.extra_data.items():
                str_value = str(value)
                # Ограничиваем длину
                if len(str_value) > 150:
                    str_value = str_value[:147] + "..."
                lines.append(f"  {c.DIM}└─{c.RESET} {c.DIM}{key}:{c.RESET} {str_value}")
        
        self._message_count += 1
        self._last_message_type = message_type
        
        return "\n".join(lines)
    
    def _get_level_color(self, level: str) -> str:
        """Получает цвет для уровня логирования."""
        level_colors = {
            "INFO": LogColors.INFO,
            "DEBUG": LogColors.DEBUG,
            "WARNING": LogColors.WARNING,
            "ERROR": LogColors.ERROR,
            "CRITICAL": LogColors.CRITICAL,
        }
        return level_colors.get(level.upper(), LogColors.RESET)


class EventBusLogHandler:
    """
    Обработчик событий логирования из EventBus.
    
    ПОДПИСЫВАЕТСЯ НА:
    - LOG_INFO
    - LOG_DEBUG
    - LOG_WARNING
    - LOG_ERROR
    
    ФУНКЦИИ:
    - Форматирование сообщений с цветами
    - Вывод в терминал через logging
    - Опциональная отправка в LogManager
    """
    
    def __init__(
        self,
        use_colors: bool = True,
        show_debug: bool = False,
        logger_name: str = "EventBusLog"
    ):
        """
        Инициализация обработчика.
        
        ARGS:
            use_colors: использовать ANSI цвета
            show_debug: показывать DEBUG сообщения
            logger_name: имя логгера для вывода
        """
        self.formatter = EventBusLogFormatter(
            use_colors=use_colors,
            show_debug=show_debug
        )
        self.logger = logging.getLogger(logger_name)
        self._enabled = True
    
    def enable(self):
        """Включить вывод логов."""
        self._enabled = True
    
    def disable(self):
        """Выключить вывод логов."""
        self._enabled = False
    
    async def handle_log_event(self, event: Event) -> None:
        """
        Обработчик событий логирования.
        
        ARGS:
            event: событие из EventBus
        """
        if not self._enabled:
            return
        
        # Форматируем сообщение
        formatted = self.formatter.format(event)
        if not formatted:
            return
        
        # Определяем уровень логирования для вывода
        event_type = event.event_type
        if event_type in ["log.error"]:
            self.logger.error(f"\n{formatted}")
        elif event_type in ["log.warning"]:
            self.logger.warning(f"\n{formatted}")
        elif event_type in ["log.debug"]:
            self.logger.debug(f"\n{formatted}")
        else:
            self.logger.info(f"\n{formatted}")
    
    def subscribe(self, event_bus):
        """
        Подписаться на события логирования в EventBus.
        
        ARGS:
            event_bus: экземпляр EventBus
        """
        event_bus.subscribe(EventType.LOG_INFO, self.handle_log_event)
        event_bus.subscribe(EventType.LOG_DEBUG, self.handle_log_event)
        event_bus.subscribe(EventType.LOG_WARNING, self.handle_log_event)
        event_bus.subscribe(EventType.LOG_ERROR, self.handle_log_event)
    
    def unsubscribe(self, event_bus):
        """
        Отписаться от событий логирования.

        ARGS:
            event_bus: экземпляр EventBus
        """
        event_bus.unsubscribe(EventType.LOG_INFO, self.handle_log_event)
        event_bus.unsubscribe(EventType.LOG_DEBUG, self.handle_log_event)
        event_bus.unsubscribe(EventType.LOG_WARNING, self.handle_log_event)
        event_bus.unsubscribe(EventType.LOG_ERROR, self.handle_log_event)

    async def info(self, message: str, **extra_data):
        """Опубликовать INFO сообщение в EventBus."""
        await log_info(self.event_bus, message, source="main", **extra_data)

    async def debug(self, message: str, **extra_data):
        """Опубликовать DEBUG сообщение в EventBus."""
        await log_debug(self.event_bus, message, source="main", **extra_data)

    async def warning(self, message: str, **extra_data):
        """Опубликовать WARNING сообщение в EventBus."""
        await log_warning(self.event_bus, message, source="main", **extra_data)

    async def error(self, message: str, **extra_data):
        """Опубликовать ERROR сообщение в EventBus."""
        await log_error(self.event_bus, message, source="main", **extra_data)

    @property
    def event_bus(self):
        """Получить шину событий."""
        from core.infrastructure.event_bus.event_bus import get_event_bus
        return get_event_bus()


def setup_event_bus_logging(
    event_bus,
    use_colors: bool = True,
    show_debug: bool = False,
    logger_name: str = "EventBusLog"
) -> EventBusLogHandler:
    """
    Настройка логирования через EventBus.
    
    USAGE:
        from core.infrastructure.logging.event_bus_log_handler import setup_event_bus_logging
        
        # При инициализации приложения
        event_bus = get_event_bus()
        log_handler = setup_event_bus_logging(event_bus, use_colors=True, show_debug=False)
    
    ARGS:
        event_bus: экземпляр EventBus
        use_colors: использовать ANSI цвета
        show_debug: показывать DEBUG сообщения
        logger_name: имя логгера
        
    RETURNS:
        EventBusLogHandler для управления
    """
    handler = EventBusLogHandler(
        use_colors=use_colors,
        show_debug=show_debug,
        logger_name=logger_name
    )
    handler.subscribe(event_bus)
    return handler


# =============================================================================
# HELPER-ФУНКЦИИ ДЛЯ КОМПОНЕНТОВ
# =============================================================================

async def log_info(
    event_bus,
    message: str,
    source: str = "",
    correlation_id: str = "",
    **extra_data
):
    """
    Опубликовать INFO сообщение в EventBus.
    
    USAGE:
        await log_info(event_bus, "Запуск процесса", source="my_component", session_id="123")
    """
    data = {"message": message, "level": "INFO", **extra_data}
    await event_bus.publish(EventType.LOG_INFO, data=data, source=source, correlation_id=correlation_id)


async def log_debug(
    event_bus,
    message: str,
    source: str = "",
    correlation_id: str = "",
    **extra_data
):
    """
    Опубликовать DEBUG сообщение в EventBus.
    
    USAGE:
        await log_debug(event_bus, "Детали процесса", source="my_component")
    """
    data = {"message": message, "level": "DEBUG", **extra_data}
    await event_bus.publish(EventType.LOG_DEBUG, data=data, source=source, correlation_id=correlation_id)


async def log_warning(
    event_bus,
    message: str,
    source: str = "",
    correlation_id: str = "",
    **extra_data
):
    """
    Опубликовать WARNING сообщение в EventBus.
    
    USAGE:
        await log_warning(event_bus, "Предупреждение", source="my_component")
    """
    data = {"message": message, "level": "WARNING", **extra_data}
    await event_bus.publish(EventType.LOG_WARNING, data=data, source=source, correlation_id=correlation_id)


async def log_error(
    event_bus,
    message: str,
    source: str = "",
    correlation_id: str = "",
    **extra_data
):
    """
    Опубликовать ERROR сообщение в EventBus.
    
    USAGE:
        await log_error(event_bus, "Ошибка", source="my_component", error_type="timeout")
    """
    data = {"message": message, "level": "ERROR", **extra_data}
    await event_bus.publish(EventType.LOG_ERROR, data=data, source=source, correlation_id=correlation_id)


class EventBusLogger:
    """
    Helper-класс для логирования через EventBus.
    
    USAGE:
        # В компоненте
        class MyComponent:
            def __init__(self, event_bus):
                self.logger = EventBusLogger(event_bus, source="my_component")
            
            async def do_something(self):
                await self.logger.info("Запуск")
                await self.logger.debug("Детали", extra={"key": "value"})
    
    ТАКЖЕ ПОДДЕРЖИВАЕТСЯ СИНХРОННЫЙ ВЫЗОВ (для main.py):
        log_handler.info("Сообщение")  # Автоматически публикует в EventBus
    """
    
    def __init__(self, event_bus, source: str = "", correlation_id: str = ""):
        self.event_bus = event_bus
        self.source = source
        self.correlation_id = correlation_id
    
    async def info(self, message: str, **extra_data):
        await log_info(self.event_bus, message, source=self.source, correlation_id=self.correlation_id, **extra_data)
    
    async def debug(self, message: str, **extra_data):
        await log_debug(self.event_bus, message, source=self.source, correlation_id=self.correlation_id, **extra_data)
    
    async def warning(self, message: str, **extra_data):
        await log_warning(self.event_bus, message, source=self.source, correlation_id=self.correlation_id, **extra_data)
    
    async def error(self, message: str, **extra_data):
        await log_error(self.event_bus, message, source=self.source, correlation_id=self.correlation_id, **extra_data)
    
    # Синхронные версии (для использования в main.py до полной асинхронности)
    def info_sync(self, message: str, **extra_data):
        """Синхронная версия info (публикует в EventBus без await)."""
        data = {"message": message, "level": "INFO", **extra_data}
        asyncio.create_task(self.event_bus.publish(EventType.LOG_INFO, data=data, source=self.source, correlation_id=self.correlation_id))
    
    def debug_sync(self, message: str, **extra_data):
        """Синхронная версия debug."""
        data = {"message": message, "level": "DEBUG", **extra_data}
        asyncio.create_task(self.event_bus.publish(EventType.LOG_DEBUG, data=data, source=self.source, correlation_id=self.correlation_id))
    
    def warning_sync(self, message: str, **extra_data):
        """Синхронная версия warning."""
        data = {"message": message, "level": "WARNING", **extra_data}
        asyncio.create_task(self.event_bus.publish(EventType.LOG_WARNING, data=data, source=self.source, correlation_id=self.correlation_id))
    
    def error_sync(self, message: str, **extra_data):
        """Синхронная версия error."""
        data = {"message": message, "level": "ERROR", **extra_data}
        asyncio.create_task(self.event_bus.publish(EventType.LOG_ERROR, data=data, source=self.source, correlation_id=self.correlation_id))

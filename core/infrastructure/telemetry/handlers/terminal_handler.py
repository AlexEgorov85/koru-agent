"""
Terminal Log Handler — вывод логов в консоль.

FEATURES:
- Умное форматирование с иконками
- Фильтрация шума
- Показывает только meaningful execution trace
"""
import logging
from typing import Optional

from core.infrastructure.event_bus.unified_event_bus import Event, EventType, UnifiedEventBus

logger = logging.getLogger(__name__)


class TerminalLogFormatter:
    """
    Smart formatter for terminal logs.

    Converts noisy infrastructure logs into clean agent execution trace.
    """

    ICONS = {
        "stage": "🧠",
        "tool": "🔧",
        "result": "📊",
        "llm": "🤖",
        "error": "❌",
        "info": "ℹ️",
    }

    KEYWORDS = {
        "stage": ("planning", "step", "phase", "stage", "decision", "thinking"),
        "tool": ("tool", "capability", "executing"),
        "result": ("result", "response", "output", "completed", "finished"),
        "llm": ("llm", "completion", "prompt", "generation"),
        "error": ("ошибка", "error:", "failed", "exception", "не удалось"),
    }

    def __init__(self):
        self._last_message: Optional[str] = None

    def format(self, event: Event, level: str = "INFO") -> Optional[str]:
        """
        Форматирование события для терминала.

        ARGS:
        - event: событие
        - level: уровень лога

        RETURNS:
        - Отформатированная строка или None (если шум)
        """
        data = event.data or {}
        message = data.get("message")

        if not message or message == self._last_message:
            return None

        self._last_message = message

        # Классификация
        component = data.get("component", "").lower()
        msg_type = self._classify(component, message, level)

        icon = self.ICONS.get(msg_type, "")

        # Форматирование по типу
        if msg_type == "stage":
            return f"\n{icon} {message}"
        elif msg_type == "tool":
            return f"{icon} TOOL → {message}"
        elif msg_type == "result":
            return f"{icon} RESULT → {message}"
        elif msg_type == "llm":
            return f"{icon} LLM → {message}"
        elif msg_type == "error":
            return f"\n{icon} ERROR → {message}"
        else:
            return message

    def _classify(self, component: str, message: str, level: str) -> str:
        """Классификация сообщения по типу."""
        msg_lower = message.lower()

        # По уровню
        if level in ("ERROR", "CRITICAL"):
            return "error"

        # По ключевым словам
        for msg_type, keywords in self.KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                return msg_type

        # По компоненту
        if "llm" in component or "provider" in component:
            return "llm"
        if "tool" in component or "skill" in component:
            return "tool"
        if "pattern" in component or "behavior" in component:
            return "stage"

        return "info"


class TerminalLogHandler:
    """
    Clean terminal log handler.

    Displays only meaningful execution trace.
    """

    def __init__(self, event_bus: UnifiedEventBus, min_level: str = "INFO"):
        self.event_bus = event_bus
        self.formatter = TerminalLogFormatter()
        self._enabled = True
        self._min_level = min_level.upper()
        self._level_priority = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "WARN": 2,
            "ERROR": 3,
            "CRITICAL": 4
        }

    def subscribe(self):
        """Подписка на события логирования."""
        self.event_bus.subscribe(EventType.LOG_INFO, self._on_log)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self._on_log)
        self.event_bus.subscribe(EventType.LOG_WARNING, self._on_log)
        self.event_bus.subscribe(EventType.LOG_ERROR, self._on_error)

    def _should_log(self, level: str) -> bool:
        """Проверка уровня логирования."""
        level_priority = self._level_priority.get(level.upper(), 1)
        min_priority = self._level_priority.get(self._min_level, 1)
        return level_priority >= min_priority

    async def _on_log(self, event: Event):
        """Обработка INFO/DEBUG/WARNING логов."""
        if not self._enabled:
            return

        data = event.data or {}
        level = data.get("level", "INFO")
        
        # Фильтрация по уровню
        if not self._should_log(level):
            return
        
        message = self.formatter.format(event, level)

        if message:
            logger.info(message)

    async def _on_error(self, event: Event):
        """Обработка ERROR логов."""
        if not self._enabled:
            return

        data = event.data or {}
        level = data.get("level", "ERROR")
        message = self.formatter.format(event, level)

        if message:
            logger.error(message)

    def disable(self):
        """Отключить вывод."""
        self._enabled = False

    def enable(self):
        """Включить вывод."""
        self._enabled = True


__all__ = ['TerminalLogFormatter', 'TerminalLogHandler']

"""
Terminal Log Handler — вывод логов в консоль.

FEATURES:
- Умное форматирование с иконками
- Фильтрация шума
- Показывает только meaningful execution trace
"""
import sys
from typing import Optional

from core.infrastructure.event_bus.unified_event_bus import Event, EventType, UnifiedEventBus


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

        noise_patterns = [
            "ComponentFactory",
            "resources: prompts=",
            "preload_for_component",
            "prompt_versions",
            "pattern.prompts",
            "pattern.output_contracts",
            "pattern.input_contracts",
            "Prompt '",
            "content len=",
            "behavior_configs",
            "Получен component_config",
            "Pattern создан",
            "Pattern ещё не инициализирован",
            "Pattern.initialize()",
            "после init",
            "LLMOrchestrator initialized",
            "LLM CALL STARTED",
            "LLM RESULT",
            "LLMResponse",
            "has_parsed",
            "parsed_content",
            "JSON извлечён",
            "JSON распарсен",
            "LLM response:",
            "LLM response received",
            "choices[0]",
            "FULL RESPONSE",
            "Extracting JSON",
            "_generate_impl started",
            "Calling LLM",
            "is_executor_thread",
        ]
        
        for pattern in noise_patterns:
            if pattern in message:
                return None

        self._last_message = message

        component = data.get("component", "").lower()
        msg_type = self._classify(component, message, level)

        icon = self.ICONS.get(msg_type, "")

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

        if level in ("ERROR", "CRITICAL"):
            return "error"

        for msg_type, keywords in self.KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                return msg_type

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

    Displays only meaningful execution trace with icons.
    """

    def __init__(self, event_bus: UnifiedEventBus, min_level: str = "INFO", icons_only: bool = True):
        self.event_bus = event_bus
        self.formatter = TerminalLogFormatter()
        self._enabled = True
        self._min_level = min_level.upper()
        self._icons_only = icons_only
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

        self.event_bus.subscribe(EventType.INFO, self._on_log)
        self.event_bus.subscribe(EventType.DEBUG, self._on_log)
        self.event_bus.subscribe(EventType.WARNING, self._on_log)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)

        self.event_bus.subscribe(EventType.USER_MESSAGE, self._on_user_message)
        self.event_bus.subscribe(EventType.USER_PROGRESS, self._on_user_message)
        self.event_bus.subscribe(EventType.USER_RESULT, self._on_user_message)

        self.event_bus.subscribe(EventType.AGENT_THINKING, self._on_agent_thinking)
        self.event_bus.subscribe(EventType.TOOL_CALL, self._on_tool_call)
        self.event_bus.subscribe(EventType.TOOL_RESULT, self._on_tool_result)

    def _should_log(self, level: str) -> bool:
        """Проверка уровня логирования."""
        level_priority = self._level_priority.get(level.upper(), 1)
        min_priority = self._level_priority.get(self._min_level, 1)
        return level_priority >= min_priority

    def _write(self, text: str):
        """Синхронный вывод в консоль."""
        sys.stdout.buffer.write((text + "\n").encode('utf-8'))
        sys.stdout.flush()

    async def _on_log(self, event: Event):
        """Обработка INFO/DEBUG/WARNING логов."""
        if not self._enabled:
            return

        data = event.data or {}
        
        level = data.get("level")
        if not level:
            if event.event_type in (EventType.INFO, EventType.LOG_INFO):
                level = "INFO"
            elif event.event_type in (EventType.DEBUG, EventType.LOG_DEBUG):
                level = "DEBUG"
            elif event.event_type in (EventType.WARNING, EventType.LOG_WARNING):
                level = "WARNING"
            elif event.event_type in (EventType.ERROR_OCCURRED, EventType.LOG_ERROR):
                level = "ERROR"
            else:
                level = "INFO"

        if not self._should_log(level):
            return

        message = self.formatter.format(event, level)

        if self._icons_only and message and not any(char in message for char in "🧠🔧📊🤖❌ℹ️✅🚀🔄💾⏱️📋🧩"):
            return

        if message:
            self._write(message)

    async def _on_user_message(self, event: Event):
        """Обработка пользовательских сообщений (всегда выводятся)."""
        if not self._enabled:
            return

        data = event.data or {}
        message = data.get("message")
        icon = data.get("icon", "ℹ️")

        if message:
            formatted = f"{icon} {message}"
            self._write(formatted)

    async def _on_agent_thinking(self, event: Event):
        """Обработка рассуждений агента."""
        if not self._enabled:
            return

        data = event.data or {}
        reasoning = data.get("message", "")
        capability_name = data.get("capability_name", "")
        parameters = data.get("parameters", {})
        decision_action = data.get("decision_action", "act")

        if reasoning:
            step_num = data.get("step_number", "?")
            message = f"ШАГ {step_num}: {decision_action} → {capability_name}"
            self._write(f"🧠 {message}")
            self._write(f"   💭 {reasoning}")
            if parameters:
                params_str = str(parameters)[:100] + "..." if len(str(parameters)) > 100 else str(parameters)
                self._write(f"   📋 {params_str}")

    async def _on_tool_call(self, event: Event):
        """Обработка вызова инструмента."""
        if not self._enabled:
            return

        data = event.data or {}
        capability_name = data.get("capability_name", "")
        parameters = data.get("parameters", {})

        if capability_name:
            params_preview = ""
            if parameters:
                params_str = str(parameters)
                params_preview = f" ({params_str[:80]}{'...' if len(params_str) > 80 else ''})"
            self._write(f"🔧 TOOL вызов: {capability_name}{params_preview}")

    async def _on_tool_result(self, event: Event):
        """Обработка результата инструмента."""
        if not self._enabled:
            return

        data = event.data or {}
        capability_name = data.get("capability_name", "")
        status = data.get("status", "completed")
        result = data.get("result", "")
        has_result = data.get("has_result", False)

        icon = "✅" if status == "completed" else "❌"
        self._write(f"{icon} {capability_name}: {status}")
        
        if has_result and result is not None:
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            self._write(f"📊 RESULT → {result_str}")

    async def _on_error(self, event: Event):
        """Обработка ERROR логов."""
        if not self._enabled:
            return

        data = event.data or {}
        level = data.get("level", "ERROR")
        message = self.formatter.format(event, level)

        if message:
            self._write(message)

    def disable(self):
        """Отключить вывод."""
        self._enabled = False

    def enable(self):
        """Включить вывод."""
        self._enabled = True


__all__ = ['TerminalLogFormatter', 'TerminalLogHandler']

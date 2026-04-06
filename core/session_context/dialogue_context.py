"""
Контекст диалога (DialogueHistory).
НАЗНАЧЕНИЕ:
- Хранение истории вопросов пользователя и ответов агента
- Форматирование истории для вставки в промпт
- Контроль размера истории (последние N раундов)

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
1. Смысловая нагрузка — хранит смысл, а не технические логи
2. Чистота промпта — без stack traces и ошибок валидации
3. Контроль размера — лимит по раундам для экономии токенов
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DialogueMessage:
    """
    Сообщение в диалоге.

    АТРИБУТЫ:
    - role: "user" или "assistant"
    - content: текст сообщения
    - tools_used: список инструментов, использованных в ответе (для assistant)
    """
    role: str  # "user" или "assistant"
    content: str
    tools_used: List[str] = field(default_factory=list)


class DialogueHistory:
    """
    История диалога для сохранения контекста между запросами.

    ПРИНЦИПЫ:
    1. Хранит только пары вопрос-ответ (не технические шаги)
    2. Автоматическая обрезка по достижении лимита
    3. Форматирование для промпта с информацией об инструментах

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    history = DialogueHistory(max_rounds=10)
    history.add_user_message("Какие книги есть у Пушкина?")
    history.add_assistant_message("У Пушкина есть 'Евгений Онегин' и 'Капитанская дочка'")
    print(history.format_for_prompt())
    """

    def __init__(self, max_rounds: int = 10):
        """
        Инициализация истории диалога.

        ПАРАМЕТРЫ:
        - max_rounds: максимальное количество раундов (пара вопрос-ответ)
        """
        self.messages: List[DialogueMessage] = []
        self.max_rounds = max_rounds

    def add_user_message(self, text: str) -> None:
        """
        Добавление сообщения пользователя.

        ПАРАМЕТРЫ:
        - text: текст сообщения
        """
        self.messages.append(DialogueMessage(role="user", content=text))
        self._trim()

    def add_assistant_message(self, text: str, tools_used: Optional[List[str]] = None) -> None:
        """
        Добавление сообщения ассистента.

        ПАРАМЕТРЫ:
        - text: текст ответа
        - tools_used: список использованных инструментов
        """
        self.messages.append(DialogueMessage(
            role="assistant",
            content=text,
            tools_used=tools_used or []
        ))
        self._trim()

    def _trim(self) -> None:
        """
        Удаляет старые сообщения, если превышен лимит.

        Хранит только последние max_rounds * 2 сообщений (пары).
        """
        limit = self.max_rounds * 2
        if len(self.messages) > limit:
            self.messages = self.messages[-limit:]

    def format_for_prompt(self) -> str:
        """
        Формирует читаемый блок истории для вставки в промпт.

        ВОЗВРАЩАЕТ:
        - str: отформатированная история или пустая строка если истории нет
        """
        if not self.messages:
            return ""

        lines = ["=== ПРЕДЫДУЩИЙ КОНТЕКСТ ДИАЛОГА ==="]
        for msg in self.messages:
            if msg.role == "user":
                lines.append(f"User: {msg.content}")
            else:
                # Добавляем информацию об инструментах для понимания контекста
                tools_info = f" [Использовались: {', '.join(msg.tools_used)}]" if msg.tools_used else ""
                lines.append(f"Assistant: {msg.content}{tools_info}")

        lines.append("=== КОНЕЦ КОНТЕКСТА ===")
        return "\n".join(lines)

    def get_last_user_message(self) -> Optional[str]:
        """
        Получить последнее сообщение пользователя.

        ВОЗВРАЩАЕТ:
        - str или None если нет сообщений
        """
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None

    def get_last_assistant_message(self) -> Optional[str]:
        """
        Получить последнее сообщение ассистента.

        ВОЗВРАЩАЕТ:
        - str или None если нет сообщений
        """
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg.content
        return None

    def clear(self) -> None:
        """Очистить историю."""
        self.messages = []

    def count(self) -> int:
        """
        Получить количество сообщений в истории.

        ВОЗВРАЩАЕТ:
        - int: количество сообщений
        """
        return len(self.messages)

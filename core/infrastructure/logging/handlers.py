"""
Обработчики и фильтры для системы логирования.

АРХИТЕКТУРА:
- EventTypeFilter — фильтрует записи в StreamHandler по LogEventType
- Применяется ТОЛЬКО к консольному выводу (файлы пишут всё)
- Работает с extra={"event_type": LogEventType.XXX}

USAGE:
```python
from core.infrastructure.logging.handlers import EventTypeFilter
from core.infrastructure.logging.event_types import LogEventType

filter = EventTypeFilter({
    LogEventType.USER_PROGRESS,
    LogEventType.USER_RESULT,
    LogEventType.USER_MESSAGE,
})
console_handler.addFilter(filter)
```
"""
import logging
from typing import Set

from core.infrastructure.logging.event_types import LogEventType


class EventTypeFilter(logging.Filter):
    """
    Фильтр по типам событий для StreamHandler.

    ПРАВИЛА:
    - Пропускает только записи с event_type в allowed
    - Записи БЕЗ event_type НЕ ПРОПУСКАЕТ (только файлы)
    - Файлы пишут всё — фильтр только для консоли

    ATTRIBUTES:
    - allowed: Set[LogEventType] — разрешённые типы
    """

    def __init__(self, allowed: Set[LogEventType]):
        """
        Инициализация фильтра.

        ARGS:
        - allowed: Набор разрешённых типов событий
        """
        super().__init__()
        self.allowed = allowed

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Проверяет допустимость записи.

        ARGS:
        - record: Запись лога

        RETURNS:
        - bool: True если event_type в allowed, иначе False
        """
        event_type = getattr(record, "event_type", None)
        # Без event_type → не пропускаем в UI (только в файлы)
        if event_type is None:
            return False
        return event_type in self.allowed

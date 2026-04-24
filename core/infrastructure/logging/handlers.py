"""
Обработчики и фильтры для системы логирования.

АРХИТЕКТУРА:
- EventTypeFilter — фильтрует записи в StreamHandler по EventType
- Применяется ТОЛЬКО к консольному выводу (файлы пишут всё)
- Работает с extra={"event_type": EventType.XXX}

USAGE:
```python
from core.infrastructure.logging.handlers import EventTypeFilter
from core.infrastructure.event_bus.unified_event_bus import EventType

filter = EventTypeFilter({
    EventType.USER_PROGRESS,
    EventType.USER_RESULT,
    EventType.USER_MESSAGE,
})
console_handler.addFilter(filter)
```
"""
import logging
from typing import Set

from core.infrastructure.event_bus.unified_event_bus import EventType


class EventTypeFilter(logging.Filter):
    """
    Фильтр по типам событий для StreamHandler.

    ПРАВИЛА:
    - Пропускает только записи с event_type в allowed
    - Записи БЕЗ event_type НЕ ПРОПУСКАЕТ (только файлы)
    - Файлы пишут всё — фильтр только для консоли

    ATTRIBUTES:
    - allowed: Set[EventType] — разрешённые типы
    """

    def __init__(self, allowed: Set[EventType]):
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

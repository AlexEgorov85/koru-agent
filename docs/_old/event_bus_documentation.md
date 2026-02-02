# Документация по шине событий (Event Bus)

## Обзор

Шина событий (Event Bus) - это компонент системы, который обеспечивает централизованную обработку событий. Она позволяет публиковать события различных типов и обрабатывать их с помощью различных обработчиков. Шина событий интегрирована в системный контекст и предоставляет следующие возможности:

- Публикация событий различных типов
- Подписка обработчиков на определенные типы событий
- Глобальная подписка на все события
- Стандартные обработчики для вывода в консоль и логирования в файлы
- Возможность создания пользовательских обработчиков

## Архитектура

Шина событий состоит из следующих компонентов:

### EventType
Перечисление типов событий:
- `TASK_EXECUTION`: События, связанные с выполнением задач
- `PROGRESS`: События прогресса выполнения
- `ERROR`: События ошибок и исключений
- `USER_INTERACTION`: События взаимодействия с пользователем
- `SYSTEM`: Системные события (инициализация, завершение и т.д.)
- `DEBUG`: Отладочные события

### Event
Класс, представляющий событие с полями:
- `event_type`: Тип события
- `source`: Источник события (например, имя компонента)
- `data`: Произвольные данные события
- `timestamp`: Временная метка события
- `metadata`: Дополнительные метаданные события

### EventHandler
Абстрактный класс для обработчиков событий. Все обработчики должны наследоваться от него и реализовывать метод `handle_event`.

### EventSystem
Основной класс шины событий, обеспечивающий:
- Подписку обработчиков на события
- Публикацию событий
- Управление обработчиками

## Использование

### Создание и использование шины событий

Шина событий автоматически создается и интегрируется в `SystemContext`:

```python
from core.system_context import SystemContext
from core.config.models import SystemConfig

config = SystemConfig()
system_context = SystemContext(config=config)

# Публикация события
await system_context.event_system.publish_simple(
    event_type=EventType.TASK_EXECUTION,
    source="MyComponent",
    data={"task_id": "123", "action": "started", "description": "Task started"}
)
```

### Подписка на события

Подписка на события определенного типа:

```python
from core.system_context.event_bus import EventHandler, Event

class MyEventHandler(EventHandler):
    async def handle_event(self, event: Event):
        print(f"Received event: {event.data}")

handler = MyEventHandler()
system_context.event_system.subscribe(EventType.TASK_EXECUTION, handler)
```

Глобальная подписка на все события:

```python
system_context.event_system.subscribe_global(handler)
```

### Создание пользовательского обработчика

```python
from core.system_context.event_bus import EventHandler, Event
import logging

class CustomLogHandler(EventHandler):
    def __init__(self, log_file_path: str):
        self.logger = logging.getLogger("CustomLogger")
        handler = logging.FileHandler(log_file_path)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def handle_event(self, event: Event):
        self.logger.info(f"[{event.event_type.value}] {event.source}: {event.data}")
```

## Стандартные обработчики

### ConsoleOutputHandler
Выводит определенные типы событий в консоль. По умолчанию выводит события типов:
- `USER_INTERACTION`
- `ERROR`
- `SYSTEM`

Можно настроить, какие типы событий выводить:

```python
from core.system_context.event_bus import ConsoleOutputHandler, EventType

custom_handler = ConsoleOutputHandler(
    allowed_event_types=[EventType.ERROR, EventType.DEBUG]
)
```

### FileLogHandler
Записывает все события в файлы логов, раздельно по типам событий. Создает файлы вида:
- `task_execution_events.log`
- `progress_events.log`
- `error_events.log`
- и т.д.

### AgentStepDisplayHandler
Обработчик для красивого отображения промежуточных шагов агента. Отображает:
- События выполнения задач с указанием ID задачи и действия
- Прогресс выполнения с визуальным индикатором
- Взаимодействие с пользователем с разделением на пользовательский ввод и системный ответ

Можно настроить, какие типы событий отображать:

```python
from core.system_context import AgentStepDisplayHandler, EventType

# Создание обработчика с отображением только задач и прогресса
step_handler = AgentStepDisplayHandler(
    show_task_execution=True,
    show_progress=True,
    show_user_interaction=False,
    use_colors=False  # Для избежания проблем с кодировкой в некоторых терминалах
)
```

## Интеграция с системным контекстом

Шина событий автоматически интегрирована в `SystemContext`. Каждый экземпляр `SystemContext` создает свою шину событий как часть своего состояния (в атрибуте `event_system`).

Для получения шины событий из системного контекста используйте прямой доступ к атрибуту `event_system`:

```python
# Создание системного контекста
from core.system_context import SystemContext
from core.config.models import SystemConfig

config = SystemConfig()
system_context = SystemContext(config=config)

# Получение шины событий из системного контекста
event_bus = system_context.event_system
```

## Примеры использования

### Пример 1: Логирование ошибок

```python
await system_context.event_system.publish_simple(
    event_type=EventType.ERROR,
    source="DatabaseConnection",
    data={
        "error_code": "CONN_001",
        "message": "Connection timeout",
        "host": "localhost:5432"
    },
    metadata={"severity": "high", "component": "database"}
)
```

### Пример 2: Отслеживание прогресса

```python
await system_context.event_system.publish_simple(
    event_type=EventType.PROGRESS,
    source="DataProcessor",
    data={
        "task_id": "DP_001",
        "progress": 75,
        "total_items": 100,
        "processed_items": 75,
        "eta_seconds": 120
    }
)
```

### Пример 3: Взаимодействие с пользователем

```python
await system_context.event_system.publish_simple(
    event_type=EventType.USER_INTERACTION,
    source="ChatInterface",
    data={
        "user_id": "USR_123",
        "input": "What is the status of my task?",
        "response": "Your task is 75% complete",
        "timestamp": "2023-10-01T10:0:00Z"
    }
)
```

### Пример 4: Красивое отображение шагов агента

```python
from core.system_context import AgentStepDisplayHandler

# Создание обработчика для отображения шагов агента
step_handler = AgentStepDisplayHandler(
    show_task_execution=True,
    show_progress=True,
    show_user_interaction=True,
    use_colors=False
)

# Подписка на все события
system_context.event_system.subscribe_global(step_handler)
```

## Лучшие практики

1. Используйте соответствующие типы событий для лучшей фильтрации и обработки
2. Включайте в `data` достаточно информации для понимания контекста события
3. Используйте `metadata` для дополнительной информации, которая может быть полезна для обработки, но не является основными данными
4. Указывайте информативный `source`, чтобы можно было определить компонент, породивший событие
5. Создавайте специализированные обработчики для различных задач (логирование, оповещения, мониторинг и т.д.)

# Архитектура логирования

## Текущая архитектура (через стандартный logging)

```
┌───────────────────────────────────────────────────────────────┐
│  LoggingSession (создаётся при инициализации InfraContext)    │
│  ├── run_timestamp: "2026-04-11_15-57-18"                     │
│  ├── base_dir: logs/2026-04-11_15-57-18/                      │
│  ├── agents_dir: logs/.../agents/                             │
│  ├── infra_logger: logging.Logger → infra_context.log         │
│  ├── app_logger: logging.Logger → app_context.log             │
│  ├── component_logger: logging.Logger → components.log        │
│  └── create_agent_logger() → logging.Logger → agents/{ts}.log │
└───────────────────────────────────────────────────────────────┘

Каждый logger:
  ├── FileHandler (пишет ВСЁ, без фильтра)
  │   Формат: "%(asctime)s | %(levelname)-8s | %(event_type)-20s | %(name)s | %(message)s"
  └── propagate = False (не дублирует в root)

Root logger:
  └── StreamHandler (stdout)
      ├── EventTypeFilter(14 разрешённых событий)
      └── Формат: "%(levelname)-7s | %(message)s"
```

## Компоненты

### LoggingSession

```python
class LoggingSession:
    def setup_context_loggers(self):
        # Создаёт директорию
        # Настраивает infra_logger, app_logger, component_logger
        # Добавляет console handler с фильтром

    def create_agent_logger(self, agent_id: str) -> logging.Logger:
        # 1 сессия = 1 файл: agents/{timestamp}.log

    def get_component_logger(self, component_name: str) -> logging.Logger:
        # Возвращает логгер для компонента, пишет в components.log
```

### ComponentLogger

Компоненты наследуют `ComponentLogger` через базовый класс `Component`. Логгер доступен через `self.log`:

```python
class MySkill(Skill):
    async def _execute_impl(self, capability, parameters, context):
        self.log.info("Начало выполнения", extra={"event_type": LogEventType.USER_PROGRESS})
        self.log.debug(f"Параметры: {parameters}")
        self.log.warning("Превышен лимит")
        self.log.error(f"Ошибка: {e}", exc_info=True)
```

Компоненты получают логгер через `LoggingSession.get_component_logger()` или через `application_context.infrastructure_context.log_session`. Все логи компонентов записываются в `components.log`.

### EventTypeFilter

```python
class EventTypeFilter(logging.Filter):
    def __init__(self, allowed: Set[LogEventType]):
        self.allowed = allowed

    def filter(self, record: logging.LogRecord) -> bool:
        event_type = getattr(record, "event_type", None)
        if event_type is None:
            return False          # Без event_type → НЕ в терминал
        return event_type in self.allowed
```

### Форматтеры

**Файловый (`_LogFileFormatter`):**
```
2026-04-11 15:57:29,995 | INFO     | SYSTEM_INIT          | app.context | Сообщение
```

**Консольный:**
```
INFO    | 📍 ШАГ 1/10
ERROR   | ❌ Действие sql_tool.execute завершилось с ошибкой
```

## Ключевые отличия от старой архитектуры

| Аспект | Было (устарело) | Сейчас |
|--------|-----------------|--------|
| Основа | EventBus + EventBusLogger | Стандартный `logging` Python |
| Компоненты | LoggingMixinV2 | ComponentLogger через `Component` |
| Фильтрация | Подписка на EventType | EventTypeFilter на StreamHandler |
| Формат | JSONL | Текст с event_type |
| Сессии | LogManager + LogIndexer | LoggingSession (1 запуск = 1 директория) |
| Agent логи | Отдельная система | Тот же logging, отдельный файл |
| Логи компонентов | Разрозненные файлы | Единый `components.log` |

## Удалённые файлы

| Файл | Причина |
|------|---------|
| `event_bus_log_handler.py` | Дублировал функциональность |
| `event_bus_logger.py` | Заменён на `ComponentLogger` + стандартный `logging` |
| `log_formatter.py` | Legacy для обратной совместимости |

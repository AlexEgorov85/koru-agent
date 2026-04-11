# Система логирования koru-agent

## Обзор

Единая система логирования, основанная на **стандартном `logging` Python** с расширением через `extra={"event_type": LogEventType.XXX}`.

**Принципы:**
- **1 запуск = 1 директория логов** (`logs/{timestamp}/`)
- **1 сессия агента = 1 файл лога** (`logs/{ts}/agents/{ts}.log`)
- **Консоль фильтруется** — только 14 разрешённых типов событий
- **Файлы пишут всё** — без фильтрации
- **Никаких EventBusLogger** — только стандартный `logging`
- **Никаких `print()`** в core коде

---

## Архитектура

```
LoggingSession (создаётся при инициализации InfraContext)
├── infra_logger  → logs/{ts}/infra_context.log
├── app_logger    → logs/{ts}/app_context.log
└── create_agent_logger(agent_id)
    └── logs/{ts}/agents/{ts}.log

Консоль (stdout):
  Фильтр: EventTypeFilter(14 разрешённых событий)
  Формат: "%(levelname)-7s | %(message)s"
```

### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `core/infrastructure/logging/session.py` | `LoggingSession` — ядро, создаёт директорию и хендлеры |
| `core/infrastructure/logging/event_types.py` | `LogEventType` — enum типов событий |
| `core/infrastructure/logging/handlers.py` | `EventTypeFilter` — фильтр для терминала |
| `core/config/logging_config.py` | `LoggingConfig`, `ConsoleConfig` — конфигурация |

---

## Типы событий (LogEventType)

| Категория | События | Терминал |
|-----------|---------|----------|
| **Пользователь** | `USER_PROGRESS`, `USER_RESULT`, `USER_MESSAGE`, `USER_QUESTION` | ✅ |
| **Агент** | `AGENT_START`, `AGENT_STOP` | ✅ |
| | `AGENT_THINKING`, `AGENT_DECISION` | ❌ (файл) |
| **Шаги** | `STEP_STARTED`, `STEP_COMPLETED` | ❌ (файл) |
| **Инструменты** | `TOOL_CALL`, `TOOL_RESULT`, `TOOL_ERROR` | ✅ |
| **LLM** | `LLM_CALL`, `LLM_RESPONSE` | ❌ (файл) |
| | `LLM_ERROR` | ✅ |
| **БД** | `DB_ERROR` | ✅ |
| **Система** | `SYSTEM_INIT`, `SYSTEM_READY`, `SYSTEM_SHUTDOWN` | ❌ (файл) |
| **Уровни** | `WARNING`, `ERROR`, `CRITICAL` | ✅ |
| | `INFO`, `DEBUG` | ❌ (файл) |

Записи **без** `event_type` **НЕ попадают** в терминал — только в файлы.

---

## Как использовать

### В компонентах (skills, services, tools, behaviors)

Компоненты наследуют `LoggingMixinV2` через `Component`:

```python
class MySkill(Skill):
    async def _execute_impl(self, capability, parameters, context):
        self._log_info("Начало выполнения", event_type=LogEventType.USER_PROGRESS)
        self._log_debug(f"Параметры: {parameters}")           # только файл
        self._log_warning("Превышен лимит")                   # терминал + файл
        self._log_error(f"Ошибка: {e}", exc_info=True)        # терминал + файл + stack
```

### В инфраструктуре

```python
import logging
from core.infrastructure.logging.event_types import LogEventType

log = logging.getLogger(__name__)

log.info("Инициализация...", extra={"event_type": LogEventType.SYSTEM_INIT})
log.warning("Превышен лимит", extra={"event_type": LogEventType.WARNING})
log.error(f"Критическая ошибка: {e}", extra={"event_type": LogEventType.CRITICAL}, exc_info=True)
```

### Цикл агента (runtime)

```python
class AgentRuntime:
    async def _run_async(self):
        self.log.info(f"🚀 Запуск агента: {self.goal}...",
                      extra={"event_type": LogEventType.AGENT_START})

        for step in range(self.max_steps):
            self.log.info(f"📍 ШАГ {step + 1}/{self.max_steps}",
                          extra={"event_type": LogEventType.STEP_STARTED})

            decision = await pattern.decide(...)
            self.log.info(f"✅ Pattern вернул: {decision.type.value}",
                          extra={"event_type": LogEventType.AGENT_DECISION})
```

---

## Структура файлов логов

```
logs/
└── 2026-04-11_15-57-18/                    # Генерируется один раз при запуске
    ├── infra_context.log                   # Инфраструктура (провайдеры, БД, LLM)
    ├── app_context.log                     # Приложение (компоненты, сервисы)
    └── agents/
        ├── 2026-04-11_15-58-00.log         # Сессия агента #1
        └── 2026-04-11_16-02-30.log         # Сессия агента #2
```

### Формат записи в файле

```
2026-04-11 15:57:29,995 | INFO     | SYSTEM_INIT          | app.context | Ресурсы загружены через ResourceLoader (профиль=prod)
2026-04-11 15:57:30,001 | INFO     | SYSTEM_INIT          | app.context | Создание LLMOrchestrator...
2026-04-11 15:57:30,001 | INFO     | SYSTEM_READY         | app.context | LLMOrchestrator инициализирован успешно!
2026-04-11 15:57:30,149 | ERROR    | ERROR                | app.context | Ошибка создания service.contract_service: No module named...
                                    Traceback (most recent call last):
                                      File "...", line 219, in initialize
                                        component = await self._create_component(...)
                                      ...
```

---

## Конфигурация

### Консольный вывод

```python
from core.config.logging_config import LoggingConfig, ConsoleConfig
from core.infrastructure.logging.event_types import LogEventType

config = LoggingConfig(
    console=ConsoleConfig(
        allowed_terminal_events={
            LogEventType.USER_PROGRESS,
            LogEventType.USER_RESULT,
            LogEventType.AGENT_START,
            LogEventType.AGENT_STOP,
            LogEventType.TOOL_CALL,
            LogEventType.TOOL_RESULT,
            LogEventType.TOOL_ERROR,
            LogEventType.WARNING,
            LogEventType.ERROR,
        }
    )
)
```

**Дефолтный набор** (14 событий):
- Пользователь: `USER_PROGRESS`, `USER_RESULT`, `USER_MESSAGE`, `USER_QUESTION`
- Агент: `AGENT_START`, `AGENT_STOP`
- Инструменты: `TOOL_CALL`, `TOOL_RESULT`, `TOOL_ERROR`
- Ошибки: `LLM_ERROR`, `DB_ERROR`, `WARNING`, `ERROR`, `CRITICAL`

---

## Правила логирования

1. **Все `except Exception`** должны иметь `exc_info=True`
2. **Никаких `pass`** в `except Exception` — минимум warning
3. **Никаких `EventBusLogger`** — только `self.log` + `LogEventType`
4. **Никаких `print()`** — только logging
5. **`logging.getLogger()`** — только в `__init__` компонентов, НЕ в runtime
6. **Формат сообщений** — `%s` вместо f-strings в `log.info/error()` (производительность)
7. **Консоль фильтруется** — только события из `allowed_terminal_events`
8. **Файловые логи пишут всё** — без фильтрации

---

## Что было раньше (устарело)

| Было | Стало |
|------|-------|
| `EventBusLogger` | `logging.getLogger()` + `extra={"event_type": ...}` |
| `event_bus.publish(EventType.LOG_INFO, ...)` для логов | `log.info(..., extra={"event_type": LogEventType.INFO})` |
| `print()` | `self._log_info()` / `self._log_debug()` |
| `LogManager` / `LogIndexer` | `LoggingSession` + стандартный `logging` |
| JSONL формат | Текстовый формат с `event_type` |

---

## Связанные документы

- [Архитектура логирования](ARCHITECTURE.md) — детальная архитектура
- [План миграции логирования](../plans/logging_migration_plan.md) — статус миграции
- [AGENTS.md](../../AGENTS.md) — раздел 5: правила логирования

# План миграции логирования в `core/infrastructure`

> Создан: 10 апреля 2026
> Обновлено: 11 апреля 2026
> Статус: **Завершена** (ядро агента), в процессе (провайдеры)

---

## ✅ Завершено (Done)

### Ядро агента (`core/agent/`)

| Файл | Что сделано |
|------|------------|
| `agent/runtime.py` | Цикл переведён с EventBus на `self.log`, try/except с exc_info, логирование каждого шага |
| `agent/behaviors/react/pattern.py` | LLM_CALL/LLM_RESPONSE логирование, все except с exc_info |
| `agent/behaviors/evaluation/pattern.py` | Все except с exc_info |
| `agent/behaviors/base_behavior_pattern.py` | Убраны print(), все except с exc_info |
| `agent/behaviors/planning/pattern.py` | Убран event_bus параметр, LogEventType |
| `agent/components/action_executor.py` | Все except с exc_info + _module_logger.error |
| `agent/components/safe_executor.py` | Добавлен event_type: DEBUG, WARNING + exc_info |
| `agent/components/component.py` | `_publish_with_context`: debug лог вместо pass |
| `agent/components/component_factory.py` | `_log_info` без event_type (только в файл) |

### Конфигурация логирования (`core/config/`)

| Файл | Что сделано |
|------|------------|
| `config/logging_config.py` | `ConsoleConfig.allowed_terminal_events` — дефолтный набор из 14 событий |
| `config/app_config.py` | Удалён мёртвый параметр `discovery` из `from_discovery()` |

### Контексты (`core/application_context/`)

| Файл | Что сделано |
|------|------------|
| `application_context/application_context.py` | `LogEventType.INFO` → `SYSTEM_INIT`/`SYSTEM_SHUTDOWN` (убрано дублирование в логах) |
| `infrastructure_context/infrastructure_context.py` | Все f-strings → %s, все except с exc_info=True |

### Провайдеры LLM

| Файл | Что сделано |
|------|------------|
| `providers/base_provider.py` | `self.log = logging.getLogger()`, EventBusLogger удалён |
| `providers/database/mock_provider.py` | Все `event_bus_logger → self.log` |
| `providers/llm/base_llm.py` | `_log_llm_call_*` → `self.log` + `LogEventType` |
| `providers/llm/mock_provider.py` | Все `event_bus_logger → self.log` |
| `providers/llm/llm_orchestrator.py` | EventBusLogger → `logging.getLogger()`, print() → logger |

### Логирование (`core/infrastructure/logging/`)

| Файл | Что сделано |
|------|------------|
| `logging/session.py` | `LoggingSession` — ядро, создаёт директорию и хендлеры |
| `logging/event_types.py` | `LogEventType` — enum типов событий |
| `logging/handlers.py` | `EventTypeFilter` — фильтр для терминала |

### Удалённые одноразовые скрипты

| Скрипт | Причина удаления |
|--------|-----------------|
| `scripts/maintenance/fix_encoding.py` | Задача выполнена |
| `scripts/maintenance/remove_bom.py` | Задача выполнена |
| `scripts/maintenance/migrate_logs.py` | Задача выполнена |
| `scripts/validation/fix_behavior_prompts.py` | Задача выполнена |

## ❌ Оставшиеся задачи

### 1. Провайдеры LLM

| Файл | Проблемы | Оценочно строк |
|------|----------|---------------|
| `providers/llm/llama_cpp_provider.py` | ~60 `event_bus_logger` вызовов, f-strings, нет exc_info | ~600 строк |
| `providers/llm/openrouter_provider.py` | ~14 `event_bus_logger` вызовов, нет exc_info | ~250 строк |
| `providers/llm/vllm_provider.py` | ~8 except без логирования/без exc_info | ~420 строк |

### 2. Провайдеры Database

| Файл | Проблемы |
|------|----------|
| `providers/database/postgres_provider.py` | 6 f-строк осталось (regex не сработал для некоторых) |

### 3. Storage

| Файл | Проблемы |
|------|----------|
| `storage/capability_registry.py` | `EventBusLogger`, f-strings в `_log_warning` без exc_info |
| `storage/base/versioned_storage.py` | `EventBusLogger`, f-strings, нет логирования в except |

### 4. EventBus

| Файл | Проблемы |
|------|----------|
| `event_bus/unified_event_bus.py` | ~32 TODO, `logging.getLogger()`, f-strings |

### 5. Loading

| Файл | Проблемы |
|------|----------|
| `loading/resource_loader.py` | `logging.getLogger()`, f-strings |

### 6. Telemetry

| Файл | Проблемы |
|------|----------|
| `telemetry/handlers/session_handler.py` | `except Exception: pass` (2 шт) — полное подавление ошибок |
| `telemetry/handlers/terminal_handler.py` | Проверить на f-strings |

### 7. Embedding

| Файл | Проблемы |
|------|----------|
| `providers/embedding/sentence_transformers_provider.py` | `except Exception: pass`, нет логирования в except |

---

## Правила логирования

1. **Никаких f-строк** в `self.log.info/error/warning/debug()` — только `%s`, `%d`, `%.2f`
2. **Все `except Exception`** должны иметь `exc_info=True`
3. **Никаких `pass`** в `except Exception` — минимум warning
4. **Никаких `EventBusLogger`** — только `self.log` + `LogEventType`
5. **Никаких `print()`** — только logging
6. **`logging.getLogger()`** — только в `__init__` компонентов, НЕ в runtime
7. **Консольный вывод фильтруется** — только события из `allowed_terminal_events` (14 типов)
8. **Файловые логи пишут всё** — без фильтрации
9. **1 сессия агента = 1 файл лога** — `logs/{timestamp}/agents/{timestamp}.log`

---

## Архитектура логирования

```
┌───────────────────────────────────────────────────────────────┐
│  LoggingSession (создаётся при инициализации InfraContext)    │
│  ├── infra_logger  → logs/{ts}/infra_context.log              │
│  ├── app_logger    → logs/{ts}/app_context.log                │
│  └── create_agent_logger() → logs/{ts}/agents/{ts}.log        │
└───────────────────────────────────────────────────────────────┘

Консоль: фильтруется по allowed_terminal_events (14 типов)
Файлы: пишут ВСЁ без фильтрации
```

**Разрешённые события для терминала:**
- `USER_PROGRESS`, `USER_RESULT`, `USER_MESSAGE`, `USER_QUESTION`
- `AGENT_START`, `AGENT_STOP`
- `TOOL_CALL`, `TOOL_RESULT`, `TOOL_ERROR`
- `LLM_ERROR`, `DB_ERROR`
- `WARNING`, `ERROR`, `CRITICAL`

**Только в файлы (НЕ в терминал):**
- `SYSTEM_INIT`, `SYSTEM_READY`, `SYSTEM_SHUTDOWN`
- `STEP_STARTED`, `STEP_COMPLETED`
- `AGENT_THINKING`, `AGENT_DECISION`
- `LLM_CALL`, `LLM_RESPONSE`
- `INFO`, `DEBUG`
- Записи **без** `event_type`

---

## Порядок выполнения

1. ✅ ~~InfraContext~~
2. ✅ ~~BaseProvider~~
3. ✅ ~~DB MockProvider~~
4. ❌ **PostgreSQLProvider** — доделать f-strings (6 осталось)
5. ✅ ~~LLMOrchestrator~~
6. ✅ ~~MockLLMProvider~~
7. ❌ **openrouter_provider** — EventBusLogger → self.log
8. ❌ **llama_cpp_provider** — EventBusLogger → self.log (самый большой)
9. ❌ **vllm_provider** — добавить логирование в except
10. ❌ **capability_registry** — EventBusLogger → self.log
11. ❌ **versioned_storage** — EventBusLogger → self.log
12. ❌ **session_handler** — убрать `except: pass`
13. ❌ **sentence_transformers** — убрать `except: pass`
14. ✅ ~~core/agent/ — полное логирование с exc_info~~
15. ✅ ~~ConsoleConfig.allowed_terminal_events — дефолтный набор~~

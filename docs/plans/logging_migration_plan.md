# План миграции логирования в `core/infrastructure`

> Создан: 10 апреля 2026
> Статус: В процессе

---

## ✅已完成 (Done)

| Файл | Что сделано |
|------|------------|
| `infrastructure_context/infrastructure_context.py` | Все f-strings → %s, все except с exc_info=True |
| `providers/base_provider.py` | `self.log = logging.getLogger()`, EventBusLogger удалён |
| `providers/database/mock_provider.py` | Все `event_bus_logger → self.log` |
| `providers/database/postgres_provider.py` | f-strings → %s, exc_info=True (в процессе) |
| `providers/llm/base_llm.py` | `_log_llm_call_*` → `self.log` + `LogEventType` |
| `providers/llm/mock_provider.py` | Все `event_bus_logger → self.log` |
| `providers/llm/llm_orchestrator.py` | EventBusLogger → `logging.getLogger()`, print() → logger |

## ❌ В процессе

| Файл | Проблемы | Приоритет |
|------|----------|-----------|
| _(ничего)_ | | |

## 📋 Оставшиеся задачи

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

### 8. Mock Provider LLM

| Файл | Проблемы |
|------|----------|
| `providers/llm/mock_provider.py` | Нет exc_info=True в except |

---

## Правила логирования

1. **Никаких f-строк** в `self.log.info/error/warning/debug()` — только `%s`, `%d`, `%.2f`
2. **Все `except Exception`** должны иметь `exc_info=True`
3. **Никаких `pass`** в `except Exception` — минимум warning
4. **Никаких `EventBusLogger`** — только `self.log` + `LogEventType`
5. **Никаких `print()`** — только logging
6. **`logging.getLogger()`** — только в `__init__` компонентов, НЕ в runtime

---

## Порядок выполнения

1. ✅ ~~InfraContext~~
2. ✅ ~~BaseProvider~~
3. ✅ ~~DB MockProvider~~
4. ❌ **PostgreSQLProvider** — доделать f-strings (6 осталось)
5. ❌ **LLMOrchestrator** — добавить exc_info
6. ❌ **MockLLMProvider** — добавить exc_info
7. ❌ **openrouter_provider** — EventBusLogger → self.log
8. ❌ **llama_cpp_provider** — EventBusLogger → self.log (самый большой)
9. ❌ **vllm_provider** — добавить логирование в except
10. ❌ **capability_registry** — EventBusLogger → self.log
11. ❌ **versioned_storage** — EventBusLogger → self.log
12. ❌ **session_handler** — убрать `except: pass`
13. ❌ **sentence_transformers** — убрать `except: pass`

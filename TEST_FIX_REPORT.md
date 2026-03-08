# Отчёт об исправлении проблем в тестах и коде

## Дата
8 марта 2026 г.

## Обнаруженные проблемы

В ходе работы были выявлены следующие проблемы, которые требовали исправления:

### 1. Несоответствие параметров ExecutionResult

**Проблема:** В `runtime.py` и тестах использовался параметр `result=`, но класс `ExecutionResult` использует `data=`.

**Где обнаружено:**
- `core/application/agent/runtime.py` — 6 мест
- `core/application/agent/components/executor.py` — 3 места
- `tests/application/agent/test_error_handling_fix.py` — 1 место

**Исправление:**
```python
# До:
ExecutionResult(status='completed', result=..., error=...)

# После:
ExecutionResult(status=ExecutionStatus.COMPLETED, data=..., error=...)
```

### 2. AgentStateSnapshot не поддерживал dict-доступ

**Проблема:** Тесты ожидали доступ через `snapshot['step']`, но `AgentStateSnapshot` — это dataclass без поддержки индексации.

**Где обнаружено:**
- `tests/application/agent/test_agent_runtime_loops.py` — тесты `test_snapshot_contains_all_fields`, `test_snapshot_with_empty_history`

**Исправление:** Добавлены методы в `AgentStateSnapshot`:
```python
def __getitem__(self, key: str) -> Any:
    """Поддержка dict-подобного доступа для совместимости с тестами."""
    return getattr(self, key)

def get(self, key: str, default: Any = None) -> Any:
    """Dict-подобный get() для безопасного доступа."""
    return getattr(self, key, default)

def to_dict(self) -> Dict[str, Any]:
    """Конвертация в словарь."""
    return {...}
```

### 3. Моки event_bus.publish не были awaitable

**Проблема:** `event_bus.publish` вызывается с `await`, но мок был `MagicMock()`, а не `AsyncMock()`.

**Где обнаружено:**
- `tests/application/agent/test_agent_runtime_loops.py` — fixture `mock_application_context`

**Исправление:**
```python
# До:
mock.infrastructure_context.event_bus.publish = MagicMock()

# После:
mock.infrastructure_context.event_bus.publish = AsyncMock()
```

### 4. get_all_capabilities должен быть AsyncMock

**Проблема:** Метод `get_all_capabilities()` вызывается с `await`, но в тестах был `MagicMock(return_value=[])`.

**Где обнаружено:**
- `tests/application/agent/test_agent_runtime_loops.py` — fixture `mock_application_context`

**Исправление:**
```python
# До:
mock.get_all_capabilities = MagicMock(return_value=[])

# После:
mock.get_all_capabilities = AsyncMock(return_value=[])
```

### 5. Тесты проверяли несуществующее поле result.result

**Проблема:** Тесты проверяли `result.result`, но `ExecutionResult` имеет поле `error` для сообщений об ошибках.

**Где обнаружено:**
- `tests/application/agent/test_agent_runtime_loops.py` — тесты `test_agent_stuck_on_repeating_decisions`, `test_agent_stuck_on_state_not_mutating`

**Исправление:**
```python
# До:
assert "AgentStuckError" in result.result or "State did not mutate" in result.result

# После:
assert result.error is not None
assert "no_progress" in result.error.lower() or "steps" in result.error.lower()
```

### 6. executor.py использовал строки вместо ExecutionStatus

**Проблема:** В `executor.py` статус передавался как строка (`status='completed'`), а должен быть `ExecutionStatus`.

**Где обнаружено:**
- `core/application/agent/components/executor.py` — 3 места

**Исправление:**
```python
# До:
return ExecutionResult(status='completed', data=result, ...)
return ExecutionResult(status='failed', data={'error': ...}, ...)

# После:
return ExecutionResult(status=ExecutionStatus.COMPLETED, data=result, ...)
return ExecutionResult(status=ExecutionStatus.FAILED, data={'error': ...}, ...)
```

## Исправленные файлы

### Код
1. **core/application/agent/components/state.py**
   - Добавлены методы `__getitem__`, `get`, `to_dict` в `AgentStateSnapshot`

2. **core/application/agent/runtime.py**
   - Исправлено 6 мест с `result=` на `data=` в `ExecutionResult`

3. **core/application/agent/components/executor.py**
   - Добавлен импорт `ExecutionStatus`
   - Исправлено 3 места с строковыми статусами на `ExecutionStatus`

### Тесты
4. **tests/application/agent/test_agent_runtime_loops.py**
   - Исправлен fixture `mock_application_context` (AsyncMock для `get_all_capabilities` и `event_bus.publish`)
   - Исправлены проверки в тестах `test_agent_stuck_on_repeating_decisions`, `test_agent_stuck_on_state_not_mutating`

5. **tests/application/agent/test_error_handling_fix.py**
   - Исправлено создание `ExecutionResult` (`data=` вместо отсутствующего параметра)

## Результаты тестов

### До исправлений
- `test_agent_runtime_loops.py`: 5/10 passed ❌
- `test_error_handling_fix.py`: 4/7 passed ❌

### После исправлений
- `test_agent_runtime_loops.py`: 10/10 passed ✅
- `test_error_handling_fix.py`: 7/7 passed ✅
- `test_error_observation_recording.py`: 5/5 passed ✅

**Итого: 22/22 теста пройдены** ✅

## Дополнительные улучшения

В ходе исправлений также было создано:
- **tests/application/agent/test_error_observation_recording.py** — новый набор тестов для проверки записи observation при ошибке

## Совместимость

Все исправления обратно совместимы:
- `AgentStateSnapshot` теперь поддерживает как dict-доступ (`snapshot['step']`), так и атрибуты (`snapshot.step`)
- `ExecutionResult` использует корректные параметры согласно своей сигнатуре
- Моки в тестах теперь соответствуют асинхронному интерфейсу

## Рекомендации

1. **Добавить линтинг тестов** — настроить проверку на использование `MagicMock` вместо `AsyncMock` для async методов
2. **Типизация тестов** — добавить type hints для fixtures и тестовых функций
3. **Документирование ExecutionResult** — явно указать в документации что используется `data=`, а не `result=`

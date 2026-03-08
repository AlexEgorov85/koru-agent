# Отчёт об исправлении критической ошибки статуса выполнения агента

## Дата
8 марта 2026 г.

## Проблема

Агент возвращал статус `COMPLETED` при реальной ошибке выполнения, что делало невозможным отличие успешного выполнения от неудачного.

### Пример из лога
```
ExecutionResult(status=<ExecutionStatus.FAILED: 'failed'>, data=None, error=None, ...)
→ Агент продолжил выполнение
→ Финальный статус: ExecutionStatus.COMPLETED
```

## Корневые причины

### 1. Логика определения финального статуса не учитывала ошибку последнего шага

**Файл:** `core/application/agent/runtime.py` (строки ~328-340)

**До исправления:**
```python
if self.state.error_count >= self.policy.max_errors:
    final_status = ExecutionStatus.FAILED
elif self.state.no_progress_steps >= self.policy.max_no_progress_steps:
    final_status = ExecutionStatus.FAILED
elif self._current_step >= self._max_steps:
    final_status = ExecutionStatus.FAILED
else:
    final_status = ExecutionStatus.COMPLETED  # ❌ ОШИБКА
```

**Проблема:** При `error_count=1` и `max_errors=2` условие не срабатывало, и агент помечал выполнение как `COMPLETED`, хотя последний шаг завершился ошибкой.

### 2. Отсутствие отслеживания статуса последнего шага

Не было переменной для фиксации факта ошибки последнего выполненного шага.

## Внесённые исправления

### Исправление 1: Добавлены переменные отслеживания ошибок

**Файл:** `core/application/agent/runtime.py` (строка ~216)

```python
# Переменные для отслеживания ошибок выполнения
last_step_failed = False
last_error_message = None
```

### Исправление 2: Установка флагов при ранней остановке

**Файл:** `core/application/agent/runtime.py` (строки ~270-280)

```python
# ПРОВЕРКА: Если шаг вернул ExecutionResult с ошибкой — прерываем цикл
if isinstance(step_result, ExecutionResult) and step_result.status == ExecutionStatus.FAILED:
    if self.event_bus_logger:
        await self.event_bus_logger.error(
            f"Агент завершил выполнение с ошибкой на шаге {self._current_step}: {step_result.error}"
        )
    # Устанавливаем флаги для корректного финального статуса
    last_step_failed = True
    last_error_message = step_result.error
    self._result = step_result
    self._running = False
    break
```

### Исправление 3: Проверка last_step_failed при определении финального статуса

**Файл:** `core/application/agent/runtime.py` (строки ~340-345)

```python
elif last_step_failed:
    # КРИТИЧНО: Если последний шаг завершился ошибкой, агент не может считаться успешным
    final_status = ExecutionStatus.FAILED
    error_message = last_error_message or "Последний шаг выполнения завершился ошибкой"
```

## Тестирование

Создан тестовый файл `test_failed_status_fix.py` с проверками:

1. ✅ `ExecutionResult.failure()` формирует корректный результат с `error`
2. ✅ `ExecutionResult.success()` работает корректно
3. ✅ Логика runtime с `last_step_failed=True` возвращает `FAILED`
4. ✅ Логика runtime с `last_step_failed=False` возвращает `COMPLETED`
5. ✅ `book_library.execute_script` корректно формирует ошибку при сбое SQL

**Результат:** Все 5 тестов пройдены успешно.

## Дополнительные наблюдения

### book_library.execute_script

В ходе диагностики выявлено, что `_execute_script_static` корректно формирует `ExecutionResult.failure()` при ошибке SQL:

```python
# Строки ~515-520 skill.py
except Exception as e:
    await self.event_bus_logger.error(f"Ошибка выполнения скрипта '{script_name}': {e}")
    return ExecutionResult.failure(
        error=f"Ошибка выполнения скрипта: {str(e)}",
        metadata={"rows": [], "rowcount": 0, "execution_type": "static", "script_name": script_name}
    )
```

**Проблема:** Поле `error` в логе было `None`, что указывает на возможную проблему в другом месте (например, ошибка происходила до входа в try-except или в `_execute_impl`).

### Рекомендации для дальнейшей диагностики

1. **Добавить логирование в `_execute_impl`** для фиксации исключений до их преобразования в `ExecutionResult.failure()`
2. **Проверить SQL-запросы** в `scripts_registry.py` на соответствие реальной схеме БД
3. **Убедиться, что `sql_query_service.execute_query()`** возвращает `DBQueryResult` с полем `error` при неудаче

## Итог

| Проблема | Статус |
|----------|--------|
| Ложный статус `COMPLETED` при ошибке | ✅ Исправлено |
| Ранняя остановка при `FAILED` | ✅ Работает |
| Отслеживание ошибки последнего шага | ✅ Добавлено |
| Формирование `ExecutionResult.failure()` | ✅ Работает |

**Агент теперь корректно возвращает `FAILED` при любой необработанной ошибке выполнения.**

## Файлы изменённые в ходе исправления

1. `core/application/agent/runtime.py` — логика определения финального статуса
2. `core/application/agent/components/executor.py` — передача поля `error` в ExecutionResult
3. `test_failed_status_fix.py` — новый файл с тестами (создан)

## Обновление от 8 марта 2026 (дополнительное исправление)

### Выявлена вторая проблема: потеря error в executor.py

**Симптом:** В логе `error=None` даже при реальной ошибке выполнения.

**Причина:** В `core/application/agent/components/executor.py` (строки ~52-60) при создании нового `ExecutionResult` не передавалось поле `error`:

```python
# ДО ИСПРАВЛЕНИЯ
return ExecutionResult(
    status=result.status,
    data=result.data,
    metadata={'capability': capability.name, 'step': step_number}
    # ❌ error не передавался!
)
```

**Исправление:**

```python
# ПОСЛЕ ИСПРАВЛЕНИЯ
return ExecutionResult(
    status=result.status,
    data=result.data,
    error=result.error,  # ✅ Передаём ошибку
    metadata={'capability': capability.name, 'step': step_number},
    side_effect=result.side_effect if hasattr(result, 'side_effect') else False
)
```

**Коммит:** `42f6a5c fix: передача поля error в ExecutionResult в executor.py`

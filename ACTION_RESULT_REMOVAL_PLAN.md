# План: Удаление ActionResult в пользу ExecutionResult

## 📋 Проблема

В проекте существуют ДВА класса для результатов выполнения:

1. **`ExecutionResult`** (core/models/data/execution.py)
   - Используется в `BaseComponent.execute()`
   - Возвращается всеми Skills, Tools, Services
   - Поля: `status`, `data`, `error`, `metadata`, `side_effect`

2. **`ActionResult`** (core/application/agent/components/action_executor.py)
   - Используется в `ActionExecutor.execute_action()`
   - Возвращается методами `execute_action()`, `_execute_llm_action()`, etc.
   - Поля: `success`, `data`, `error`, `metadata`, `llm_called`

### Критическая Несовместимость

```python
# action_executor.py, строка 184
async def execute_action(...) -> ActionResult:
    result = await target_component.execute(...)  # ← Возвращает ExecutionResult!
    return result  # ← TypeError: ExecutionResult != ActionResult
```

## ✅ Решение

**Удалить `ActionResult`, использовать везде `ExecutionResult`**

### Преимущества

1. **Единый класс** для всех результатов выполнения
2. **Совместимость** между компонентами и executor
3. **Более богатая семантика**: `ExecutionStatus` vs `bool`
4. **Меньше кода**: не нужно поддерживать два класса

### План Изменений

#### 1. Обновить ActionExecutor

**Файл:** `core/application/agent/components/action_executor.py`

```python
# БЫЛО:
from typing import Generic, TypeVar

class ActionResult(Generic[T]):
    def __init__(self, success: bool, data: Optional[T] = None, ...):
        self.success = success
        ...

# СТАЛО (удалить класс ActionResult):
# Использовать ExecutionResult напрямую

# Обновить сигнатуры методов:
# БЫЛО:
async def execute_action(...) -> ActionResult:

# СТАЛО:
async def execute_action(...) -> ExecutionResult:
```

#### 2. Обновить Возвращаемые Значения

```python
# БЫЛО:
return ActionResult(success=False, error="...")

# СТАЛО:
from core.models.data.execution import ExecutionResult, ExecutionStatus

return ExecutionResult(
    status=ExecutionStatus.FAILED,
    error="...",
    metadata={"llm_called": False}  # ← llm_called в metadata
)
```

#### 3. Обновить Поля

| ActionResult | ExecutionResult | Примечание |
|--------------|-----------------|------------|
| `success: bool` | `status: ExecutionStatus` | COMPLETED/FAILED/ABORTED |
| `data: T` | `data: Any` | Одинаково |
| `error: str` | `error: str` | Одинаково |
| `metadata: dict` | `metadata: dict` | Одинаково |
| `llm_called: bool` | `metadata["llm_called"]` | Переместить в metadata |

#### 4. Файлы для Изменения

1. **core/application/agent/components/action_executor.py**
   - Удалить класс `ActionResult`
   - Обновить все методы: `execute_action()`, `_execute_context_action()`, `_execute_llm_action()`, etc.
   - Заменить все `ActionResult(...)` на `ExecutionResult(...)`

2. **core/application/skills/planning/skill.py**
   - Обновить импорты
   - Заменить `ActionResult` на `ExecutionResult`

3. **Тесты (если есть)**
   - Обновить все тесты которые используют `ActionResult`

### Пример Изменения

```python
# БЫЛО (action_executor.py):
async def _execute_llm_action(
    self,
    action_name: str,
    parameters: Dict[str, Any],
    context: ExecutionContext
) -> ActionResult:
    ...
    if not llm_provider:
        return ActionResult(
            success=False,
            error="LLM provider not found"
        )
    
    response = await llm_provider.generate(...)
    return ActionResult(
        success=True,
        data={"content": response.content},
        llm_called=True
    )

# СТАЛО:
from core.models.data.execution import ExecutionResult, ExecutionStatus

async def _execute_llm_action(
    self,
    action_name: str,
    parameters: Dict[str, Any],
    context: ExecutionContext
) -> ExecutionResult:
    ...
    if not llm_provider:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error="LLM provider not found",
            metadata={"llm_called": False}
        )
    
    response = await llm_provider.generate(...)
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        data={"content": response.content},
        metadata={"llm_called": True}
    )
```

## 📊 Статистика

| Файл | Изменений |
|------|-----------|
| `action_executor.py` | ~20 методов, ~50 вызовов |
| `planning/skill.py` | ~35 вызовов |
| **Всего** | **~85 изменений** |

## ✅ Критерии Приёмки

- [ ] Все `ActionResult` заменены на `ExecutionResult`
- [ ] Класс `ActionResult` удалён
- [ ] Все тесты проходят
- [ ] Агент работает корректно
- [ ] Нет ошибок типов

## 🎯 Итог

После этого изменения:
- **Один класс** для всех результатов: `ExecutionResult`
- **Полная совместимость** между компонентами и executor
- **Чище код** и проще поддержка

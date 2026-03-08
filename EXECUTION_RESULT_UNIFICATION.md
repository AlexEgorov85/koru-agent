# Единый формат ответов компонентов Agent_v5

## Обзор

Все компоненты системы (Skills, Tools, Services) используют **единый формат** для возврата результатов выполнения — класс `ExecutionResult`.

## ExecutionResult

### Структура

```python
@dataclass
class ExecutionResult:
    status: ExecutionStatus          # Статус выполнения (COMPLETED/FAILED)
    data: Optional[Any] = None       # Данные результата (может быть Pydantic моделью)
    error: Optional[str] = None      # Описание ошибки
    metadata: Dict[str, Any] = {}    # Метаданные (время, токены, версии)
    side_effect: bool = False        # Был ли побочный эффект
```

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `status` | `ExecutionStatus` | Статус выполнения: `COMPLETED` или `FAILED` |
| `data` | `Optional[Any]` | Полезные данные результата. Может быть `dict`, `Pydantic` моделью или любым другим типом |
| `error` | `Optional[str]` | Описание ошибки если `status == FAILED` |
| `metadata` | `Dict[str, Any]` | Дополнительные метаданные: время выполнения, токены, версии контрактов |
| `side_effect` | `bool` | Флаг наличия побочного эффекта (изменение файлов, БД, контекста) |

### Factory методы

```python
# Успешный результат
ExecutionResult.success(
    data={"answer": "42"},
    metadata={"tokens": 100},
    side_effect=True
)

# Неудачный результат
ExecutionResult.failure(
    error="Не удалось выполнить запрос",
    metadata={"error_code": 500}
)
```

### Алиасы для обратной совместимости

```python
result = ExecutionResult.success(data={"key": "value"})

# Алиас на data
result.result  # Возвращает data

# Алиас на status
result.technical_success  # True если status == COMPLETED
```

### Сериализация

```python
result = ExecutionResult.success(data={"key": "value"})
result_dict = result.to_dict()
# {
#     "status": "completed",
#     "data": {"key": "value"},
#     "error": None,
#     "metadata": {},
#     "side_effect": False
# }
```

## Архитектура выполнения компонентов

### Базовый класс BaseComponent

Все компоненты наследуются от `BaseComponent` который реализует универсальный шаблон выполнения:

```python
class BaseComponent:
    async def execute(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> ExecutionResult:
        # 1. Валидация входных данных
        validated_input = self.validate_input_typed(capability.name, parameters)
        
        # 2. Выполнение бизнес-логики
        result_data = await self._execute_impl(capability, validated_input, execution_context)
        
        # 3. Валидация выходных данных
        validated_output = self.validate_output_typed(capability.name, result_data)
        
        # 4. Оборачивание в ExecutionResult
        return ExecutionResult.success(data=validated_output)
```

### Роль _execute_impl

**ВАЖНО:** Метод `_execute_impl` должен возвращать **только данные** (dict или Pydantic модель), а не `ExecutionResult`!

```python
async def _execute_impl(
    self,
    capability: Capability,
    parameters: Dict[str, Any],
    execution_context: ExecutionContext
) -> Dict[str, Any]:  # ← Возвращаем данные, не ExecutionResult!
    # Бизнес-логика
    result_data = {"answer": "42", "confidence": 0.95}
    return result_data  # ← BaseComponent.execute() сам обернёт в ExecutionResult
```

## Примеры реализации

### Skill (BookLibrarySkill)

```python
class BookLibrarySkill(BaseComponent):
    async def _execute_impl(self, capability, parameters, execution_context) -> Dict[str, Any]:
        # Выполняем бизнес-логику
        rows = await self._search_books(parameters)
        
        # Возвращаем данные (не ExecutionResult!)
        return {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": 0.5
        }
```

### Tool (SQLTool)

```python
class SQLTool(BaseComponent):
    async def _execute_impl(self, capability, parameters, execution_context) -> Dict[str, Any]:
        # Выполняем SQL запрос
        rows = await self.db.execute(parameters["sql"])
        
        # Возвращаем данные
        return {
            "rows": rows,
            "columns": self.columns,
            "rowcount": len(rows)
        }
```

### Service (PromptService)

```python
class PromptService(BaseComponent):
    async def _execute_impl(self, capability, parameters, execution_context) -> Dict[str, Any]:
        # Получаем промпт из кэша
        prompt = self.get_prompt(capability.name)
        
        # Возвращаем данные
        return {"prompt": prompt, "capability": capability.name}
```

## Типичные ошибки

### ❌ Неправильно: возврат ExecutionResult из _execute_impl

```python
async def _execute_impl(self, capability, parameters, context) -> ExecutionResult:
    # ОШИБКА: двойная обёртка!
    return ExecutionResult.success(data={"answer": "42"})
```

Это приведёт к тому что `BaseComponent.execute()` обернёт `ExecutionResult` в другой `ExecutionResult`.

### ✅ Правильно: возврат данных из _execute_impl

```python
async def _execute_impl(self, capability, parameters, context) -> Dict[str, Any]:
    # ПРАВИЛЬНО: возвращаем только данные
    return {"answer": "42"}
```

### ❌ Неправильно: использование SkillResult

```python
from core.models.data.execution import SkillResult  # ОШИБКА: класс удалён!

async def _execute_impl(self, capability, parameters, context):
    return SkillResult.success(data={"answer": "42"})
```

### ✅ Правильно: использование ExecutionResult

```python
from core.models.data.execution import ExecutionResult

# Только в BaseComponent.execute() для обёртки результата
return ExecutionResult.success(data=result_data)
```

## ActionResult в ActionExecutor

`ActionResult` используется **только внутри** `ActionExecutor` для взаимодействия между компонентами. Компоненты **не должны** возвращать `ActionResult` из `_execute_impl`.

```python
class ActionExecutor:
    async def execute_action(self, action_name, parameters, context) -> ActionResult:
        # Внутренний класс для взаимодействия компонентов
        return ActionResult(success=True, data=result_data)
```

## Миграция со SkillResult

Если ваш код использует `SkillResult`, замените его на `ExecutionResult`:

### До

```python
from core.models.data.execution import SkillResult

async def _execute_impl(self, capability, parameters, context) -> SkillResult:
    return SkillResult.success(
        data={"answer": "42"},
        metadata={"tokens": 100},
        side_effect=True
    )
```

### После

```python
async def _execute_impl(self, capability, parameters, context) -> Dict[str, Any]:
    # Возвращаем только данные
    return {"answer": "42"}
```

`BaseComponent.execute()` автоматически обернёт результат в `ExecutionResult`.

## Преимущества унификации

1. **Единообразие**: все компоненты возвращают одинаковый тип
2. **Предсказуемость**: разработчик всегда знает что `execute()` вернёт `ExecutionResult`
3. **Упрощение тестирования**: универсальные ассерты для всех компонентов
4. **Чистота архитектуры**: данные отделены от служебной информации
5. **Валидация централизована**: `BaseComponent` обрабатывает валидацию входа/выхода

## Заключение

Единый формат `ExecutionResult` обеспечивает согласованность и предсказуемость архитектуры Agent_v5. Следуйте этим правилам:

1. `_execute_impl` возвращает **только данные** (dict или Pydantic модель)
2. `BaseComponent.execute()` оборачивает результат в `ExecutionResult`
3. Используйте `ExecutionResult.success()` и `ExecutionResult.failure()` для создания результатов
4. Не используйте `SkillResult` (класс удалён)
5. Не возвращайте `ActionResult` из компонентов

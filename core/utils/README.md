# Core Utils — Утилиты для Agent_v5

## 📦 Что здесь

| Утилита | Файл | Назначение |
|---------|------|------------|
| **Error Handling** | `error_handling.py` | Декораторы и контекстные менеджеры для обработки ошибок |
| **Module Reloader** | `module_reloader.py` | Безопасная перезагрузка модулей |

## 🚀 Быстрый старт

```python
from core.utils import handle_errors, ErrorContext

# Обработка ошибок через декоратор
@handle_errors(logger=logger, component="my_service")
async def execute(self, data):
    return await self.process(data)

# Контекстный менеджер для ошибок
with ErrorContext("operation_name", logger, component="service") as ctx:
    result = await risky_operation()
```

## ⚠️ Lifecycle — больше не здесь!

**Удалено в рамках рефакторинга (2026-03-06).**

Для управления жизненным циклом компонентов используйте:

```python
from core.agent.components.lifecycle import ComponentLifecycle
from core.models.enums.component_status import ComponentStatus

class MyComponent(ComponentLifecycle):
    def __init__(self, name: str):
        super().__init__(name)

    async def initialize(self):
        await self._transition_to(ComponentStatus.INITIALIZING)
        try:
            await self._do_init()
            await self._transition_to(ComponentStatus.READY)
        except Exception:
            await self._transition_to(ComponentStatus.FAILED)
            raise
```

**Файлы:**
- `core/agent/components/lifecycle.py` — `ComponentLifecycle`
- `core/models/enums/component_status.py` — `ComponentStatus`
- `core/agent/components/base_component.py` — `BaseComponent` (наследуется от `ComponentLifecycle`)

## 📚 Документация

### handle_errors

Декоратор для автоматической обработки ошибок.

```python
from core.utils import handle_errors
import logging

logger = logging.getLogger("my_service")

class MyService:
    @handle_errors(logger=logger, component="my_service")
    async def execute(self, data):
        # Код который может выбросить исключение
        result = await self.process(data)
        return result
```

### ErrorContext

Контекстный менеджер для сбора информации об ошибках.

```python
from core.utils import ErrorContext

with ErrorContext("database_operation", logger, component="sql_service") as ctx:
    result = await db.execute(query)
```

### safe_execute / safe_execute_async

Безопасное выполнение функций с обработкой ошибок.

```python
from core.utils import safe_execute, safe_execute_async

# Синхронное
result = safe_execute(my_func, arg1, arg2, default=None, logger=logger)

# Асинхронное
result = await safe_execute_async(my_async_func, arg1, arg2, default=None)
```

## 🧪 Тестирование

```bash
pytest tests/utils/ -v
```

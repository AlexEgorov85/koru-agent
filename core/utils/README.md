# Core Utils — Утилиты для упрощения архитектуры

Этот модуль содержит переиспользуемые утилиты для устранения дублирования кода и упрощения архитектуры.

## Быстрый старт

```python
from core.utils import LifecycleManager, handle_errors, ErrorContext
```

## Компоненты

### 1. LifecycleManager

Универсальный менеджер жизненного цикла для компонентов. Устраняет дублирование кода инициализации/завершения.

**Пример использования:**

```python
from core.utils import LifecycleManager

class MyService:
    def __init__(self, name: str):
        self.lifecycle = LifecycleManager(name, logger=my_logger)
    
    async def initialize(self) -> bool:
        async def custom_init():
            # Кастомная логика инициализации
            await self.connect_to_database()
            return True
        
        return await self.lifecycle.initialize(custom_init)
    
    async def shutdown(self) -> None:
        async def custom_shutdown():
            await self.disconnect_from_database()
        
        await self.lifecycle.shutdown(custom_shutdown)
```

**Где используется:**
- `BaseService`
- `BaseSkill`
- `BaseTool`
- Behavior patterns

### 2. DependencyResolver

Универсальный резолвер зависимостей для компонентов.

**Пример использования:**

```python
from core.utils import DependencyResolver

class MyService(BaseService):
    DEPENDENCIES = ["prompt_service", "contract_service"]
    
    def __init__(self, name: str, app_context):
        self.resolver = DependencyResolver(
            name,
            get_dependency_func=self.get_dependency,
            logger=self.logger
        )
    
    async def initialize(self) -> bool:
        # Разрешение зависимостей
        await self.resolver.resolve(self.DEPENDENCIES)
        
        # Получение зависимости
        prompt_service = self.resolver.get("prompt_service")
```

### 3. InputValidator

Валидатор входных данных.

**Пример использования:**

```python
from core.utils import InputValidator

# Валидация обязательных полей
if not InputValidator.validate_required_fields(
    data,
    required_fields=["query", "max_rows"],
    component_name="sql_service"
):
    raise ValueError("Missing required fields")

# Санитизация строки
clean_query = InputValidator.sanitize_string(user_input)
```

### 4. handle_errors (декоратор)

Автоматическая обработка ошибок в методах.

**Пример использования:**

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
    
    @handle_errors(logger=logger, component="my_service", default_error_type="Validation")
    def validate(self, data):
        # Синхронный метод
        pass
```

**Преимущества:**
- Автоматическое логирование ошибок
- Консистентный формат ошибок
- Поддержка async/sync методов
- Конвертация в AgentError

### 5. ErrorContext (context manager)

Контекстный менеджер для сбора информации об ошибках.

**Пример использования:**

```python
from core.utils import ErrorContext

with ErrorContext("database_operation", logger, component="sql_service") as ctx:
    # Код который может выбросить исключение
    result = await db.execute(query)

# Если произошло исключение, оно будет залогировано с контекстом
```

### 6. ErrorCollector

Коллектор для сбора множественных ошибок.

**Пример использования:**

```python
from core.utils import ErrorCollector

collector = ErrorCollector(logger)

# Сбор ошибок валидации
for item in items:
    try:
        validate(item)
    except ValidationError as e:
        collector.add_error(e)

# Выбросить если есть ошибки
collector.raise_if_any("Validation failed for some items")
```

### 7. safe_execute / safe_execute_async

Безопасное выполнение функций с обработкой ошибок.

**Пример использования:**

```python
from core.utils import safe_execute, safe_execute_async

# Синхронное
result = safe_execute(my_func, arg1, arg2, default=None, logger=logger)

# Асинхронное
result = await safe_execute_async(my_async_func, arg1, arg2, default=None)
```

## Архитектурные принципы

1. **DRY (Don't Repeat Yourself)** — утилиты устраняют дублирование кода
2. **Single Responsibility** — каждая утилита решает одну задачу
3. **Composability** — утилиты можно комбинировать
4. **Zero Dependencies** — утилиты не зависят от бизнес-логики

## Тестирование

Все утилиты покрыты тестами в `tests/utils/`.

```bash
pytest tests/utils/ -v
```

## Расширение

Для добавления новой утилиты:

1. Создайте файл в `core/utils/`
2. Добавьте экспорт в `__init__.py`
3. Напишите тесты
4. Обновите этот README

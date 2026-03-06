# Лучшие практики асинхронности

**Версия:** 1.0  
**Дата:** 6 марта 2026 г.

---

## 1. Управление фоновыми задачами

### ✅ Правильно

```python
class MyService:
    def __init__(self):
        self._background_tasks: Set[asyncio.Task] = set()
    
    async def start_background_task(self):
        task = asyncio.create_task(self._do_something())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
    
    async def shutdown(self):
        # Завершение всех задач
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
```

### ❌ Неправильно

```python
# Fire-and-forget (задача может потеряться)
asyncio.create_task(self._do_something())

# Без сохранения ссылки
task = asyncio.create_task(self._do_something())
# task не сохраняется и может быть удалён сборщиком мусора
```

---

## 2. Обработка ошибок

### ✅ Правильно

```python
# С декоратором handle_errors
@error_handler.handle_errors(component="my_component", reraise=True)
async def my_async_function():
    # ... код ...
    pass

# Ручная обработка
try:
    await some_operation()
except Exception as e:
    await error_handler.handle(e, context)
    raise
```

### ❌ Неправильно

```python
# ❌ Синхронные функции с декоратором
@error_handler.handle_errors(component="test")
def sync_function():  # TypeError!
    pass

# ❌ asyncio.run() внутри async контекста
async def outer():
    asyncio.run(inner())  # RuntimeError!
```

---

## 3. Файловые операции

### ✅ Правильно

```python
import aiofiles

# Чтение
async with aiofiles.open('file.txt', 'r') as f:
    content = await f.read()

# Запись
async with aiofiles.open('file.txt', 'w') as f:
    await f.write('data')

# Синхронные операции в executor
loop = asyncio.get_running_loop()
data = await loop.run_in_executor(None, yaml.safe_load, content)
```

### ❌ Неправильно

```python
# Блокировка event loop
with open('file.txt', 'r') as f:
    content = f.read()  # Блокирует все корутины!

# Синхронный YAML парсинг
import yaml
data = yaml.safe_load(content)  # Может занять много времени
```

---

## 4. Жизненный цикл компонентов

### ✅ Правильно

```python
# Инициализация с проверками
class MyComponent(LifecycleMixin):
    async def initialize(self):
        await self._transition_to(ComponentState.INITIALIZING)
        try:
            await self._do_init()
            await self._transition_to(ComponentState.READY)
        except Exception as e:
            await self._transition_to(ComponentState.FAILED)
            raise
    
    def do_work(self):
        self.ensure_ready()  # Проверка перед работой
        # ... бизнес-логика
```

### ❌ Неправильно

```python
# Без проверки состояния
def do_work(self):
    # Может вызвать ошибку если не инициализирован
    self._do_something()

# Прямое изменение состояния
self._state = ComponentState.READY  # ❌
# Используйте: await self._transition_to(ComponentState.READY)
```

---

## 5. Event Bus

### ✅ Правильно

```python
# Публикация с обработкой ошибок
try:
    await event_bus.publish(event_type, data)
except Exception as e:
    logger.error(f"Failed to publish event: {e}")

# Подписка с фильтром
event_bus.subscribe(
    EventType.AGENT_STARTED,
    handler,
    domain=EventDomain.AGENT,
    session_id="session_123"
)
```

### ❌ Неправильно

```python
# Fire-and-forget публикация
asyncio.create_task(event_bus.publish(...))  # Может потеряться

# Подписка без фильтра (получает все события)
event_bus.subscribe(EventType.AGENT_STARTED, handler)
# Лучше указать domain или session_id
```

---

## 6. Логирование

### ✅ Правильно

```python
# Асинхронное логирование
await self.event_bus_logger.info("Operation started")
await self.event_bus_logger.error(f"Error: {e}", exc_info=True)

# Синхронное логирование (если необходимо)
self._safe_log_sync("info", "Message")
```

### ❌ Неправильно

```python
# Стандартное logging в async коде
import logging
logger = logging.getLogger(__name__)
logger.info("Message")  # Может блокировать

# Логирование без проверки
self.event_bus_logger.info("Message")  # Может быть None!
# Проверяйте: if self.event_bus_logger: ...
```

---

## 7. Таймауты

### ✅ Правильно

```python
# С таймаутом
try:
    result = await asyncio.wait_for(
        long_operation(),
        timeout=30.0
    )
except asyncio.TimeoutError:
    logger.error("Operation timed out")

# Семфор для ограничения параллелизма
semaphore = asyncio.Semaphore(5)

async def limited_operation():
    async with semaphore:
        await do_something()
```

### ❌ Неправильно

```python
# Без таймаута
result = await long_operation()  # Может висеть бесконечно

# Без ограничения параллелизма
tasks = [do_something() for _ in range(1000)]
await asyncio.gather(*tasks)  # Может перегрузить систему
```

---

## 8. Graceful Shutdown

### ✅ Правильно

```python
class MyService:
    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._background_tasks: Set[asyncio.Task] = set()
    
    async def run(self):
        while not self._shutdown_event.is_set():
            try:
                await self._do_work()
            except asyncio.CancelledError:
                break
    
    async def shutdown(self):
        self._shutdown_event.set()
        
        # Отмена задач
        for task in self._background_tasks:
            task.cancel()
        
        # Ожидание завершения
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
```

### ❌ Неправильно

```python
# Без обработки отмены
async def run(self):
    while True:
        await self._do_work()  # Не реагирует на shutdown

# Без ожидания завершения задач
async def shutdown(self):
    for task in self._background_tasks:
        task.cancel()
    # Задачи не дожаты!
```

---

## 9. Проверка кода

### Чек-лист для код-ревью

- [ ] Все `create_task()` сохраняют ссылку
- [ ] Нет `asyncio.run()` в async коде
- [ ] Файловые операции используют `aiofiles`
- [ ] Компоненты проверяют состояние через `ensure_ready()`
- [ ] Есть обработка `CancelledError`
- [ ] Реализован graceful shutdown
- [ ] Таймауты на длительных операциях
- [ ] Логирование через `EventBusLogger`

---

## 10. Диагностика проблем

### Проблема: Задачи не завершаются

**Решение:**
```python
# Добавьте сохранение ссылок
self._tasks.add(task)
task.add_done_callback(self._tasks.discard)

# В shutdown() дожидайтесь завершения
await asyncio.gather(*self._tasks, return_exceptions=True)
```

### Проблема: Блокировка event loop

**Решение:**
```python
# Найдите синхронные операции
# Замените на асинхронные или executor
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, sync_func, args)
```

### Проблема: Потеря логов

**Решение:**
```python
# Проверяйте инициализацию логгера
if self.event_bus_logger:
    await self.event_bus_logger.info("Message")
else:
    # Fallback на print или buffer
    print(f"[BUFFERED] Message")
```

---

## 11. Приложения

### A. Полезные утилиты

```python
# Декоратор для таймаута
def with_timeout(timeout: float):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout)
        return wrapper
    return decorator

# Контекстный менеджер для семафора
@asynccontextmanager
async def rate_limit(semaphore: asyncio.Semaphore):
    async with semaphore:
        yield
```

### B. Связанная документация

- [lifecycle.md](./lifecycle.md) - Жизненный цикл компонентов
- [LOGGING_GUIDE.md](./LOGGING_GUIDE.md) - Руководство по логированию
- [EVENT_BUS_MIGRATION.md](./EVENT_BUS_MIGRATION.md) - Миграция Event Bus

# 🪵 Универсальный механизм логирования - Документация

## 📋 Обзор

Универсальный механизм логирования предоставляет централизованный способ логирования для всех компонентов системы (навыков, инструментов, сервисов).

### Основные возможности

- ✅ **Единая конфигурация** - централизованное управление настройками логирования
- ✅ **Автоматическое логирование** - декораторы для логирования без ручного кода
- ✅ **Ручное логирование** - миксин для детального контроля
- ✅ **Санитизация данных** - автоматическое удаление чувствительных данных
- ✅ **EventBus интеграция** - публикация событий выполнения
- ✅ **Гибкое форматирование** - текстовый и JSON форматы

---

## 📁 Структура модуля

```
core/infrastructure/logging/
├── __init__.py              # Экспорт публичного API
├── log_config.py            # Конфигурация логирования
├── log_decorator.py         # Декоратор @log_execution
├── log_mixin.py             # LogComponentMixin
├── log_formatter.py         # LogFormatter
```

---

## 🚀 Быстрый старт

### 1. Базовое использование

```python
from core.infrastructure.logging import log_execution, LogComponentMixin

# Вариант A: Декоратор для автоматического логирования
@log_execution()
async def my_function(param1, param2):
    return result

# Вариант B: Миксин для ручного управления
class MyComponent(LogComponentMixin):
    async def execute(self, params):
        self.log_start("execute", params)
        try:
            result = await self._execute(params)
            self.log_success("execute", result)
            return result
        except Exception as e:
            self.log_error("execute", e)
            raise
```

### 2. Настройка конфигурации

```python
from core.infrastructure.logging import configure_logging, LogConfig, LogLevel

configure_logging(LogConfig(
    level=LogLevel.DEBUG,
    log_parameters=True,
    log_result=False,  # Не логировать результаты
    exclude_parameters=['password', 'api_key', 'token'],
))
```

---

## 📖 API Reference

### LogConfig

Конфигурация логирования.

```python
from core.infrastructure.logging import LogConfig, LogLevel

config = LogConfig(
    # Уровень логирования
    level=LogLevel.INFO,
    
    # Формат строки лога
    format_string="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    
    # Что логировать
    log_execution_start=True,
    log_execution_end=True,
    log_parameters=True,
    log_result=True,
    log_errors=True,
    log_duration=True,
    
    # Исключения (чувствительные данные)
    exclude_parameters=['password', 'token', 'api_key', 'secret'],
    
    # Ограничения длины
    max_parameter_length=1000,
    max_result_length=5000,
    
    # EventBus интеграция
    enable_event_bus=True,
)
```

### @log_execution

Декоратор для автоматического логирования.

```python
from core.infrastructure.logging import log_execution

# Базовое использование
@log_execution()
async def my_func():
    pass

# С пользовательским именем операции
@log_execution(operation_name="Custom Operation Name")
def sync_func():
    pass

# С настройками логирования
@log_execution(
    log_level="DEBUG",
    log_params=True,
    log_result=False
)
async def sensitive_func(secret_data):
    pass
```

### LogComponentMixin

Миксин для добавления логирования в классы.

```python
from core.infrastructure.logging import LogComponentMixin

class MyComponent(LogComponentMixin):
    def __init__(self):
        super().__init__()  # Обязательно!
    
    def my_method(self):
        # Логирование начала
        self.log_start("operation_name", {'param': 'value'})
        
        # Логирование успеха
        self.log_success("operation_name", {'result': 'ok'}, duration_ms=100.5)
        
        # Логирование ошибки
        try:
            pass
        except Exception as e:
            self.log_error("operation_name", e, duration_ms=50.0)
```

#### Методы миксина

| Метод | Описание |
|-------|----------|
| `log_start(operation, parameters)` | Логирование начала операции |
| `log_success(operation, result, duration_ms)` | Логирование успеха |
| `log_error(operation, error, duration_ms)` | Логирование ошибки |
| `log_with_timing(operation, func, *args, **kwargs)` | Логирование с замером времени (синхронное) |
| `async_log_with_timing(operation, func, *args, **kwargs)` | Логирование с замером времени (асинхронное) |

### LogFormatter

Форматтер для логов.

```python
from core.infrastructure.logging import LogFormatter
import logging

# Текстовый формат с цветами
formatter = LogFormatter(
    format_type="text",
    use_colors=True,
    include_timestamp=True,
    include_level=True,
    include_logger_name=True
)

# JSON формат
json_formatter = LogFormatter(format_type="json")

# Настройка handler
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)
```

### setup_logging

Быстрая настройка логирования.

```python
from core.infrastructure.logging import setup_logging
import logging

setup_logging(
    level=logging.INFO,
    format_type="text",  # или "json"
    log_file="logs/agent.log",  # опционально
    use_colors=True
)
```

---

## 🔒 Санитизация данных

Автоматическое удаление чувствительных данных:

```python
from core.infrastructure.logging import LogConfig, _sanitize_params

config = LogConfig()
params = {
    'username': 'john',
    'password': 'secret123',  # Будет заменено на ***REDACTED***
    'api_key': 'key-12345',   # Будет заменено на ***REDACTED***
}

sanitized = _sanitize_params(params, config)
# {'username': 'john', 'password': '***REDACTED***', 'api_key': '***REDACTED***'}
```

### Поля для исключения

По умолчанию исключаются:
- `password`
- `token`
- `api_key`
- `secret`
- `credential`

Добавьте свои:
```python
config = LogConfig(
    exclude_parameters=['password', 'custom_secret', 'auth_token']
)
```

---

## 📊 EventBus интеграция

Новые типы событий:

```python
from core.infrastructure.event_bus.event_bus import EventType

EventType.EXECUTION_STARTED      # Начало выполнения
EventType.EXECUTION_COMPLETED    # Успешное завершение
EventType.EXECUTION_FAILED       # Ошибка выполнения
EventType.COMPONENT_INITIALIZED  # Инициализация компонента
EventType.COMPONENT_SHUTDOWN     # Завершение компонента
```

### Подписка на события

```python
from core.infrastructure.event_bus.event_bus import get_event_bus, EventType

event_bus = get_event_bus()

async def on_execution_started(event):
    print(f"Execution started: {event.data}")

event_bus.subscribe(EventType.EXECUTION_STARTED, on_execution_started)
```

---

## 📝 Примеры использования

### Пример 1: Логирование в навыке

```python
from core.components.skills.base_skill import BaseSkill
from core.infrastructure.logging import log_execution

class MySkill(BaseSkill):
    @log_execution()
    async def _execute_impl(self, capability, parameters, context):
        # Автоматическое логирование
        return {"status": "completed"}
```

### Пример 2: Логирование в инструменте

```python
from core.components.tools.base_tool import BaseTool
from core.infrastructure.logging import LogComponentMixin

class MyTool(BaseTool, LogComponentMixin):
    async def _execute_impl(self, capability, parameters, context):
        self.log_start("execute", {'tool': self.name})
        try:
            result = await self.perform_action(parameters)
            self.log_success("execute", result)
            return result
        except Exception as e:
            self.log_error("execute", e)
            raise
```

### Пример 3: Логирование в сервисе

```python
from core.components.services.base_service import BaseService
from core.infrastructure.logging import log_execution

class MyService(BaseService):
    @log_execution(operation_name="Database Query")
    async def query(self, sql: str):
        # Логирование с пользовательским именем
        return await self.db.execute(sql)
```

### Пример 4: Кастомная конфигурация

```python
from core.infrastructure.logging import configure_logging, LogConfig, LogLevel

# Для отладки
configure_logging(LogConfig(
    level=LogLevel.DEBUG,
    log_parameters=True,
    log_result=True,
    enable_event_bus=True
))

# Для продакшена (без чувствительных данных)
configure_logging(LogConfig(
    level=LogLevel.INFO,
    log_parameters=False,
    log_result=False,
    exclude_parameters=['password', 'token', 'api_key', 'user_data'],
    enable_event_bus=True
))
```

---

## 🧪 Тестирование

```python
import pytest
from core.infrastructure.logging import LogConfig, configure_logging

@pytest.fixture
def test_logging_config():
    """Конфигурация для тестов."""
    original = get_log_config()
    configure_logging(LogConfig(level=LogLevel.DEBUG))
    yield
    configure_logging(original)

def test_my_function(test_logging_config, caplog):
    with caplog.at_level(logging.DEBUG):
        my_function()
    assert "START:" in caplog.text
```

---

## 🎯 Лучшие практики

### ✅ Делайте

- Используйте декоратор `@log_execution()` для автоматического логирования
- Добавляйте чувствительные поля в `exclude_parameters`
- Используйте `LogComponentMixin` для детального контроля
- Настраивайте уровень логирования через конфигурацию

### ❌ Не делайте

- Не логируйте пароли и токены без санитизации
- Не создавайте свои логгеры вручную (используйте миксин)
- Не дублируйте код логирования в каждом методе

---

## 🔧 Конфигурационный файл

`core/config/logging_config.yaml`:

```yaml
logging:
  level: INFO
  format_type: text
  use_colors: true
  
  log_execution_start: true
  log_execution_end: true
  log_parameters: true
  log_result: true
  log_errors: true
  log_duration: true
  
  exclude_parameters:
    - password
    - token
    - api_key
  
  max_parameter_length: 1000
  max_result_length: 5000
  
  enable_event_bus: true
```

---

## 📈 Метрики и мониторинг

Логирование публикует события в EventBus:

- **execution.started** - начало выполнения
- **execution.completed** - успешное завершение
- **execution.failed** - ошибка выполнения

Эти события могут быть использованы для:
- Сбора метрик производительности
- Отслеживания ошибок
- Анализа поведения компонентов

---

## 🐛 Отладка

### Включение подробного логирования

```python
from core.infrastructure.logging import configure_logging, LogConfig, LogLevel

configure_logging(LogConfig(
    level=LogLevel.DEBUG,
    log_parameters=True,
    log_result=True
))
```

### Просмотр логов

```python
import logging

# Настройка консольного вывода
from core.infrastructure.logging import setup_logging
setup_logging(level=logging.DEBUG, format_type="text", use_colors=True)
```

---

## 📚 Дополнительные ресурсы

- [Python logging documentation](https://docs.python.org/3/library/logging.html)
- [EventBus документация](core/infrastructure/event_bus/event_bus.py)
- [Тесты](tests/unit/test_logging_module/test_logging.py)

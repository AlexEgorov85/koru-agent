# Руководство по использованию MetricsPublisher

## Обзор

`MetricsPublisher` - это тонкая обёртка для унифицированной публикации метрик в системе. Он предоставляет единый, типизированный API для работы с метриками, используя существующие компоненты без излишней сложности.

## Основные возможности

- **Единый API** для всех типов метрик (GAUGE, COUNTER, HISTOGRAM)
- **Типизированные параметры** с валидацией
- **Интеграция** с существующим `IMetricsStorage` и `UnifiedEventBus`
- **Контекстный менеджер** для измерения времени выполнения
- **Декоратор** для автоматического сбора метрик функций
- **Обработка ошибок** и graceful degradation

## Установка и импорт

```python
from core.application.services.metrics_publisher import (
    MetricsPublisher, 
    MetricsContext, 
    record_metrics
)
from core.infrastructure.metrics_storage import FileSystemMetricsStorage
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
```

## Быстрый старт

### Базовое использование

```python
# Инициализация
storage = FileSystemMetricsStorage(Path('data/metrics'))
event_bus = UnifiedEventBus()  # Опционально
publisher = MetricsPublisher(storage, event_bus)

# Публикация метрик
await publisher.gauge("accuracy", 0.95, capability="sql_generation")
await publisher.counter("execution_count", capability="data_analysis")
await publisher.histogram("execution_time_ms", 150.5, capability="sql_generation")
```

### Типы метрик

#### GAUGE - текущие значения
```python
# Точность, температура, загрузка CPU
await publisher.gauge("accuracy", 0.95, tags={"model": "gpt-4"})
await publisher.gauge("temperature", 0.7, capability="prompt_optimization")
```

#### COUNTER - счётчики
```python
# Количество выполнений, ошибок, запросов
await publisher.counter("execution_count")  # По умолчанию value=1.0
await publisher.counter("error_count", 3.0, tags={"error_type": "timeout"})
```

#### HISTOGRAM - распределения
```python
# Время выполнения, использование памяти, размер ответа
await publisher.histogram("execution_time_ms", 150.5)
await publisher.histogram("memory_usage_mb", 128.0)
```

### Параметры метрик

Все методы поддерживают общие параметры:

```python
await publisher.gauge(
    name="metric_name",
    value=1.0,
    agent_id="agent_1",           # Идентификатор агента
    capability="sql_generation", # Название способности
    tags={"key": "value"},       # Дополнительные теги
    session_id="session_123",    # Идентификатор сессии
    correlation_id="corr_456",   # Идентификатор корреляции
    version="v1.2.3",            # Версия промпта/контракта
    timestamp=datetime.now(),    # Время измерения
    publish_event=True           # Публиковать ли в EventBus
)
```

## Продвинутое использование

### Контекстный менеджер для измерения времени

```python
async with MetricsContext(
    publisher, 
    "operation_time_ms",
    capability="data_processing",
    agent_id="batch_processor",
    tags={"size": "large"}
) as timer:
    # Выполнение операции
    result = await process_data()
    print(f"Прошло времени: {timer.get_elapsed_ms():.2f} мс")

# Метрика публикуется автоматически при выходе из контекста
```

### Декоратор для функций

```python
@record_metrics(
    publisher, 
    "api_call_duration",
    capability="external_api",
    agent_id="api_client",
    tags={"version": "v1"}
)
async def call_api(endpoint: str, data: dict):
    """Функция с автоматическим сбором метрик."""
    response = await http_client.post(endpoint, json=data)
    return response.json()

# При вызове метрика времени выполнения публикуется автоматически
result = await call_api("/users", {"action": "get"})
```

### Кастомные типы метрик

```python
# Использование строкового типа
await publisher.record_custom(
    metric_type="gauge",  # Или MetricType.GAUGE
    name="custom_metric",
    value=42.0,
    capability="custom_processing"
)
```

## Интеграция с существующими сервисами

### Замена прямого использования хранилища

**Было:**
```python
# Старый способ
metric = MetricRecord(
    agent_id="agent_1",
    capability="sql_generation",
    metric_type=MetricType.GAUGE,
    name="accuracy",
    value=0.95
)
await storage.record(metric)
```

**Стало:**
```python
# Новый способ
await publisher.gauge(
    "accuracy", 0.95, 
    capability="sql_generation", 
    agent_id="agent_1"
)
```

### Интеграция с EventBus

```python
# MetricsPublisher автоматически публикует события в EventBus
# при условии, что event_bus передан в конструктор

publisher = MetricsPublisher(storage, event_bus)

# Эта метрика будет сохранена в хранилище И опубликована в EventBus
await publisher.gauge("accuracy", 0.95)
```

## Обработка ошибок

### Graceful degradation

```python
# При отсутствии EventBus публикация продолжает работать
publisher_without_eventbus = MetricsPublisher(storage)

# Метрика сохранится в хранилище, но событие не будет опубликовано
await publisher_without_eventbus.gauge("test_metric", 1.0)

# Явное отключение публикации событий
await publisher.gauge("test_metric", 1.0, publish_event=False)
```

### Валидация параметров

```python
try:
    # Неверный тип метрики вызовет ValueError
    await publisher.record_custom("invalid_type", "test", 1.0)
except ValueError as e:
    print(f"Ошибка валидации: {e}")
```

## Тестирование

### Mocking в тестах

```python
@pytest.fixture
def mock_publisher():
    publisher = Mock()
    publisher.gauge = AsyncMock()
    publisher.counter = AsyncMock()
    publisher.histogram = AsyncMock()
    return publisher

async def test_service_with_metrics(mock_publisher):
    service = MyService(mock_publisher)
    await service.process()
    
    # Проверка вызова метрик
    mock_publisher.gauge.assert_called_with("accuracy", 0.95, capability="test")
```

### Интеграционные тесты

```python
async def test_metrics_integration():
    # Использование реального хранилища
    storage = FileSystemMetricsStorage(Path('test_metrics'))
    publisher = MetricsPublisher(storage)
    
    await publisher.gauge("test_metric", 1.0)
    
    # Проверка сохранения метрики
    records = await storage.get_records("", None, None, 10)
    assert len(records) == 1
    assert records[0].name == "test_metric"
```

## Best Practices

### 1. Использование тегов

```python
# Хорошо: Использование тегов для дополнительного контекста
await publisher.gauge(
    "accuracy", 0.95,
    tags={
        "model": "gpt-4",
        "dataset": "books",
        "prompt_version": "v2.1"
    }
)

# Плохо: Создание отдельных метрик для каждого варианта
await publisher.gauge("accuracy_gpt4_books", 0.95)
await publisher.gauge("accuracy_gpt3_books", 0.85)
```

### 2. Семантические имена метрик

```python
# Хорошо: Описательные имена
await publisher.histogram("sql_generation_time_ms", 150.5)
await publisher.counter("api_http_errors", tags={"status_code": "500"})

# Плохо: Неясные имена
await publisher.histogram("time", 150.5)
await publisher.counter("errors")
```

### 3. Единицы измерения

```python
# Явное указание единиц измерения в имени
await publisher.histogram("response_size_bytes", 1024)
await publisher.histogram("execution_time_ms", 150.5)
await publisher.gauge("memory_usage_mb", 128.0)
```

## Миграция с старого API

### Поэтапная миграция

1. **Добавление MetricsPublisher** в существующие сервисы
2. **Постепенная замена** прямых вызовов storage.record()
3. **Тестирование** новой функциональности
4. **Удаление** старого кода после полного перехода

### Пример миграции

**Было в сервисе:**
```python
class MyService:
    def __init__(self, storage: IMetricsStorage, event_bus: UnifiedEventBus):
        self.storage = storage
        self.event_bus = event_bus
    
    async def process(self):
        # Старый способ
        metric = MetricRecord(...)
        await self.storage.record(metric)
        await self.event_bus.publish(...)
```

**Стало:**
```python
class MyService:
    def __init__(self, metrics_publisher: MetricsPublisher):
        self.publisher = metrics_publisher
    
    async def process(self):
        # Новый способ
        await self.publisher.gauge(...)
        # EventBus публикация обрабатывается автоматически
```

## Производительность

`MetricsPublisher` разработан с учётом производительности:

- **Асинхронные операции** - не блокирует основной поток
- **Минимальные накладные расходы** - тонкая обёртка над существующими компонентами
- **Опциональная EventBus интеграция** - можно отключить если не нужна

## Мониторинг и отладка

Для мониторинга работы MetricsPublisher можно использовать:

1. **Логи хранилища** - проверка сохранения метрик
2. **События EventBus** - мониторинг публикации событий
3. **Метрики самого MetricsPublisher** - сбор статистики использования

## Заключение

`MetricsPublisher` предоставляет современный, типизированный и удобный API для работы с метриками, сохраняя совместимость с существующей инфраструктурой. Его использование упрощает код, улучшает тестируемость и обеспечивает единообразие в публикации метрик across всей codebase.
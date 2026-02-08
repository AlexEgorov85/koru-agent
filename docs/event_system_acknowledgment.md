# Механизм подтверждения доставки событий

## Обзор

Новый механизм подтверждения доставки событий (AcknowledgedEventSystem) обеспечивает надежную доставку событий с возможностью отслеживания статуса обработки и автоматическими повторными попытками для неподтвержденных событий.

## Основные возможности

### 1. Подтверждение доставки
- Каждое событие получает уникальный ID при публикации
- Обработчики могут подтверждать успешную обработку событий
- Система отслеживает статус каждого события

### 2. Автоматические повторные попытки
- Неподтвержденные события автоматически повторно отправляются
- Настройка максимального количества повторных попыток
- Настройка задержки между попытками

### 3. Совместимость
- Полная обратная совместимость с существующим кодом
- Новые методы не влияют на старую функциональность
- Постепенная миграция возможна без изменений в существующем коде

## Использование

### Подписка с подтверждением

```python
from infrastructure.event_system_with_ack import get_ack_event_system
from domain.abstractions.event_types import EventType

event_system = get_ack_event_system()

async def task_completion_handler(event):
    # Обработка события
    print(f"Обработка события: {event.data}")
    
    # Возвращаем True при успешной обработке
    # False или исключение означает неудачу
    return True

# Подписка с подтверждением
event_system.subscribe_with_ack(EventType.TASK_EXECUTION, task_completion_handler)
```

### Публикация с подтверждением

```python
# Публикация события с отслеживанием подтверждения
event_id = await event_system.publish_with_ack(
    EventType.TASK_EXECUTION,
    "my_component",
    {"task_id": 123, "status": "completed"}
)

# Проверка статуса события
status = await event_system.get_event_status(event_id)
print(f"Статус события {event_id}: {status}")
```

### Запуск мониторинга повторных попыток

```python
# Запуск фонового процесса для обработки retry
await event_system.start_retry_monitoring()

# Остановка фонового процесса
await event_system.stop_retry_monitoring()
```

## Статусы событий

- `PENDING` - событие отправлено, но еще не подтверждено
- `CONFIRMED` - событие подтверждено всеми обработчиками
- `FAILED` - событие не было обработано успешно
- `RETRYING` - событие находится в процессе повторной отправки

## Конфигурация

При создании системы событий можно настроить:

- `max_retries` - максимальное количество повторных попыток (по умолчанию 3)
- `retry_delay` - задержка между попытками в секундах (по умолчанию 5.0)
- `filters` - фильтры событий
- `validators` - валидаторы событий
- `rate_limiter` - ограничитель частоты

## Пример полного использования

```python
import asyncio
from infrastructure.event_system_with_ack import get_ack_event_system
from domain.abstractions.event_types import EventType

async def main():
    # Получаем экземпляр системы событий с подтверждением
    event_system = get_ack_event_system()
    
    # Запускаем мониторинг повторных попыток
    await event_system.start_retry_monitoring()
    
    # Определяем обработчик с подтверждением
    async def my_handler(event):
        print(f"Обработка события: {event.data}")
        # Имитация обработки
        await asyncio.sleep(0.1)
        print(f"Событие обработано: {event.data}")
        return True  # Подтверждаем успешную обработку
    
    # Подписываемся на событие с подтверждением
    event_system.subscribe_with_ack(EventType.INFO, my_handler)
    
    # Публикуем событие с подтверждением
    event_id = await event_system.publish_with_ack(
        EventType.INFO,
        "my_app",
        {"message": "Hello with ACK"}
    )
    
    print(f"Событие опубликовано: {event_id}")
    
    # Ждем немного для обработки
    await asyncio.sleep(1)
    
    # Проверяем статус
    status = await event_system.get_event_status(event_id)
    print(f"Статус: {status}")
    
    # Останавливаем мониторинг
    await event_system.stop_retry_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
```

## Миграция с существующего кода

Существующий код продолжает работать без изменений:

```python
# Это по-прежнему работает
from infrastructure.event_system import get_event_system

event_system = get_event_system()
event_system.subscribe(EventType.INFO, handler)
await event_system.publish(EventType.INFO, "source", data)
```

Новые методы также доступны в базовом классе:

```python
# Эти методы теперь доступны в обоих реализациях
event_id = await event_system.publish_with_ack(EventType.INFO, "source", data)
event_system.subscribe_with_ack(EventType.INFO, handler_with_ack)
```

## Архитектурные преимущества

1. **Надежность** - гарантия обработки важных событий
2. **Мониторинг** - возможность отслеживания статуса событий
3. **Автоматизация** - автоматические повторные попытки
4. **Совместимость** - без изменений в существующем коде
5. **Гибкость** - настраиваемые параметры retry
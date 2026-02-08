# Целевая архитектура системы событий

## Общие принципы

1. **Минимальная абстракция**: Один интерфейс `IEventPublisher` + одна основная реализация `EventSystem`
2. **Единая точка ответственности**: Публикация событий только из `AgentRuntime` и `SystemOrchestrator`
3. **Композиция вместо наследования**: Фильтры, лимитеры и валидаторы как компоненты, а не наследуемые классы
4. **Четкое разделение обязанностей**: Каждый компонент имеет одну четко определенную роль

## Компоненты целевой архитектуры

### 1. IEventPublisher (Интерфейс)
- **Расположение**: `domain/abstractions/event_types.py`
- **Ответственность**: Определение контракта для публикации событий
- **Методы**:
  - `publish(event_type: EventType, source: str, data: Any)`
  - `subscribe(event_type: EventType, handler: Callable)`

### 2. EventSystem (Основная реализация)
- **Расположение**: `infrastructure/gateways/event/event_system.py`
- **Ответственность**: Управление событиями, подписками, обработка
- **Функциональность**:
  - Публикация событий
  - Управление подписчиками
  - Поддержка middleware для обработки событий

### 3. Компоненты фильтрации (Composition-based)
- **Расположение**: `infrastructure/event_filters/`
- **Ответственность**: Фильтрация событий по различным критериям
- **Компоненты**:
  - `SecurityEventFilter` - фильтрация чувствительных данных
  - `SizeLimitFilter` - ограничение размера событий
  - `RateLimiter` - ограничение частоты публикации

### 4. EventValidator
- **Расположение**: `infrastructure/event_validation/`
- **Ответственность**: Валидация событий перед публикацией

## Сценарии использования в новой архитектуре

### 1. Публикация событий
```python
# Только в AgentRuntime и SystemOrchestrator
event_system = EventSystem(filters=[SecurityEventFilter(), SizeLimitFilter()])
await event_system.publish(EventType.INFO, "AgentRuntime", {"message": "Task completed"})
```

### 2. Подписка на события
```python
# В компонентах, которым нужно реагировать на события
event_system.subscribe(EventType.TASK_EXECUTION, handler_function)
```

### 3. Композиция фильтров
```python
# При создании EventSystem
filters = [
    SecurityEventFilter(),
    SizeLimitFilter(max_size=1024*1024),  # 1MB limit
    RateLimiter(requests_per_second=100)
]
event_system = EventSystem(filters=filters)
```

## Разделение ответственностей

| Компонент | Ответственность |
|-----------|----------------|
| EventSystem | Публикация и маршрутизация событий |
| SecurityEventFilter | Фильтрация чувствительных данных |
| SizeLimitFilter | Ограничение размера событий |
| RateLimiter | Ограничение частоты публикации |
| EventValidator | Валидация событий перед публикацией |

## Миграционный план

1. **Создать новую реализацию** EventSystem с поддержкой композиции
2. **Обновить все компоненты** для использования новой архитектуры
3. **Централизовать публикацию** событий в AgentRuntime и SystemOrchestrator
4. **Удалить избыточные абстракции** после миграции
5. **Обновить тесты** для работы с новой архитектурой
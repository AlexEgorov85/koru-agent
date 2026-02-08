# Анализ системы событий

## Текущая архитектура

### Найденные компоненты:

1. **IEventPublisher** (интерфейс) - в `domain/abstractions/event_types.py`
   - Определяет контракт для публикации событий
   - Имеет методы `publish()` и `subscribe()`

2. **EventSystem** (реализация) - в `infrastructure/gateways/event/event_system.py`
   - Основная реализация шины событий
   - Поддерживает middleware, фильтрацию, глобальные обработчики
   - Имеет глобальный экземпляр

3. **EventPublisherAdapter** (адаптер) - в `infrastructure/gateways/event/event_publisher_adapter.py`
   - Адаптирует EventSystem к интерфейсу IEventPublisher
   - Добавляет уровень абстракции без явной необходимости

4. **EventBusAdapter** (адаптер) - в `infrastructure/gateways/event/event_bus_adapter.py`
   - Еще один адаптер для EventSystem
   - Также добавляет избыточный уровень абстракции

5. **IEventPublisherFactory** (фабрика) - в `domain/abstractions/event_factory.py`
   - Фабрика для создания издателей событий
   - Добавляет дополнительный уровень абстракции

### Использование в системе:

- **SystemOrchestrator** использует IEventPublisherFactory для получения издателя событий
- Множество компонентов получают IEventPublisher через DI
- События публикуются из различных слоев (приложение, домен, инфраструктура)

## Проблемы текущей архитектуры:

1. **Избыточные уровни абстракции**:
   - IEventPublisherFactory → EventPublisherAdapter → EventSystem (3+ уровня)
   - EventBusAdapter как дополнительный уровень поверх EventSystem

2. **Нарушение принципа единственной ответственности**:
   - Множество классов имеют схожую функциональность

3. **Сложность для понимания и обслуживания**:
   - Требуется понимание нескольких уровней абстракции
   - Усложненная диагностика проблем

4. **Потенциальные точки отказа**:
   - Множественные точки инъекции зависимостей
   - Возможные проблемы с синглтонами

## Точки использования IEventPublisher:

1. **SystemOrchestrator** - центральная точка управления событиями
2. **AgentRuntime** - публикация событий выполнения агента
3. **ThinkingPatterns** - публикация событий выполнения паттернов
4. **AtomicActionExecutor** - публикация событий выполнения действий
5. **Various services** - публикация событий в различных сервисах

## Рекомендации по упрощению:

1. Удалить IEventPublisherFactory - использовать прямую инъекцию EventSystem
2. Удалить EventPublisherAdapter и EventBusAdapter - использовать EventSystem напрямую
3. Оставить только IEventPublisher интерфейс и EventSystem реализацию
4. Централизовать публикацию событий в AgentRuntime и SystemOrchestrator
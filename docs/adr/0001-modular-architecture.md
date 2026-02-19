# ADR-0001: Модульная архитектура с разделение на Infrastructure и Application контексты

**Дата:** 2026-02-19  
**Статус:** Принято  
**Авторы:** Agent_v5 Team

---

## Контекст

При разработке системы агентов потребовалось обеспечить:
- Изоляцию между агентами
- Общие инфраструктурные ресурсы
- Масштабируемость на несколько агентов
- Тестируемость компонентов

## Решение

Разделить контекст системы на два уровня:

### InfrastructureContext
Общий для всех агентов:
- ProviderFactory (LLM, DB провайдеры)
- ResourceRegistry
- EventBus
- MetricsCollector
- LogCollector

### ApplicationContext
Изолированный на каждого агента:
- ComponentRegistry (сервисы, навыки, инструменты)
- Isolated caches (промпты, контракты)
- ComponentConfig

```mermaid
graph TD
    subgraph Infrastructure
        A[ProviderFactory]
        B[ResourceRegistry]
        C[EventBus]
    end
    
    subgraph Agent1["ApplicationContext 1"]
        D1[ComponentRegistry]
        E1[Prompt Cache]
    end
    
    subgraph Agent2["ApplicationContext 2"]
        D2[ComponentRegistry]
        E2[Prompt Cache]
    end
    
    A --> D1
    A --> D2
    B --> D1
    B --> D2
```

## Последствия

### Положительные
- Четкое разделение ответственности
- Возможность запуска нескольких агентов параллельно
- Упрощение тестирования через изоляцию
- Снижение coupling между компонентами

### Отрицательные
- Усложнение инициализации
- Необходимость управления двумя контекстами
- Дополнительная документация для разработчиков

## Ссылки

- `core/infrastructure/context/infrastructure_context.py`
- `core/application/context/application_context.py`
- `docs/architecture.md`

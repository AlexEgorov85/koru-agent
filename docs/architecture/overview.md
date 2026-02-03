# Архитектура системы

Проект реализует **чистую слоистую архитектуру** с сильным разделением ответственности.

## Основные принципы
- Dependency Inversion
- Event-driven коммуникация
- Асинхронная модель выполнения
- Расширяемость через плагины (skills, tools, providers)
- Минимальная связность между компонентами

## Архитектурные слои

1. **Domain**
   - Capability
   - Value Objects
   - Модели решений и статусов

2. **Application**
   - Lifecycle
   - Domain management
   - Prompt services

3. **Core**
   - Agent runtime
   - SystemContext
   - SessionContext
   - Atomic actions
   - Composable patterns

4. **Infrastructure**
   - Репозитории
   - LLM / DB провайдеры
   - In-memory реализации

5. **Examples / Demos**
   - Демонстрационные сценарии

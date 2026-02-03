# Слои системы

## Core
Содержит бизнес-логику агента:
- ComposableAgent
- AtomicActionExecutor
- EventBus
- Context-объекты

Core не зависит от инфраструктуры.

## Application
Оркестрация use-case’ов:
- PromptInitializer
- PromptRenderer
- LifecycleManager

## Infrastructure
Технические реализации:
- InMemoryPromptRepository
- LLM adapters
- DB adapters

## Configuration
Изолирована и валидируется через Pydantic.

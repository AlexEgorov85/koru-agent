# Миграция на систему версионности промтов

## Обзор

В проект была успешно внедрена система версионности промтов, которая позволяет централизованно управлять, отслеживать и аудировать промты, используемые в системе.

## Что было реализовано

### 1. Доменная модель версии промта

Создана модель `PromptVersion` в `domain/models/prompt/prompt_version.py`:

- Семантическое версионирование (MAJOR.MINOR.PATCH)
- Поддержка ролей (SYSTEM, USER, ASSISTANT)
- Интеграция с существующими перечислениями (`DomainType`, `LLMProviderType`)
- Метрики использования (количество использований, успехи, среднее время генерации)
- Безопасная подстановка переменных в шаблонах

### 2. Репозиторий промтов

Созданы абстракция и реализации репозитория:

- `IPromptRepository` - абстракция для инверсии зависимостей
- `InMemoryPromptRepository` - реализация в памяти
- `FileBasedPromptRepository` - файловая реализация

### 3. Сервис рендеринга

Создан `PromptRenderer` в `application/services/prompt_renderer.py`:

- Безопасный рендеринг промтов из версий
- Подстановка переменных с защитой от инъекций
- Интеграция с репозиторием промтов

### 4. Инициализация промтов

Создан `PromptInitializer` в `application/services/prompt_initializer.py`:

- Автоматическая инициализация существующих промтов в репозитории
- Поддержка промтов из шаблонов планирования
- Извлечение переменных шаблонов

## Что было мигрировано в репозиторий

### 1. Промт для принятия решений LLM
- Файл: `application/prompts/llm_decision_prompt.py`
- Capability: `llm_decision`
- Роль: SYSTEM
- Переменные: `["goal", "tools", "last_steps_summary"]`

### 2. Промты планирования
- Файл: `infrastructure/adapters/skills/planning/prompt_templates.py`
- Capabilities:
  - `planning.plan_generation` (генерация плана)
  - `planning.code_generation` (генерация кода)
  - `planning.task_breakdown` (разбиение задач)
- Переменные извлекаются автоматически из шаблонов

## Архитектурные принципы

- **Инверсия зависимостей**: домен не зависит от инфраструктуры
- **Иммутабельность**: модели промтов неизменяемы
- **Обратная совместимость**: существующий код продолжает работать
- **Безопасность**: подстановка переменных без эвристик, только точное совпадение
- **Метрики**: отслеживание использования и эффективности промтов

## Использование

### Инициализация системы
```python
from application.services.prompt_initializer import PromptInitializer
from infrastructure.repositories.prompt_repository import InMemoryPromptRepository

repository = InMemoryPromptRepository()
initializer = PromptInitializer(repository)
await initializer.initialize_prompts()
```

### Использование в ExecutionGateway
ExecutionGateway теперь может использовать репозиторий промтов для получения актуальных версий:

```python
# Внедрение репозитория в ExecutionGateway
gateway = ExecutionGateway(system_context, prompt_repository=repository)

# Использование PromptRenderer для рендеринга промтов
renderer = PromptRenderer(repository)
rendered_prompts = await renderer.render_for_request(...)
```

## Тестирование

Созданы тесты для проверки:

- Unit-тесты для всех компонентов
- Интеграционные тесты
- Тесты безопасности (подстановка переменных)
- Тесты обратной совместимости
- Тесты архитектурных границ

## Преимущества

1. **Централизованное управление**: все промты в одном месте
2. **Версионность**: возможность откатов и отслеживания изменений
3. **Метрики**: отслеживание эффективности промтов
4. **Безопасность**: защита от инъекций в шаблонах
5. **Аудит**: полная история использования промтов
6. **Гибкость**: поддержка разных провайдеров и ролей
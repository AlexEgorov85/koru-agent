# Решение проблем с инициализацией ApplicationContext

## Описание проблемы

При попытке инициализировать `ApplicationContext` возникали следующие ошибки:

1. `Ошибка инициализации PromptService: Промпт planning.create_plan@v1.0.0 указан в конфигурации, но отсутствует в хранилище`
2. `Зависимость 'prompt_service' для 'sql_generation_service' ещё не инициализирована`
3. `Ошибка предзагрузки промпта planning.create_plan: Сервис 'prompt_service' не инициализирован`

## Причины проблем

### 1. Отсутствие поддержки YAML-файлов в PromptStorage

Исходный `PromptStorage` поддерживал только JSON-файлы, но в системе использовались YAML-файлы для промптов. Файл `prompts/skills/planning/create_plan_v1.0.0.yaml` не мог быть найден и загружен.

### 2. Неправильное определение путей к файлам

`PromptStorage` искал файлы по пути `prompts/prompts/planning/create_plan/v1.0.0.yaml`, но файлы находились в `prompts/skills/planning/create_plan_v1.0.0.yaml`.

### 3. Неправильная настройка пути к хранилищу промптов

`InfrastructureContext` инициализировал `PromptStorage` с неправильным путем - `prompts/prompts` вместо `prompts`, что приводило к невозможности найти файлы в подкаталогах.

### 4. Непроверенные результаты инициализации сервисов

`ApplicationContext` не проверял результаты инициализации сервисов, что приводило к продолжению инициализации даже при ошибках.

## Решение

### 1. Обновление PromptStorage

Обновлен `PromptStorage` для поддержки:
- YAML-файлов (.yaml, .yml)
- Поиска файлов в различных подкаталогах (skills/, strategies/, sql_generation/, contracts/)
- Правильного сопоставления capability_name с файлами

### 2. Исправление пути к хранилищу промптов

Обновлен `InfrastructureContext` для правильной инициализации `PromptStorage` с корневой директорией `prompts`, а не `prompts/prompts`.

### 3. Проверка результатов инициализации

Добавлена проверка возвращаемого значения из `initialize()` методов сервисов в `ApplicationContext._create_isolated_services()`.

### 4. Использование правильных конфигураций

- Использование `core.config.agent_config.AgentConfig` вместо `core.application.context.agent_config.AgentConfig`
- Использование поддерживаемых типов провайдеров (llama_cpp, sqlite)
- Правильное указание версий промптов

## Пример правильного использования

```python
import asyncio
from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.agent_config import AgentConfig

async def example():
    # Создаем системную конфигурацию
    llm_providers = {
        "llama_cpp_provider": LLMProviderConfig(
            enabled=True,
            type_provider="llama_cpp",
            parameters={
                "model_path": "mock_model",
                "n_ctx": 2048,
                "n_threads": 4,
                "n_gpu_layers": 0
            }
        )
    }
    
    db_providers = {
        "mock_db": DBProviderConfig(
            enabled=True,
            type_provider="sqlite",
            parameters={
                "database": ":memory:"
            }
        )
    }
    
    config = SystemConfig(
        debug=True,
        log_level="INFO",
        log_dir="./logs",
        data_dir="./",
        llm_providers=llm_providers,
        db_providers=db_providers
    )
    
    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    # Создаем конфигурацию агента с правильной версией промпта
    agent_config = AgentConfig(
        prompt_versions={"planning.create_plan": "v1.0.0"}
    )
    
    # Создаем и инициализируем прикладной контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=agent_config
    )
    
    await ctx1.initialize()
    
    # Проверяем, что промпт можно получить
    prompt_text = ctx1.get_prompt("planning.create_plan")
    print(f"Промпт успешно получен, длина: {len(prompt_text)} символов")
    
    # Завершаем работу
    await infra.shutdown()
```

## Заключение

Проблемы с инициализацией `ApplicationContext` были успешно решены путем:
1. Обновления `PromptStorage` для поддержки YAML-файлов и правильного поиска файлов
2. Исправления пути к хранилищу промптов в `InfrastructureContext`
3. Добавления проверок результатов инициализации сервисов
4. Использования правильных типов провайдеров и конфигураций
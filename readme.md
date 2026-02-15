# Система агентов

## Описание проекта

Этот проект представляет собой модульную платформу для автономных AI-агентов с возможностью:
- Reasoning-циклов (ReAct)
- Планирования и выполнения задач
- Интеграции с различными LLM и базами данных
- Отслеживания состояния и контекста
- Структурированного вывода с поддержкой нативной валидации провайдеров
- Типизированной обработки данных с гарантией валидности

## Взаимодействие с Git

### Защита от попадания нежелательных файлов в репозиторий

Проект настроен для автоматического игнорирования следующих типов файлов и директорий:

- Временные файлы и директории (`*.tmp`, `*.temp`, `tmp/`, `temp/`)
- Лог-файлы и директории (`logs/`)
- Файлы настроек IDE (`.vscode/`, `.idea/`, `*.swp`, `*.swo`)
- Виртуальные окружения (`venv/`, `env/`, `.venv/`, `.env`)
- Файлы с секретами и конфигурациями (`*.secrets`, `.env*`, `config/secrets.*`)
- Кэш-файлы (`__pycache__/`, `.pytest_cache/`, `.hypothesis/`, `*.pyc`)
- Файлы данных и модели (`*.csv`, `*.json`, `*.db`, `models/trained/`, `data/`)
- Файлы Jupyter Notebook checkpoints (`.ipynb_checkpoints/`)
- Системные файлы ОС (`.DS_Store`, `Thumbs.db`, `desktop.ini`)

### Структура проекта

```
project/
├── core/                           # Ядро системы
│   ├── agent_runtime/              # Runtime агента
│   │   └── runtime.py              # Reasoning-цикл
│   ├── application/                # Прикладной слой
│   │   ├── context/               # Контекст приложения
│   │   │   ├── application_context.py # Прикладной контекст
│   │   │   └── base_system_context.py # Базовый класс системного контекста
│   │   ├── services/              # Прикладные сервисы
│   │   └── tools/                 # Инструменты
│   ├── infrastructure/             # Инфраструктурный слой
│   │   ├── context/               # Контекст инфраструктуры
│   │   │   ├── infrastructure_context.py # Инфраструктурный контекст
│   │   │   └── agent_factory.py   # Фабрика агентов
│   │   ├── providers/             # Провайдеры (LLM, DB, etc.)
│   │   └── storage/               # Хранилища
│   ├── session_context/            # Контекст сессии
│   │   ├── session_context.py      # Контекст сессии
│   │   └── base_session_context.py # Базовый класс контекста сессии
│   ├── infrastructure/             # Инфраструктурные компоненты
│   │   ├── providers/              # Провайдеры (LLM, DB, etc.)
│   │   ├── service/                # Инфраструктурные сервисы
│   │   └── tools/                  # Инструменты
│   ├── events/                     # Система событий
│   │   ├── event_bus.py            # Шина событий
│   │   └── event_handlers.py       # Обработчики событий
│   ├── retry_policy/               # Политики повторных попыток
│   └── errors/                     # Кастомные ошибки
│       └── structured_output.py    # Ошибки структурированного вывода
├── models/                         # Типы данных
│   └── llm_types.py                # Типы LLM (LLMRequest, LLMResponse, etc.)
├── tools/                          # Инструменты для I/O
├── providers/                      # Адаптеры для внешних сервисов
├── config/                         # Конфигурационные файлы
└── tests/                          # Тесты всех компонентов
```

## Запуск тестов
```bash
python -m pytest tests/test_components_simple.py -v

python -m pytest tests/test_components.py -v

python -m pytest tests/providers/ -v
```

## Запуск агента

```bash
# Простой запуск с вопросом по умолчанию
python main.py

# Запуск с конкретным вопросом
python main.py "Проанализируй рынок искусственного интеллекта"

# Запуск в режиме разработки с отладкой
python main.py "Какие книги написал Пушкин?" --profile=dev --debug

# Запуск с ограничением шагов и сохранением результатов
python main.py "Сравни различные подходы к машинному обучению" --max-steps=3 --output=results.json

# Запуск с кастомной конфигурацией
python main.py "Проанализируй данные" --config-path=./configs/production.yaml
```

## Архитектурные особенности

### Структурированный вывод
Система поддерживает два режима обработки структурированного вывода:
- **Нативная валидация провайдером** - когда LLM-провайдер поддерживает `generate_structured` (например, OpenAI с response_format)
- **Системная валидация** - резервный режим с ретраями и коррекцией через централизованный `InfrastructureContext`

### Типизированные модели
- `StructuredOutputConfig` - конфигурация структурированного вывода
- `StructuredLLMResponse[T]` - обобщенная модель для типизированного ответа
- `RawLLMResponse` - модель для обычного (сырого) ответа
- `provider_native_validation` - флаг, показывающий, была ли использована нативная валидация

### Контексты

SessionContext
 ├── DataContext           # вся истина, сырые данные
 │     └── ContextItem
 ├── StepContext           # reasoning / шаги
 │     └── AgentStep
 └── current_plan_item_id  # ссылка


InfrastructureContext (Общий для всех агентов)
│
├── ProviderFactory (фабрика провайдеров)
├── ResourceRegistry (данные о ресурсах)
├── LifecycleManager (init / shutdown)
├── Event Bus (система событий)
└── Config (SystemConfig)


ApplicationContext (Изолированный на агента)
│
├── ComponentRegistry (сервисы, навыки, инструменты)
├── Isolated caches (промпты, контракты)
├── Config (AppConfig → ComponentConfig для компонентов)
└── Links to InfrastructureContext (только для чтения)


AgentRuntime
├─ think (LLM)
├─ select capability
├─ describe action (text/json)
└─ system.execute_capability()
├─ skill.run()
├─ tool.call()
├─ error handling
├─ write DataContext
└─ write StepContext


### AgentRuntime:
* просто видит SUCCESS / FAILED
* не знает, сколько было попыток
* не знает, почему был retry

### Retry — policy-driven
Ты можешь:
* подставить другую RetryPolicy
* сделать policy per capability
* вынести policy в конфиг

### ExecutionGateway стал «центром тяжести»
И это правильно:
* execution
* side-effects
* ошибки
* retry
* запись контекста


### Цель structured actions
Сделать так, чтобы:
* агент не мог выполнить невалидное действие
* ошибки агента ≠ ошибки tools
* INVALID_INPUT → ABORT, а не retry
* execution стал предсказуемым

### Цель structured output
Сделать так, чтобы:
* компоненты получали гарантированно валидные Pydantic-модели
* поддерживалась нативная валидация провайдеров, где доступна
* использовалась резервная валидация на уровне системы при отсутствии нативной
* обеспечивалась полная обратная совместимость

## Система конфигурации

Проект использует гибкую систему конфигурации на основе YAML файлов с поддержкой разных профилей окружения.

### Файлы конфигурации

- `config/settings.yaml` - базовая конфигурация (разработка)
- `config/settings_prod.yaml` - конфигурация для продакшена
- `config/settings_test.yaml` - конфигурация для тестирования

### Структура конфигурации

```yaml
profile: "dev"  # dev, test, prod
log_level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

providers:
  llm:
    provider_type: "vllm"
    model_name: "mistral-7b-instruct-v0.2"
    parameters:
      tensor_parallel_size: 1
      gpu_memory_utilization: 0.9

  database:
    provider_type: "postgres"
    parameters:
      host: "localhost"
      password: "${DB_PASSWORD|default_password}"  # Поддержка переменных окружения

agent:
  max_steps: 10
  timeout: 300
```

### Разделение конфигурации

Система использует два типа конфигурации для четкого разделения ответственности:

- **AppConfig** - глобальная конфигурация приложения, содержит общие параметры для всей системы
- **ComponentConfig** - локальная конфигурация компонента, содержит специфичные версии промптов и контрактов для каждого компонента

AppConfig загружается из `data/registry.yaml` и используется для настройки системы в целом, в то время как ComponentConfig создается для каждого компонента отдельно и обеспечивает изоляцию между агентами.
# Система агентов

## Описание проекта

Этот проект представляет собой модульную платформу для автономных AI-агентов с возможностью:
- Reasoning-циклов (ReAct)
- Планирования и выполнения задач
- Интеграции с различными LLM и базами данных
- Отслеживания состояния и контекста

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
├── core/                    # Ядро системы
│   ├── agent_runtime.py     # Reasoning-цикл
│   ├── execution_gateway.py # Единая точка выполнения
│   ├── context.py          # Двухуровневый контекст
│   ├── system_context.py   # Управление ресурсами
│   ├── retry_policy.py     # Политика повторных попыток
│   ├── structured_actions.py # Валидация действий
│   └── events/             # Система событий
│       ├── event_bus.py    # Шина событий
│       └── event_handlers.py # Обработчики событий
├── models/                 # Типы данных
├── skills/                 # Навыки агента
├── tools/                  # Инструменты для I/O
├── providers/              # Адаптеры для внешних сервисов
└── tests/                  # Тесты всех компонентов
```

## Запуск тестов
```bash
python -m pytest tests/test_session_context.py -v

python -m pytest tests/test_execution_gateway.py -v

python -m pytest tests/providers/conftest.py -v
python -m pytest -v tests/providers/
```

## Запуск агента

```bash
########
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

# Что нужно реализовать:
* у инструментов и скиллов формат входящих данных
* у всех действий агента должно быть структура
* как будет определяться стратегия? Может добавить SGR для размышления?


SessionContext
 ├── DataContext           # вся истина, сырые данные
 │     └── ContextItem
 ├── StepContext           # reasoning / шаги
 │     └── AgentStep
 └── current_plan_item_id  # ссылка


SystemContext (Facade / Composition Root)
│
├── ResourceRegistry (данные о ресурсах)
├── LifecycleManager (init / shutdown)
├── HealthManager (health checks)
├── CapabilityRegistry (capabilities)
├── AgentFactory (создание агентов)
└── Config (SystemConfig)


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
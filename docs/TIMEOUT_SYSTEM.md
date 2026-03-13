# Система Таймаутов Agent v5

## Проблема

До рефакторинга таймауты были разбросаны по всему коду с противоречивыми значениями:

| Компонент | Файл | Значение | Проблема |
|-----------|------|----------|----------|
| LLM (action_executor) | `action_executor.py` | 60s | Слишком мало для локальных LLM |
| LLM (llama_cpp) | `llama_cpp_provider.py` | 600s | Правильно, но не согласовано |
| Database | `postgres_provider.py` | 30s | OK |
| Vector Search | Various | 30s | OK |
| Action Executor | `action_executor.py` | 60s | Слишком мало |

**Результат:** LLM timeout через 60s при генерации SQL запроса (требуется ~120-300s для Qwen 4B).

## Решение

### 1. Централизованная Конфигурация

Создан единый источник истины: `core/config/timeout_config.py`

```python
from core.config.timeout_config import get_timeout_config

timeout_config = get_timeout_config()

# Использование
llm_timeout = timeout_config.llm_attempt_timeout  # 600s для локальных LLM
db_timeout = timeout_config.db_query_timeout      # 60s
```

### 2. Иерархия Таймаутов

```
┌─────────────────────────────────────────────────────────────┐
│                    TimeoutConfig                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LLM timeouts (600s attempt, 1200s total)            │    │
│  │ - llm_attempt_timeout: 600.0                        │    │
│  │ - llm_total_timeout: 1200.0                         │    │
│  │ - llm_max_retries: 3                                │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Database timeouts (30-60s)                          │    │
│  │ - db_connection_timeout: 30.0                       │    │
│  │ - db_query_timeout: 60.0                            │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Action timeouts (600s default)                      │    │
│  │ - action_default_timeout: 600.0                     │    │
│  │ - action_context_timeout: 120.0                     │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Agent timeouts (1200-7200s)                         │    │
│  │ - agent_step_timeout: 1200.0                        │    │
│  │ - agent_total_timeout: 7200.0                       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 3. Пресеты Конфигурации

```python
# Для локальных LLM (Qwen 4B, Llama 3)
TimeoutConfig.for_local_llm()
# → attempt=600s, total=1200s, retries=3

# Для облачных LLM (OpenAI, Anthropic)
TimeoutConfig.for_cloud_llm()
# → attempt=60s, total=180s, retries=3

# Для тестов
TimeoutConfig.for_testing()
# → attempt=30s, total=60s, retries=1
```

### 4. Специфичные Таймауты для Действий

```python
timeout_config.get_llm_timeout_for_action('llm.generate_structured')
# → 600.0s

timeout_config.get_llm_timeout_for_action('llm.generate')
# → 300.0s (0.5 * attempt_timeout)

timeout_config.get_llm_timeout_for_action('llm.classify')
# → 180.0s (0.3 * attempt_timeout)
```

## Использование

### В ActionExecutor

```python
from core.config.timeout_config import get_timeout_config

timeout_config = get_timeout_config()

if action_name.startswith("llm."):
    attempt_timeout = parameters.get(
        "attempt_timeout",
        timeout_config.get_llm_timeout_for_action(action_name)
    )
    total_timeout = parameters.get(
        "total_timeout",
        timeout_config.llm_total_timeout
    )
else:
    attempt_timeout = parameters.get(
        "attempt_timeout",
        timeout_config.action_default_timeout
    )
```

### В Конфигурации Приложения

```python
from core.config.timeout_config import TimeoutConfig

app_config = AppConfig(
    profile="dev",
    timeout_config=TimeoutConfig.for_local_llm()
)
```

### Переопределение Таймаута

```python
# Переопределение на уровне действия
result = await executor.execute_action(
    action_name="llm.generate_structured",
    parameters={
        "prompt": "...",
        "attempt_timeout": 900.0,  # 15 минут для сложной генерации
        "total_timeout": 1800.0    # 30 минут на все попытки
    },
    context=context
)
```

## Рекомендации

### Для Локальных LLM (Qwen 4B, Llama 3 8B)

```python
TimeoutConfig(
    llm_attempt_timeout=600.0,    # 10 минут на попытку
    llm_total_timeout=1200.0,     # 20 минут на все попытки
    agent_step_timeout=1200.0,    # 20 минут на шаг агента
)
```

### Для Облачных LLM (GPT-4, Claude)

```python
TimeoutConfig(
    llm_attempt_timeout=60.0,     # 1 минута на попытку
    llm_total_timeout=180.0,      # 3 минуты на все попытки
    agent_step_timeout=120.0,     # 2 минуты на шаг агента
)
```

### Для Тестов

```python
TimeoutConfig(
    llm_attempt_timeout=30.0,     # 30 секунд
    llm_total_timeout=60.0,       # 1 минута
    llm_max_retries=1,            # 1 попытка
)
```

## Мониторинг

### Логирование Таймаутов

```
[WARNING] [LLMOrchestrator] ⏰ LLM TIMEOUT | call_id=llm_123 | 
  elapsed=600.01s | timeout=600.0s | prompt_len=5641

[ERROR] [LLMOrchestrator] ❌ Structured EXHAUSTED | 
  total_attempts=3 | last_error=LLM timeout после 600.01с
```

### Метрики

```python
metrics = {
    'timeout_rate': 0.05,      # 5% вызовов превысили таймаут
    'avg_generation_time': 120.5,  # Средняя генерация 120s
    'orphan_rate': 0.01,       # 1% "осиротевших" вызовов
}
```

## Расширение

### Добавление Нового Таймаута

1. Добавьте поле в `TimeoutConfig`:

```python
class TimeoutConfig(BaseModel):
    new_component_timeout: float = Field(
        default=60.0,
        description="Таймаут нового компонента"
    )
```

2. Обновите методы-пресеты:

```python
@classmethod
def for_local_llm(cls):
    return cls(
        new_component_timeout=120.0,  # Больше для локальных
        ...
    )
```

3. Используйте в коде:

```python
timeout = timeout_config.new_component_timeout
```

## Troubleshooting

### Частые Таймауты LLM

**Проблема:** LLM не успевает сгенерировать ответ за 600s

**Решение:**
```python
# Увеличьте таймаут
timeout_config = TimeoutConfig(
    llm_attempt_timeout=900.0,   # 15 минут
    llm_total_timeout=1800.0,    # 30 минут
)
```

### Слишком Долгое Ожидание

**Проблема:** Агент ждёт 600s даже для простых запросов

**Решение:**
```python
# Используйте специфичные таймауты
timeout_config.get_llm_timeout_for_action('llm.classify')  # 180s
timeout_config.get_llm_timeout_for_action('llm.generate')  # 300s
```

### Тесты Выполняются Долгое Время

**Проблема:** Тесты ждут 600s на каждый LLM вызов

**Решение:**
```python
# Используйте тестовый пресет
timeout_config = TimeoutConfig.for_testing()
# attempt=30s, total=60s, retries=1
```

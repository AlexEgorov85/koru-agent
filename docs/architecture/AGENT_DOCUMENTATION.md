# Архитектура и документация Agent v5

## Содержание

1. [Обзор](#обзор)
2. [Компоненты ядра](#компоненты-ядра)
3. [Метрики](#метрики)
4. [Сравнения и проверки](#сравнения-и-проверки)
5. [Сервисы](#сервисы)
6. [Жизненный цикл](#жизненный-цикл)
7. [События и телеметрия](#события-и-телеметрия)

---

## Обзор

Agent v5 представляет собой асинхронную систему агента с многоуровневой архитектурой:

```
User Query
    ↓
┌─────────────────────────────────────────────────────┐
│                AgentRuntime                        │
│  ┌──────────┐    ┌─────────────┐    ┌───────────┐  │
│  │ Pattern  │ →  │  Executor   │ →  │ Observer │  │
│  │ (decide)│    │ (execute)  │    │(analyze) │  │
│  └──────────┘    └─────────────┘    └───────────┘  │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│              Result (ExecutionResult)               │
└─────────────────────────────────────────────────────┘
```

### Основной цикл

```
1. Pattern.decide()     → Анализирует контекст и генерирует решение
2. Policy.check()       → Проверяет допустимость действия
3. Executor.execute()   → Выполняет действие через компоненты
4. Observer.analyze()  → Анализирует результат через LLM
5. Metrics.update()    → Обновляет метрики на основе наблюдения
```

---

## Компоненты ядра

### 1. AgentRuntime (`core/agent/runtime.py`)

**Назначение**: Главный orchestration компонент, управляющий циклом выполнения агента.

**Ответственность**:
- Инициализация Pattern, executor, metrics, observer
- Управление циклом выполнения (max_steps)
- Координация всех компонентов
- Логирование в файлы

**Ключевые компоненты, которые создаёт**:
```python
self.executor = ActionExecutor(application_context)
self.failure_memory = FailureMemory()
self.policy = AgentPolicy()
self.metrics = AgentMetrics()
self.observer = Observer(application_context)
self.safe_executor = SafeExecutor(...)
self.observation_signal_service = ObservationSignalService()
self.fallback_strategy = FallbackStrategyService()
```

**Параметры инициализации**:
- `application_context` - контекст приложения
- `goal` - цель агента
- `max_steps` - максимальное количество шагов (по умолчанию 10)
- `user_context` - контекст пользователя
- `correlation_id` - ID корреляции
- `agent_id` - ID агента
- `dialogue_history` - история диалога

### 2. Pattern (ReActPattern) (`core/agent/behaviors/react/pattern.py`)

**Назначение**: Принятие решений через LLM на основе анализа контекста.

**Методы**:
- `decide(session_context, available_capabilities)` - главная точка входа
- `analyze_context(session_context, capabilities)` - анализ контекста
- `generate_decision(session_context, context, capabilities)` - генерация решения через LLM
- `_make_decision(reasoning_result, capabilities)` - преобразование ответа LLM в Decision

**Входные данные для анализа**:
- `goal` - цель сессии
- `last_steps` - последние шаги
- `progress` - прогресс
- `execution_time_seconds` - время выполнения
- `state_errors` - ошибки состояния
- `empty_results_count` - счётчик пустых результатов
- `repeated_actions_count` - счётчик повторяющихся действий
- `last_observation` - последнее наблюдение

**Выходные данные (Decision)**:
- `type` - тип решения (ACT, FINISH, FAIL, SWITCH_STRATEGY)
- `action` - имя capability для выполнения
- `parameters` - параметры действия
- `reasoning` - обоснование решения
- `result` - результат выполнения (для FINISH)

### 3. ActionExecutor (`core/agent/components/action_executor.py`)

**Назначение**: Единственный посредник для взаимодействия компонентов.

**Архитектурные принципы**:
- Изоляция компонентов друг от друга
- Контроль зависимостей и порядка выполнения
- Единая точка для метрик и логирования
- Возможность внедрения мидлварей (retry, rate-limits)

**Поддерживаемые типы действий**:
| Префикс | Тип | Описание |
|--------|-----|---------|
| `context.` | Context actions | Операции с контекстом |
| `llm.` | LLM actions | Генерация через LLM |
| `validation.` | Validation actions | Валидация данных |
| `skill.*` | Skill actions | Выполнение навыков |
| `tool.*` | Tool actions | Выполнение инструментов |
| `service.*` | Service actions | Выполнение сервисов |

**Контекстные методы**:
- `context.record_plan` - сохранение плана
- `context.get_current_plan` - получение текущего плана
- `context.get_context_item` - получение элемента по ID
- `context.get_all_items` - получение всех элементов
- `context.get_step_history` - получение истории шагов
- `context.record_action` - запись действия
- `context.record_observation` - запись наблюдения
- `context.get_goal` - получение цели
- `context.get_summary` - получение резюме
- `context.get_recent_errors` - получение ошибок

### 4. SafeExecutor (`core/agent/components/safe_executor.py`)

**Назначение**: Безопасный исполнитель с retry логикой для временных ошибок.

**Принципы работы** (Этап 2):
- Изоляция ошибок от основного потока выполнения
- Классификация ошибок для правильных решений
- Экспоненциальная задержка для retry
- Запись в FailureMemory для анализа паттернов

**Retry логика**:
```python
for attempt in range(max_retries):
    result = await executor.execute_action(...)
    
    if success:
        return result
    
    if error_type == TRANSIENT:
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
            continue
```

**Параметры**:
- `max_retries` - максимум попыток (по умолчанию 3)
- `base_delay` - базовая задержка (0.5 сек)
- `max_delay` - максимальная задержка (5.0 сек)
- `jitter` - случайное изменение задержки

### 5. Observer (`core/agent/components/observer.py`)

**Назначение**: LLM-анализ результатов выполнения действий.

**Функции**:
1. Анализирует результат действия через LLM
2. Оценивает статус, качество, проблемы
3. Генерирует insight и рекомендации для следующего шага
4. Использует контракт `behavior.react.observe_output_v1.0.0`

**Методы**:
- `analyze(action_name, parameters, result, error, session_id, agent_id, step_number)` - главная точка входа

**Выходные данные (observation)**:
```python
{
    "status": "success" | "partial" | "error" | "empty",
    "observation": "описание результата",
    "key_findings": ["список важных фактов"],
    "data_quality": {
        "completeness": 0.0-1.0,
        "reliability": 0.0-1.0
    },
    "errors": ["список ошибок"],
    "next_step_suggestion": "рекомендация для следующего шага",
    "requires_additional_action": True | False
}
```

### 6. SessionContext (`core/session_context/session_context.py`)

**Назначение**: Контекст сессии агента - хранилище всех данных сессии.

**Структура**:
```python
self.session_id          # Уникальный ID сессии
self.agent_id          # ID агента
self.goal             # Цель сессии
self.data_context      # Хранилище всех сырых данных
self.step_context      # Хранилище шагов агента
self.dialogue_history # История диалога
self.agent_state      # Централизованное состояние
self._empty_query_log # Лог пустых результатов
```

**Подкомпоненты**:
- `DataContext` - хранилище ContextItem
- `StepContext` - хранилище AgentStep
- `DialogueHistory` - история диалога
- `AgentState` - состояние цикла агента

**AgentState** - отслеживает:
```python
consecutive_repeated_actions   # Повторяющиеся действия
consecutive_empty_results     # Пустые результаты
last_observation           # Последнее наблюдение
errors                   # Список ошибок
```

---

## Метрики

### AgentMetrics (`core/agent/components/agent_metrics.py`)

**Назначение**: Отслеживание качества выполнения агента.

**Атрибуты**:
| Атрибут | Тип | Описание |
|---------|-----|---------|
| `step_number` | int | Текущий номер шага |
| `errors` | List[Dict] | Список ошибок |
| `empty_results_count` | int | Счётчик пустых результатов |
| `repeated_actions_count` | int | Счётчик повторяющихся действий |
| `last_observation` | Dict | Последнее наблюдение от Observer |
| `recent_actions` | List[str] | Последние N действий |
| `action_hashes` | List[str] | Хеши действий с параметрами |

**Методы**:

```python
# Регистрация шага
add_step(action_name, status, error, parameters)

# Обновление наблюдения
update_observation(observation)

# Проверка повторяющегося действия
check_repeated_action(action_name, parameters) -> bool

# Получение последних действий
get_recent_actions(n) -> List[str]

# Получение ошибок
get_errors_summary(n) -> List[str]

# Проверка условий остановки
should_stop(max_errors, max_empty, max_repeats) -> (bool, str)
```

### Метрики LLM (LLMMetrics) (`core/infrastructure/providers/llm/llm_orchestrator.py`)

**Атрибуты**:
| Атрибут | Тип | Описание |
|--------|-----|---------|
| `total_calls` | int | Всего вызовов |
| `completed_calls` | int | Успешных вызовов |
| `failed_calls` | int | Ошибок вызовов |
| `total_generation_time` | float | Суммарное время генерации |
| `cache_hits` | int | Попадания в кэш |
| `structured_calls` | int | Структурированных вызовов |
| `structured_success` | int | Успешных структурированных |
| `total_retry_attempts` | int | Сумма попыток |

**Вычисляемые свойства**:
```python
avg_generation_time     # Среднее время генерации
structured_success_rate # Процент успешных структурированных
avg_retries_per_call   # Среднее количество попыток
```

---

## Сравнения и проверки

### 1. Policy (AgentPolicy)

**Назначение**: Единая политика агента - ограничения и проверки.

**Ограничения**:
| Параметр | Значение по умолчанию | Описание |
|----------|---------------------|---------|
| `max_steps` | 10 | Максимум шагов |
| `max_errors` | 10 | Максимум ошибок |
| `max_consecutive_errors` | 3 | Максимум последовательных ошибок |
| `max_no_progress_steps` | 5 | Максимум шагов без прогресса |
| `max_repeated_actions` | 3 | Максимум повторов |
| `max_empty_results` | 3 | Максимум пустых результатов |

**Retry параметры**:
| Параметр | Значение по умолчанию | Описание |
|----------|---------------------|---------|
| `retry_max_attempts` | 3 | Максимум попыток |
| `retry_base_delay` | 0.5 | Базовая задержка |
| `retry_max_delay` | 5.0 | Максимальная задержка |
| `retry_jitter` | True | Использовать jitter |

**Методы проверки**:
```python
# Проверка допустимости шага
check_step(action_name, parameters, state) -> (bool, reason)

# Проверка на повтор
_check_repeat_action(action_name, metrics, parameters) -> bool

# Проверка на empty loop
_check_empty_loop(metrics) -> bool

# Проверка на превышение ошибок
_check_max_errors(metrics) -> bool
```

### 2. Проверки, которые выполняет AgentRuntime

**На каждом шаге**:

1. **Проверка остановки по Policy**:
```python
if agent_state.consecutive_repeated_actions >= 3:
    return failure("repeat_action")
if agent_state.consecutive_empty_results >= 3:
    return failure("empty_loop")
```

2. **Проверка условий остановки по метрикам**:
```python
should_stop, reason = metrics.should_stop()
if should_stop:
    return failure(reason)
```

**После выполнения действия**:

3. **Observer.analyze()** возвращает observation:
```python
observation = await observer.analyze(...)
status = observation.get("status")

if status == "empty" or status == "error":
    if observation.get("requires_additional_action"):
        # Рекомендуется сменить стратегию
```

---

## Сервисы

### 1. FallbackStrategyService (`core/agent/behaviors/services/fallback_strategy.py`)

**Назначение**: Генерация fallback решений при ошибках.

**Типы fallback**:
- `create_error(reason, capabilities)` - при ошибке
- `create_reasoning_fallback(context, capabilities, reason)` - при ошибке рассуждения
- `create_no_capabilities_fallback(goal)` - при отсутствии capability

### 2. ObservationSignalService (`core/agent/components/observation_signal.py`)

**Назначение**: Построение observation-сигнала из результата выполнения.

**Выходной формат**:
```python
{
    "status": "success" | "error" | "empty",
    "quality": "high" | "low" | "useless",
    "issues": [],
    "insight": "описание",
    "next_step_hint": "рекомендация"
}
```

### 3. SQLDiagnosticService (`core/agent/components/sql_diagnostic.py`)

**Назначение**: Диагностика и исправление SQL-запросов после пустых результатов.

**Методы**:
- `analyze_empty_result(sql_query, original_params)` - анализ пустого результата

**Выходные данные**:
```python
{
    "hints": ["список подсказок"],
    "corrected_params": {исправленные параметры}
}
```

### 4. FailureMemory (`core/agent/components/failure_memory.py`)

**Назначение**: Запись и анализ паттернов ошибок.

**Методы**:
- `record(capability, error_type, timestamp)` - запись ошибки
- `reset(capability)` - сброс
- `get_count(capability)` - количество ошибок

### 5. ErrorClassifier (`core/agent/components/error_classifier.py`)

**Назначение**: Классификация ошибок по категориям.

**Категории ошибок**:
| Category | Описание | Примеры |
|----------|---------|--------|
| `TRANSIENT` | Временные | Timeout, Connection |
| `LOGIC` | Логические | Неверные параметры |
| `VALIDATION` | Валидация | Невалидные данные |
| `FATAL` | Фатальные | Критические ошибки |

---

## Жизненный цикл

### Инициализация

```python
# 1. Создание AgentRuntime
runtime = AgentRuntime(
    application_context=app_ctx,
    goal="пользовательский запрос",
    max_steps=10,
    agent_id="agent_001"
)

# 2. Инициализация Pattern (один раз)
pattern = await runtime._get_pattern()

# 3. Создание SessionContext
session_context = runtime.session_context
```

### Выполнение

```
for step in range(max_steps):
    1. Pattern.decide()
       ↓
    2. Decision.type == ACT?
       ↓ Да
    3. Policy.check_step() - проверка допустимости
       ↓
    4. SafeExecutor.execute() - выполнение
       ↓
    5. Observer.analyze() - анализ результата
       ↓
    6. Metrics.update() - обновление метрик
       ↓
    7. Сохранение в SessionContext
```

### Типы решений Pattern

| DecisionType | Описание | Действие |
|--------------|----------|----------|
| `ACT` | Выполнить действие | Execute action |
| `FINISH` | Завершить успешно | Return result |
| `FAIL` | Завершить с ошибкой | Return error |
| `SWITCH_STRATEGY` | Сменить стратегию | Load new pattern |

### Завершение

```python
# Успешное завершение
return ExecutionResult.success(data=result)

# Завершение с ошибкой
return ExecutionResult.failure(error="reason")

# Остановка по policy
return ExecutionResult.failure("Stopped by policy: repeat_action")
```

---

## События и телеметрия

### UnifiedEventBus

**Назначение**: Единая шина событий с session isolation и domain routing.

**Типы событий** (`EventType`):

**Системные**:
- `SYSTEM_INITIALIZED`, `SYSTEM_SHUTDOWN`, `SYSTEM_ERROR`

**Сессии**:
- `SESSION_CREATED`, `SESSION_STARTED`, `SESSION_COMPLETED`, `SESSION_FAILED`

**Агента**:
- `AGENT_CREATED`, `AGENT_STARTED`, `AGENT_COMPLETED`, `AGENT_FAILED`

**Выполнения**:
- `CAPABILITY_SELECTED`, `ACTION_PERFORMED`, `STEP_REGISTERED`

**LLM**:
- `LLM_CALL_STARTED`, `LLM_CALL_COMPLETED`, `LLM_CALL_FAILED`

**Ошибки**:
- `RETRY_ATTEMPT`, `ERROR_OCCURRED`

### Domain routing

События маршрутизируются по доменам:

| Domain | События |
|--------|---------|
| `AGENT` | agent.*, capability.*, action.* |
| `INFRASTRUCTURE` | system.*, provider.*, llm.*, service.* |
| `BENCHMARK` | benchmark.* |
| `OPTIMIZATION` | optimization.*, self_improvement.*, version.* |
| `COMMON` | retry.*, error.*, metric.*, execution.* |

### Метрики выполнения

**FileSystemMetricsStorage** сохраняет метрики в:
```
data/metrics/
├── {capability}/
│   ├─�� {version}/
│   │   ├── metrics_{date}.json
│   │   └── aggregated.json
│   └── latest/
│       └── metrics.json
```

**MetricRecord включает**:
- `capability`, `version`, `timestamp`
- `success`, `failure`
- `execution_time_ms`, `tokens_used`
- `error_type`, `error_message`

---

## Схема потоков данных

```
User Query
    │
    ├── Pattern.decide()
    │   ├── analyze_context() ─→ SessionContext
    │   ├── get_prompt("behavior.react.think")
    │   ├── get_contract("behavior.react.think")
    │   ├── LLMOrchestrator.execute_structured()
    │   │   └── LLMProvider.generate()
    │   │
    │   └── Decision(type=ACT, action=..., parameters=...)
    │
    ├── Policy.check_step()
    │
    ├── SafeExecutor.execute()
    │   ├── ActionExecutor.execute_action()
    │   │   ├── skill.sql_tool.execute()
    │   │   └── llm.generate()
    │   │
    │   └── (retry logic для TRANSIENT errors)
    │
    ├── Observer.analyze()
    │   ├── get_contract("behavior.react.observe")
    │   └── LLMOrchestrator.execute_structured()
    │
    ├── Metrics.update()
    │
    └── SessionContext
        ├── register_step()
        ├── record_action()
        ├── record_observation()
        └── commit_turn()
```

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `core/agent/runtime.py` | Главный цикл агента |
| `core/agent/components/action_executor.py` | Единый посредник |
| `core/agent/components/safe_executor.py` | Retry логика |
| `core/agent/components/observer.py` | LLM-анализ результатов |
| `core/agent/components/agent_metrics.py` | Метрики агента |
| `core/agent/components/policy.py` | Ограничения и проверки |
| `core/agent/behaviors/react/pattern.py` | Принятие решений |
| `core/session_context/session_context.py` | Контекст сессии |
| `core/infrastructure/event_bus/unified_event_bus.py` | Шина событий |
| `core/infrastructure/providers/llm/llm_orchestrator.py` | Управление LLM |

---

## Константы и лимиты

| Параметр | Значение |
|----------|---------|
| `DEFAULT_QUEUE_MAX_SIZE` | 1000 |
| `DEFAULT_WORKER_IDLE_TIMEOUT` | 60.0 сек |
| `DEFAULT_SUBSCRIBER_TIMEOUT` | 60.0 сек |
| `max_steps` по умолчанию | 10 |
| `max_retries` по умолчанию | 3 |
| `retry_base_delay` по умолчанию | 0.5 сек |
| `retry_max_delay` по умолчанию | 5.0 сек |

---

*Документация сгенерирована автоматически на основе исходного кода Agent v5.*
# Анализ проблем асинхронности и жизненного цикла

**Дата:** 6 марта 2026 г.  
**Статус:** Этап 0 завершён

---

## 1. Карта зависимостей компонентов

### 1.1. Ключевые компоненты и их связи

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  run_agent()                                             │   │
│  │    ↓                                                     │   │
│  │  1. InfrastructureContext.initialize()                   │   │
│  │    ↓                                                     │   │
│  │  2. ApplicationContext.initialize()                      │   │
│  │    ↓                                                     │   │
│  │  3. AgentFactory.create_agent()                          │   │
│  │    ↓                                                     │   │
│  │  4. AgentRuntime.run()                                   │   │
│  │         ↓                                                │   │
│  │    - BehaviorManager.generate_next_decision()            │   │
│  │    - ActionExecutor.execute_capability()                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2. InfrastructureContext

**Зависимости:**
- `SystemConfig` (конфигурация)
- `UnifiedEventBus` (шина событий)
- `LifecycleManager` (менеджер жизненного цикла)
- `ResourceRegistry` (реестр ресурсов)
- `LLMProviderFactory`, `DBProviderFactory` (фабрики провайдеров)
- `PromptStorage`, `ContractStorage` (хранилища)
- `ResourceDiscovery` (обнаружение ресурсов)
- `MetricsCollector`, `LogCollector` (сборщики)

**Методы жизненного цикла:**
- `async initialize()` → инициализация всех инфраструктурных ресурсов
- `async shutdown()` → завершение работы (вызывает `_cleanup_providers()`)

**Состояние:**
- `_initialized: bool` (флаг инициализации)

### 1.3. ApplicationContext

**Зависимости:**
- `InfrastructureContext` (только для чтения!)
- `AppConfig` (конфигурация приложения)
- `ComponentRegistry` (реестр компонентов)
- `DataRepository` (репозиторий данных)
- `LLMOrchestrator` (оркестратор LLM)

**Методы жизненного цикла:**
- `async initialize()` → создание и инициализация всех компонентов
- `async shutdown()` → завершение работы компонентов

**Состояние:**
- `_initialized: bool`
- `components: ComponentRegistry`

### 1.4. AgentRuntime

**Зависимости:**
- `ApplicationContext`
- `BehaviorManager`
- `ActionExecutor`
- `AgentPolicy`, `AgentState`, `ProgressScorer`
- `ExecutionGateway`

**Методы жизненного цикла:**
- `async run()` → основной цикл выполнения
- `async stop()` → остановка

**Состояние:**
- `_running: bool`
- `_current_step: int`
- `_result: Optional[ExecutionResult]`

### 1.5. BehaviorManager

**Зависимости:**
- `ApplicationContext`
- `BehaviorStorage`
- `BehaviorPatternInterface` (текущий паттерн)

**Методы жизненного цикла:**
- `async initialize(component_name)` → загрузка паттерна
- `async generate_next_decision()` → генерация решения

**Состояние:**
- `_current_pattern: Optional[BehaviorPatternInterface]`
- `_pattern_history: List[dict]`

### 1.6. ActionExecutor

**Зависимости:**
- `ApplicationContext`

**Методы:**
- `async execute_action()` → выполнение действия
- `async execute_capability()` → выполнение capability

**Состояние:** Нет состояния (stateless)

---

## 2. Методы initialize() и shutdown()

### 2.1. Сводная таблица

| Компонент | initialize() | shutdown() | Состояние |
|-----------|-------------|------------|-----------|
| `InfrastructureContext` | ✅ async | ✅ async | `_initialized: bool` |
| `ApplicationContext` | ✅ async | ✅ async | `_initialized: bool` |
| `LifecycleManager` | ✅ async (`initialize_all()`) | ✅ async (`shutdown_all()`) | `_initialized: bool`, `_shutdown_in_progress: bool` |
| `BaseComponent` | ✅ async | ❌ (опционально) | `_initialized: bool` |
| `BaseSkill` | ✅ async | ❌ (опционально) | `_is_initialized: bool` |
| `BaseService` | ✅ async | ❌ (опционально) | `_initialized: bool` |
| `BaseTool` | ✅ async | ❌ (опционально) | `_initialized: bool` |
| `BehaviorManager` | ✅ async | ❌ | `_current_pattern` |
| `AgentRuntime` | ❌ | ✅ async (`stop()`) | `_running: bool` |
| `LLMOrchestrator` | ✅ async | ✅ async | `_initialized: bool` |
| `MetricsCollector` | ✅ async | ✅ async | `_initialized: bool` |
| `LogCollector` | ✅ async | ✅ async | `_initialized: bool` |
| `UnifiedEventBus` | ❌ (авто) | ✅ async (`shutdown()`) | `_running: bool` |
| `SessionWorker` | ✅ async (`start()`) | ✅ async (`stop()`) | `_running: bool` |

### 2.2. Проблемы

1. **Непоследовательные имена:** Некоторые компоненты используют `initialize()`, другие `start()`, третьи не имеют явных методов.
2. **Отсутствие проверок состояния:** Не все методы проверяют `_initialized` перед выполнением.
3. **Нет enum состояний:** Используется простой bool, что не позволяет отследить FAILED состояние.

---

## 3. Фоновые задачи (create_task) без ожидания

### 3.1. Найденные вызовы `asyncio.create_task()`

| Файл | Строка | Контекст | Сохраняется ли ссылка |
|------|--------|----------|----------------------|
| `config/dynamic_config.py` | 185 | `_watch_loop()` | ✅ `self._task` |
| `observability/observability_manager.py` | 193 | `_periodic_check_loop()` | ✅ `self._task` |
| `storage/file_system_data_source.py` | 100 | `event_bus.publish()` | ❌ Fire-and-forget |
| `providers/llm/llm_orchestrator.py` | 303 | `_cleanup_loop()` | ✅ `self._cleanup_task` |
| `providers/llm/llm_orchestrator.py` | 450 | `_schedule_cleanup()` | ❌ Fire-and-forget |
| `logging/handlers.py` | 306 | `event_bus.publish()` | ❌ Fire-and-forget |
| `event_bus/unified_event_bus.py` | 387 | `SessionWorker._run()` | ✅ `self._task` |
| `event_bus/unified_event_bus.py` | 1060 | `handler(event)` | ❌ Fire-and-forget |

### 3.2. Проблемы

1. **Fire-and-forget задачи:** 4 места создают задачи без сохранения ссылки.
2. **Риск потери задач:** При shutdown задачи могут быть отменены без завершения.
3. **Отсутствие обработки исключений:** В fire-and-forget задачах исключения могут теряться.

### 3.3. Рекомендации

- Добавить `_background_tasks: Set[asyncio.Task]` в `UnifiedEventBus` и `LLMOrchestrator`.
- Явно дожидаться задачи в `shutdown()`.
- Обернуть fire-and-forget вызовы в `try/except` с логированием.

---

## 4. Использование `asyncio.run()` в библиотеках

### 4.1. Найденные вызовы

| Файл | Строка | Контекст | Проблема |
|------|--------|----------|----------|
| `errors/error_handler.py` | 462 | `sync_wrapper()` в декораторе `handle_errors` | **КРИТИЧНО**: Запуск нового event loop внутри существующего |

### 4.2. Детали проблемы в `error_handler.py`

```python
def sync_wrapper(*args, **kwargs):
    context = ErrorContext(...)
    try:
        return func(*args, **kwargs)
    except Exception as e:
        # ❌ ПРОБЛЕМА: asyncio.run() внутри синхронного контекста
        asyncio.run(self.handle(e, context, severity=severity))
        if reraise:
            raise
        return None
```

**Почему это проблема:**
- Если `sync_wrapper` вызывается внутри уже запущенного event loop, `asyncio.run()` выбросит `RuntimeError`.
- Это нарушает принцип единого event loop.
- Невозможно использовать в асинхронном контексте.

### 4.3. Рекомендации

1. **Удалить поддержку синхронных функций** в декораторе `handle_errors`.
2. Требовать, чтобы все декорируемые функции были асинхронными.
3. Добавить проверку через `inspect.iscoroutinefunction()`.

---

## 5. Синхронные вызовы логирования

### 5.1. Найденные синхронные методы

| Компонент | Метод | Контекст использования |
|-----------|-------|----------------------|
| `EventBusLogger` | `info_sync()`, `debug_sync()`, `warning_sync()`, `error_sync()` | До инициализации event_bus, в тестовом коде |
| `BaseComponent` | `_safe_log_sync()` | В методах инициализации |
| `ApplicationContext` | `logger.info()`, `logger.warning()` (синхронная обертка) | В `initialize()` до создания event_bus |

### 5.2. Проблема потери логов

**Сценарий:**
1. `InfrastructureContext.initialize()` вызывается.
2. Компоненты пытаются логировать через `_safe_log_sync()`.
3. `event_bus` ещё не создал worker'ы для сессии.
4. События публикуются, но не обрабатываются.
5. **Логи теряются.**

### 5.3. Рекомендации

1. Добавить **буферизацию** в `EventBusLogger`:
   - Хранить сообщения в `_buffer: List[LogRecord]` до инициализации.
   - Вызывать `flush()` после создания worker'ов.
2. Альтернатива: Использовать `print()` с префиксом `[PRE-INIT]` для ранних логов.

---

## 6. Текущий порядок инициализации в main.py

### 6.1. Последовательность

```python
async def run_agent(goal: str, ...):
    # 1. Загрузка конфигурации
    config = get_config(profile='dev')
    
    # 2. Создание InfrastructureContext
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()
    # → Создаётся event_bus
    # → Создаётся lifecycle_manager
    # → Регистрируются провайдеры (LLM, DB)
    # → Вызывается lifecycle_manager.initialize_all()
    
    # 3. Создание session_logger
    session_logger = get_session_logger(session_id, ...)
    session_log_handler = create_session_log_handler(...)
    
    # 4. Создание ApplicationContext
    app_config = AppConfig.from_discovery(...)
    application_context = ApplicationContext(...)
    await application_context.initialize()
    # → Создаётся DataRepository
    # → Создаются компоненты (Skills, Tools, Services, Behaviors)
    # → Вызывается _initialize_components_with_dependencies()
    # → Создаётся LLMOrchestrator
    
    # 5. Создание агента
    agent_factory = AgentFactory(application_context)
    agent = await agent_factory.create_agent(goal=goal, config=agent_config)
    
    # 6. Запуск агента
    result = await agent.run(goal)
    # → BehaviorManager.initialize()
    # → Цикл рассуждений (BehaviorManager.generate_next_decision → ActionExecutor.execute_capability)
    
    # 7. Завершение (finally)
    await session_log_handler.shutdown()
    await application_context.shutdown()
    await infrastructure_context.shutdown()
    await shutdown_logging_system()
```

### 6.2. Точки сбоя

1. **Между шагом 2 и 3:** `event_bus` создан, но worker'ы ещё не запущены. Логи могут теряться.
2. **В шаге 4:** Если `AppConfig.from_discovery()` не найдёт компоненты, `application_context` будет пустым.
3. **В шаге 6:** Если `BehaviorManager` не инициализирован, `generate_next_decision()` выбросит исключение.
4. **В шаге 7:** Если `shutdown()` одного компонента падает, остальные могут не завершиться.

---

## 7. Проверка готовности компонентов

### 7.1. Текущие проверки

| Компонент | Проверка готовности | Метод |
|-----------|-------------------|-------|
| `InfrastructureContext` | ✅ `_initialized: bool` | Нет явного метода |
| `ApplicationContext` | ✅ `_initialized: bool` | Нет явного метода |
| `BaseComponent` | ✅ `_initialized: bool` | `_ensure_initialized()` |
| `BehaviorManager` | ❌ Нет проверки | Нет метода |
| `AgentRuntime` | ❌ Нет проверки | Нет метода |

### 7.2. Проблемы

1. **Нет единого интерфейса:** Каждый компонент проверяет состояние по-своему.
2. **Нет публичных методов:** `_ensure_initialized()` вызывается только внутри компонентов.
3. **Нет проверок в runtime:** `AgentRuntime.run()` не проверяет, что контекст инициализирован.

### 7.3. Рекомендации

1. Создать `ComponentState` enum: `CREATED`, `INITIALIZING`, `READY`, `FAILED`, `SHUTDOWN`.
2. Добавить метод `ensure_ready()` во все компоненты.
3. Вызывать `ensure_ready()` в начале каждого публичного метода.

---

## 8. Файловые операции (синхронные)

### 8.1. Найденные синхронные операции

| Файл | Метод | Проблема |
|------|-------|----------|
| `application/tools/file_tool.py` | `_read_file()`, `_write_file()` | Синхронный `open()` блокирует event loop |
| `infrastructure/storage/file_system_data_source.py` | `discover_prompts()`, `discover_contracts()` | Синхронный обход ФС |
| `infrastructure/storage/prompt_storage.py` | `load_prompt()` | Синхронное чтение |

### 8.2. Рекомендации

1. Установить `aiofiles` (уже есть в `requirements.txt`).
2. Заменить `open()` на `aiofiles.open()`.
3. Для `yaml.safe_load()` использовать `loop.run_in_executor()`.

---

## 9. Сводный список проблем

### Критические (блокирующие)

1. **`asyncio.run()` в `error_handler.py`** — может вызвать `RuntimeError` в асинхронном контексте.
2. **Отсутствие проверок готовности** — агент может запуститься с неинициализированным контекстом.
3. **Потеря логов при инициализации** — события публикуются до запуска worker'ов.

### Серьёзные (требуют исправления)

4. **Fire-and-forget задачи** — 4 места создают задачи без сохранения ссылки.
5. **Синхронные файловые операции** — блокируют event loop.
6. **Нет enum состояний** — невозможно отследить FAILED состояние.

### Желательные (улучшение архитектуры)

7. **Непоследовательные имена методов** — `initialize()` vs `start()`.
8. **Нет буферизации логов** — ранние логи теряются.
9. **Нет документации по жизненному циклу** — разработчики могут нарушать порядок.

---

## 10. План исправлений (кратко)

| Этап | Задача | Файлы | Приоритет |
|------|--------|-------|-----------|
| 1 | Введение `ComponentState` enum | `components/base_component.py`, `utils/lifecycle.py` | Высокий |
| 2 | Доработка `LifecycleManager` | `infrastructure/context/lifecycle_manager.py` | Высокий |
| 3 | Исправление `handle_errors` декоратора | `errors/error_handler.py` | Критический |
| 4 | Замена файловых операций на асинхронные | `application/tools/file_tool.py` | Средний |
| 5 | Буферизация логов | `infrastructure/logging/logger.py` | Высокий |
| 6 | Аудит `create_task` | Все файлы | Средний |
| 7 | Проверки готовности в `AgentRuntime` | `application/agent/runtime.py` | Высокий |
| 8 | Документирование | `docs/architecture/` | Низкий |

---

## 11. Приложения

### 11.1. Список всех файлов для анализа

**Контексты:**
- `core/infrastructure/context/infrastructure_context.py`
- `core/infrastructure/context/lifecycle_manager.py`
- `core/infrastructure/context/resource_registry.py`
- `core/application/context/application_context.py`
- `core/application/context/base_system_context.py`

**Компоненты:**
- `core/components/base_component.py`
- `core/application/skills/base_skill.py`
- `core/application/tools/base_tool.py`
- `core/application/services/base_service.py`
- `core/application/agent/components/behavior_manager.py`
- `core/application/agent/components/action_executor.py`
- `core/application/agent/runtime.py`

**Ошибки:**
- `core/errors/error_handler.py`

**Event Bus:**
- `core/infrastructure/event_bus/unified_event_bus.py`
- `core/infrastructure/logging/logger.py`
- `core/infrastructure/logging/handlers.py`

**Утилиты:**
- `core/utils/lifecycle.py`

### 11.2. Глоссарий

| Термин | Определение |
|--------|-------------|
| **Event Loop** | Цикл событий asyncio, управляющий выполнением корутин |
| **Fire-and-forget** | Задача, созданная без сохранения ссылки и ожидания |
| **ComponentState** | Enum состояний компонента (планируется) |
| **LifecycleManager** | Менеджер жизненного цикла инфраструктурных ресурсов |
| **BehaviorManager** | Менеджер паттернов поведения агента |

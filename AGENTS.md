# AGENTS.md — Agent v5 Development Guide

> For coding agents working in this repository. Read this before making any changes.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Run agent | `python main.py "Your question"` |
| All tests | `python -m pytest tests/ -v` |
| Single test | `python -m pytest tests/path/to/test_file.py -v` |
| Single test function | `python -m pytest tests/path/to/test_file.py::test_name -v` |
| Unit tests | `python -m pytest tests/unit/ -v` |
| Integration tests | `python -m pytest tests/integration/ -v` |
| With coverage | `python -m pytest tests/ --cov=core --cov-report=html` |
| Lint | `flake8 core/ && black core/ --check` |
| Architecture check | `python scripts/validation/check_skill_architecture.py` |
| YAML check | `python scripts/validation/check_yaml_syntax.py` |
| Consistency check | `python scripts/maintenance/check_consistency.py` |

---

## Philosophy

> **«Тяжёлые ресурсы — общие. Лёгкое поведение — изолированное. Конфигурация — строго иерархическая без дублирования.»**

---

## Code Style

### Language
- **Russian** for all docstrings, comments, log messages, and user-facing text
- **English** for code identifiers (variable names, function names, class names)

### Imports
- **Absolute imports only**: `from core.infrastructure.event_bus.unified_event_bus import EventType`
- **No relative imports** except in `__init__.py` files
- **Grouping**: stdlib → third-party → local (`core.*`), separated by blank lines
- Use `if TYPE_CHECKING:` guards for circular imports
- No wildcard imports; use explicit `__all__` in `__init__.py`

### Naming Conventions
| Element | Style | Example |
|---------|-------|---------|
| Classes | PascalCase | `AgentRuntime`, `BaseSkill` |
| Functions/Methods | snake_case | `run_agent`, `_execute_impl` |
| Private methods | Leading underscore | `_init_event_bus_logger` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_QUEUE_MAX_SIZE` |
| Variables | snake_case | `session_id`, `error_handler` |
| Enum values | UPPER_SNAKE_CASE | `ErrorSeverity.CRITICAL` |
| Files | snake_case | `base_component.py` |

### Type Hints
- Use on **all** function/method signatures
- Use `Optional[X]` (not `X | None`)
- Standard `typing` module: `Optional`, `Dict`, `List`, `Any`, `Union`, `Callable`, `Type`
- Forward references in quotes for circular types: `'ApplicationContext'`
- Return types required on all methods
- Pydantic `BaseModel` with `Field()` for data models
- `ClassVar` for class-level attributes

### Formatting
- Use **Black** for auto-formatting
- 4-space indentation (no tabs)
- Max line length: follow Black defaults
- Triple double-quotes for all docstrings

### Docstrings
- Russian language
- Use section headers in caps: `АРХИТЕКТУРА:`, `FEATURES:`, `ARGS:`, `RETURNS:`, `EXAMPLE:`
- Include code examples in ```python blocks where helpful

---

## Architecture Rules (CRITICAL)

### 1. Three-Layer Configuration Hierarchy

The system has three independent lifecycle layers with strict configuration boundaries:

| Layer | Config | Source | Lifecycle | Responsibility |
|-------|--------|--------|-----------|----------------|
| **Infrastructure** | `InfraConfig` | `core/config/defaults/{profile}.yaml` | Once per app | Heavy resources (LLM/DB providers, data paths) |
| **Application** | `AppConfig` | Auto-discovery из `data/prompts/`, `data/contracts/` | Once per agent | Versioned behavior (prompts, contracts), profile |
| **Session** | `AgentConfig` | Request parameters | Once per request | Execution context (goal, correlation_id, max_steps) |

**Critical rule:** If a parameter relates to a resource (provider, path) → `InfraConfig`. If to behavior (versions, profile) → `AppConfig`. If to request (goal, limits) → `AgentConfig`.

### 2. No Configuration Duplication

| Parameter | `InfraConfig` | `AppConfig` | `AgentConfig` | Why |
|-----------|---------------|-------------|---------------|-----|
| `llm_providers` | ✅ Only here | ❌ | ❌ | Heavy resources — shared across agents |
| `db_providers` | ✅ Only here | ❌ | ❌ | Connection pools — shared |
| `data_dir` | ✅ Only here | ❌ | ❌ | Data paths — system setting |
| `prompt_versions` | ❌ | ✅ Only here | ❌ | Versioning — app behavior |
| `contract_versions` | ❌ | ✅ Only here | ❌ | Versioning — app behavior |
| `profile` (prod/sandbox) | ❌ | ✅ Only here | ❌ | Behavior safety — app level |
| `goal` | ❌ | ❌ | ✅ Only here | Request context — session level |
| `max_steps` | ❌ | ❌ | ✅ Only here | Execution param — session level |
| `correlation_id` | ❌ | ❌ | ✅ Only here | Tracing — session level |

**Forbidden:**
- ❌ `agent_config` or `prompt_versions` in `core/config/defaults/*.yaml`
- ❌ `llm_providers`, `db_providers` в discovery
- ❌ `goal`, `max_steps` in config files — only in code at request time

### 3. All components inherit `BaseComponent`
- Skills → `BaseSkill`, Tools → `BaseTool`, Services → `BaseService`
- Never create custom base classes without justification
- `event_bus` is a **required** parameter — component fails to initialize if None

### 4. Components interact ONLY through `ActionExecutor`
```python
# ✅ CORRECT
result = await self.executor.execute_action(
    action_name="sql_tool.execute",
    parameters={"query": "..."},
    context=execution_context
)

# ❌ FORBIDDEN: Direct component access
other = self.application_context.components.get(...)
```

### 5. Logging — стандартный `logging` + `LoggingSession`

Система логирования работает через стандартный `logging` Python.
**НЕ используйте** `EventBusLogger`, `event_bus.publish()` для логов, `print()`.

#### Архитектура логирования

| Компонент | Логгер | Файл |
|-----------|--------|------|
| `InfrastructureContext` | `log_session.infra_logger` | `logs/{timestamp}/infra_context.log` |
| `ApplicationContext` | `log_session.app_logger` | `logs/{timestamp}/app_context.log` |
| Агент (сессия) | `log_session.create_agent_logger(agent_id)` | `logs/{timestamp}/agents/{timestamp}.log` |

**ПРАВИЛО:** 1 сессия агента = 1 файл лога. Файл создаётся автоматически при старте агента.

#### Как использовать в коде

```python
import logging
from core.infrastructure.logging.event_types import LogEventType

log = logging.getLogger(__name__)

# ✅ CORRECT: Логирование с типом события (фильтруется в терминале)
log.info("Поиск информации...", extra={"event_type": LogEventType.USER_PROGRESS})
log.warning("Превышен лимит", extra={"event_type": LogEventType.WARNING})

# ✅ CORRECT: Обычное логирование (только в файлы, НЕ в терминал)
log.debug("Внутреннее состояние компонента")

# ❌ FORBIDDEN: EventBusLogger для логов
await self.event_bus_logger.info("Message")

# ❌ FORBIDDEN: Прямой print() или logging.getLogger() без LoggingSession
print("debug")
logger = logging.getLogger(__name__); logger.info("...")  # без LoggingSession
```

#### Доступные типы событий (`LogEventType`)

```
USER_PROGRESS, USER_RESULT, USER_MESSAGE, USER_QUESTION
AGENT_START, AGENT_STOP, AGENT_THINKING, AGENT_DECISION
PLAN_CREATED, PLAN_UPDATED, STEP_STARTED, STEP_COMPLETED
TOOL_CALL, TOOL_RESULT, TOOL_ERROR
LLM_CALL, LLM_RESPONSE, LLM_ERROR
DB_QUERY, DB_RESULT, DB_ERROR
SYSTEM_INIT, SYSTEM_READY, SYSTEM_SHUTDOWN, SYSTEM_ERROR
INFO, DEBUG, WARNING, ERROR, CRITICAL
```

#### Фильтрация в терминале

В `LoggingConfig.console.allowed_terminal_events` задаётся набор `LogEventType`, которые выводятся в консоль.
Записи **без** `event_type` **НЕ попадают** в терминал — только в файлы.

```python
from core.config.logging_config import LoggingConfig, ConsoleConfig
from core.infrastructure.logging.event_types import LogEventType

config = LoggingConfig(
    console=ConsoleConfig(
        allowed_terminal_events={
            LogEventType.USER_PROGRESS,
            LogEventType.USER_RESULT,
            LogEventType.AGENT_START,
            LogEventType.AGENT_STOP,
        }
    )
)
```

#### Структура файлов логов

```
logs/
└── 2026-04-10_14-30-00/          # Генерируется один раз при запуске
    ├── infra_context.log          # Инфраструктура (провайдеры, БД, LLM)
    ├── app_context.log            # Приложение (компоненты, сервисы)
    └── agents/
        ├── 2026-04-10_14-31-12.log  # Сессия агента #1
        └── 2026-04-10_14-35-40.log  # Сессия агента #2
```

#### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `core/infrastructure/logging/session.py` | `LoggingSession` — ядро, создаёт директорию и хендлеры |
| `core/infrastructure/logging/event_types.py` | `LogEventType` — enum типов событий для логов |
| `core/infrastructure/logging/handlers.py` | `EventTypeFilter` — фильтр для терминала |
| `core/config/logging_config.py` | `LoggingConfig`, `ConsoleConfig` — конфигурация |

### 6. LLM calls ONLY through `LLMOrchestrator` (via executor)
```python
# ✅ CORRECT
result = await self.executor.execute_action(
    action_name="llm.generate_structured",
    parameters={"prompt": "...", "structured_output": {...}},
    context=execution_context
)

# ❌ FORBIDDEN: Direct provider calls
response = await llm.generate(prompt)
```

### 7. Infrastructure Context is Read-Only from Application Layer
```python
# ✅ CORRECT: Read-only access
prompt = app_ctx.infrastructure.prompt_storage.load(cap, ver)

# ❌ FORBIDDEN: Modifying infrastructure
app_ctx.infrastructure.register_resource("x", y)
```

### 8. No Shared State Between Agents
```python
# ✅ CORRECT: Isolated cache per agent
class PromptService:
    def __init__(self, application_context):
        self._isolated_cache = {}

# ❌ FORBIDDEN: Shared cache = state leak
class PromptService:
    _shared_cache = {}
```
- Providers (`LLMProvider`, `DBProvider`) are shared; caches are NOT
- Each agent gets isolated `ApplicationContext`

### 9. Resources Preloaded at Init — Zero Filesystem Access During Execution
```python
# At initialization (once):
await prompt_storage.load("planning.create_plan", "v1.0.0")

# During execution (from cache, 0 FS calls):
prompt = prompt_service.get_prompt("planning.create_plan")
```

### 10. Profile-Based Version Validation
| Profile | Allowed statuses | Behavior |
|---------|-----------------|----------|
| `prod` | Only `active` | Exception on violation |
| `sandbox` | `draft` + `active` | Warning for `draft` |
| `dev` | All statuses | No restrictions |

### 11. NO FALLBACK — Strict Discovery Mode
ВСЕ компоненты загружаются автоматически из discovery. Fallback запрещён.

```python
# ✅ CORRECT: Компонент либо загружен полностью, либо ошибка
prompt = self.get_prompt(capability_name)
if not prompt or not prompt.content:
    raise ValueError(f"Промпт '{capability_name}' не загружен! Проверьте YAML в data/prompts/")

# ❌ FORBIDDEN: Fallback промпты
DEFAULT_PROMPT = "Default prompt for ..."  # ЗАПРЕЩЕНО
fallback_prompt = prompt or DEFAULT_PROMPT  # ЗАПРЕЩЕНО
```

**Почему:**
- Fallback создаёт скрытые баги — система работает но с неправильными промптами
- Ошибка должна всплывать сразу при инициализации, а не молчаливо игнорироваться
- Discovery должен находить ВСЕ компоненты автоматически

**Как работает:**
- `AppConfig.from_discovery()` сканирует `data/prompts/` и `data/contracts/`
- Для КАЖДОГО найденного компонента создаётся ComponentConfig с версиями
- Обязательные сервисы (sql_generation, sql_query_service и т.д.) НЕ исключаются
- Если компонент не найден в discovery → Exception при инициализации

### 12. Hot Version Switching via Cloning
```python
# Create new context with new version — old one untouched
new_ctx = await old_ctx.clone_with_version_override(
    prompt_overrides={"planning.create_plan": "v2.0.0"}
)  # < 50 ms (cache-only)
```

### 13. `_execute_impl` returns `Dict[str, Any]`, NOT `ExecutionResult`
### 14. No retry logic in skills — handled by infrastructure

### 15. Empty Query Log — статистика пустых результатов
```python
# Запись пустого результата в SessionContext
session_context.record_empty_result(
    tool="sql_tool.execute",
    tables=["audits", "violations"],
    filters={"planned_date": "2030"},
    columns_used=["id", "planned_date"]
)

# Проверка порога для активации режима исследования
if session_context.needs_exploration(threshold=2):
    exploration_context = session_context.get_exploration_context()
```

### 16. Exploration Mode — автоматическое зондирование данных
Когда 2+ запроса вернули 0 строк, LLM получает универсальные правила зондирования:
- `SELECT MIN(col), MAX(col), COUNT(*) FROM {table}`
- `SELECT DISTINCT col, COUNT(*) GROUP BY col LIMIT 10`
- `SELECT COUNT(*) WHERE col IS NULL`

---

## Matrix of Responsibility

| Component | ✅ Does | 🚫 Does NOT | 🔄 Communicates via |
|-----------|---------|------------|-----------------|
| `AgentFactory` | Component initialization, dependency injection | Business logic, execution | Creates all components for Runtime |
| `AgentRuntime` | Thin orchestrator: loop, step counter, final result | Component creation, decision logic | Calls phases, `Pattern.decide()` |
| `ReActPattern` | Context analysis, reasoning, decision generation | Direct LLM/DB calls, state storage | `LLMOrchestrator`, `SessionContext` (read) |
| `ActionExecutor` | Routing, contract validation, metric collection | Business logic, decision logic | `Skill.execute_impl()`, `ContractRegistry` |
| `SafeExecutor` | Retry, circuit breaker, idempotency | Response generation, parsing | `ActionExecutor`, `RetryPolicy` |
| `LLMOrchestrator` | Provider calls, structured JSON parsing, timeout | Result interpretation | `LLMProvider`, `StructuredOutputParser` |
| `SessionContext` | Step/observation/plan storage | Branching logic, fallback | Read/write via runtime |
| Skills/Tools | Business logic, input validation | Agent loop, direct calls | `ActionExecutor` only |
| Phases | Single responsibility (decision, execution, observation, etc.) | Creating components directly | `ActionExecutor`, injected dependencies |

---

## Hard Architectural Prohibitions (What Breaks the System)

| Component | Prohibition | Why |
|-----------|-------------|-----|
| `ReActPattern` | Direct `executor.execute()` without `Decision` | Breaks decision/execution separation |
| `ActionExecutor` | Store `confidence` or `no_progress` | This is analysis state, not routing |
| `LLMOrchestrator` | Interpret result (`row_count`, `schema mismatch`) | Business validation belongs in Skill/Analysis |
| Skills/Tools | Import `AgentRuntime` / `SessionContext` | Breaks isolation, makes untestable |
| `SessionContext` | Branching logic or fallback | Passive storage, not active agent |
| `SafeExecutor` | Generate prompts or parse LLM | Orchestrator responsibility |

---

## File Modification Rules

| File | Rule | Why |
|------|------|-----|
| `.gitignore` | **ЗАПРЕЩЕНО ИЗМЕНЯТЬ** | Критический файл игнорирования Git. Изменение может привести к коммиту мусора или потере важных файлов. |
| `core/config/defaults/*.yaml` | Только инфраструктурные параметры | Конфигурация ресурсов (LLM, DB), не поведения |
| `data/prompts/**/*.yaml` | Только промпты и контракты | Поведение агента, версионируется отдельно |

---

## Error Handling

- Custom exceptions inherit from `AgentBaseError`
- Use centralized `ErrorHandler` singleton: `get_error_handler()`
- Severity levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- CRITICAL/HIGH errors are re-raised (never swallowed)
- Use `@error_handler.handle_errors()` decorator where applicable

---

## Async Patterns

- Entire codebase is async/await
- Entry point: `asyncio.run(main_async())`
- All key methods are `async`: `initialize()`, `shutdown()`, `execute()`, `handle()`
- Synchronous fallbacks use `_sync` suffix: `info_sync()`, `error_sync()`

---

## Project Structure

```
Agent_v5/
├── core/
│   ├── agent/
│   │   ├── runtime.py              # Thin orchestrator (loop only)
│   │   ├── agent_factory.py       # Factory for component initialization
│   │   ├── phases/               # Execution phases
│   │   │   ├── decision_phase.py
│   │   │   ├── policy_check_phase.py
│   │   │   ├── execution_phase.py
│   │   │   ├── observation_phase.py
│   │   │   ├── context_update_phase.py
│   │   │   ├── final_answer_phase.py
│   │   │   └── error_recovery_phase.py
│   │   ├── behaviors/             # Patterns (ReAct, Planning, etc.)
│   │   └── components/           # Agent-specific components
│   ├── application_context/    # ApplicationContext (isolated per agent)
│   ├── config/
│   │   ├── defaults/           # InfraConfig ONLY (dev.yaml, prod.yaml)
│   │   └── version.py          # Version info (5.46.1)
│   ├── errors/                 # Exceptions + ErrorHandler
│   ├── infrastructure/         # Providers, EventBus, logging, storage
│   ├── models/                 # Data models and enums
│   ├── security/               # Authorization
│   ├── services/               # Business services and skills
│   └── session_context/        # Session/Step contexts
├── data/                       # SINGLE source of truth for resources
│   ├── prompts/                # Auto-discovery: data/prompts/{type}/{component}/{version}.yaml
│   └── contracts/              # Auto-discovery: data/contracts/{type}/{component}/{version}.yaml
├── docs/
│   ├── RULES.MD                # Full development rules
│   └── architecture/ideal.md   # Target architecture blueprint
├── scripts/                    # Validation, maintenance, CLI tools
├── tests/                      # Test suite
├── main.py                     # Entry point
└── .coveragerc                 # Coverage config
```

---

## Before Committing

- [ ] All tests pass: `python -m pytest tests/ -v`
- [ ] Architecture check: `python scripts/validation/check_skill_architecture.py`
- [ ] YAML check: `python scripts/validation/check_yaml_syntax.py`
- [ ] No `print()` в core code
- [ ] No `EventBusLogger` для логов — используйте `logging` с `LogEventType`
- [ ] Логирование через `logging.getLogger()` + `extra={"event_type": LogEventType.XXX}`
- [ ] No direct component access (only via `ActionExecutor`)
- [ ] No direct LLM calls (only via orchestrator)
- [ ] `_execute_impl` returns dict, not `ExecutionResult`
- [ ] Russian docstrings and comments
- [ ] Type hints on all signatures
- [ ] No config duplication across layers
- [ ] Infrastructure not modified from application layer

---

## Red Flags (Stop and Fix)

| Symptom | Problem | Action |
|---------|---------|--------|
| `agent_config` in `dev.yaml` | Config duplication | Remove field, versions come from discovery |
| `prompt_versions` in `dev.yaml` | Config duplication | Remove field, versions come from discovery |
| `type_provider` in configs | Incorrect provider registration | Replace with `provider_type` |
| `id(ctx1.prompt_service) == id(ctx2.prompt_service)` | Shared prompt cache | Move `PromptService` to `ApplicationContext` |
| FS calls after `initialize()` | No preloading | Implement caching in `PromptService`/`ContractService` |
| `prod` accepts `draft` versions | Missing status validation | Add `_validate_status_by_profile()` check |

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `docs/RULES.MD` | Full development rules and architecture docs |
| `docs/architecture/ideal.md` | Target architecture blueprint and maturity checklist |
| `core/agent/agent_factory.py` | Factory for component initialization |
| `core/agent/runtime.py` | Thin orchestrator (loop only) |
| `core/version.py` | Version info (5.46.1) |
| `core/agent/components/base_component.py` | Base class for all components |
| `core/agent/components/action_executor.py` | Component interaction gateway |
| `core/infrastructure/logging/session.py` | `LoggingSession` — ядро файлового логирования |
| `core/infrastructure/logging/event_types.py` | `LogEventType` — типы событий для логов |
| `core/infrastructure/providers/llm/llm_orchestrator.py` | LLM call orchestration |
| `core/errors/error_handler.py` | Centralized error handling |
| `core/infrastructure/event_bus/unified_event_bus.py` | Event bus for metrics/telemetry (НЕ для логов) |
| `tests/conftest.py` | Shared pytest fixtures (Mock LLM, fake contexts) |

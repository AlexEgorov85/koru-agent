# 📋 ПЛАН РЕФАКТОРИНГА АРХИТЕКТУРЫ АГЕНТА

**Версия:** 5.0 (ФИНАЛЬНАЯ)  
**Дата:** 2026-03-30  
**Статус:** Готов к реализации

**ИЗМЕНЕНИЯ В ВЕРСИИ 5.0:**
- ✅ Убран `_should_stop()` из Runtime
- ✅ Убрана логика загрузки pattern из Runtime (PatternFactory)
- ✅ Усилен Context (query helpers)
- ✅ Зафиксирован ExecutionResult
- ✅ Убран RETRY как отдельный DecisionType
- ✅ Добавлено: как избежать god-object в Pattern

---

## 🎯 ГЛАВНЫЙ ПРИНЦИП

```text
Pattern — думает
Runtime — управляет
Executor — делает
```

**ВСЁ.**

---

## 🚀 ЦЕЛИ РЕФАКТОРИНГА

1. **Pattern — единственный мозг:** вся логика решений в одном месте
2. **Runtime — только цикл:** orchestration без принятия решений
3. **Executor — только выполнение:** без классификации и decision
4. **Context — умный источник состояния:** query helpers для Pattern
5. **Чистый код без legacy:** удаляем, а не улучшаем

---

## ✅ ЦЕЛЕВАЯ АРХИТЕКТУРА (ВЕРСИЯ 5.0)

### Общая схема

```
┌──────────────────────────┐
│      AgentRuntime        │   ← orchestration (цикл)
│                          │
│  - while True:           │
│  -   pattern.decide()    │
│  -   executor.execute()  │
│  -   context.update()    │
│  -   if FINISH: return   │
└─────────────┬────────────┘
              │
              │ Decision
              ▼
┌──────────────────────────┐
│     BehaviorPattern      │   ← 🧠 ВСЯ логика решений
│                          │
│  - decide(context)       │
│  - анализирует ошибки    │
│  - решает retry/switch   │
│  - решает finish/fail    │
└─────────────┬────────────┘
              │
              │ Action
              ▼
┌──────────────────────────┐
│     ActionExecutor       │   ← ⚙️ выполнение действий
│                          │
│  - registry.get(name)    │
│  - component.run()       │
│  - без decision logic    │
└─────────────┬────────────┘
              │
              ▼
        Capabilities / Tools
```

### Ключевые изменения (Версия 5.0)

| Компонент | Версия 4.0 | Версия 5.0 |
|-----------|------------|------------|
| **Runtime._should_stop()** | Есть | ❌ **Удалить** |
| **Runtime SWITCH_STRATEGY** | Загружает pattern | ❌ **PatternFactory** |
| **Context** | Только хранение | ✅ **Query helpers** |
| **ExecutionResult** | Не определён | ✅ **Зафиксирован** |
| **DecisionType.RETRY** | Есть | ❌ **Удалить** |

---

## 🧠 КОНТРАКТЫ КОМПОНЕНТОВ (ВЕРСИЯ 5.0)

### Pattern — единственный decision-maker

```python
class BehaviorPattern(Protocol):

    async def decide(
        self,
        context: AgentContext
    ) -> Decision:
        """
        ЕДИНСТВЕННОЕ место принятия решений.
        """
```

### Decision модель (без RETRY)

```python
class DecisionType(Enum):
    ACT = "act"                    # Выполнить действие
    FINISH = "finish"              # Завершить успешно
    FAIL = "fail"                  # Завершить с ошибкой
    SWITCH_STRATEGY = "switch"     # Переключить стратегию


@dataclass
class Decision:
    type: DecisionType
    
    # Для ACT
    action: Optional[Action] = None
    reasoning: str = ""
    
    # Для SWITCH_STRATEGY
    next_pattern: Optional[str] = None
    
    # RETRY — это просто ACT с тем же действием
    # Не нужен отдельный тип!
```

### Runtime — только цикл (без _should_stop)

```python
class AgentRuntime:

    async def run(self, context: AgentContext) -> ExecutionResult:

        for step in range(self.max_steps):
            # Pattern решает всё
            decision = await self.pattern.decide(context)

            # Runtime только исполняет
            if decision.type == DecisionType.ACT:
                result = await self.executor.execute(decision.action)
                context.record_step(result)

            elif decision.type == DecisionType.SWITCH_STRATEGY:
                # PatternFactory загружает, Runtime не знает как
                self.pattern = self.pattern_factory.create(decision.next_pattern)

            elif decision.type == DecisionType.FINISH:
                return result

            elif decision.type == DecisionType.FAIL:
                return ExecutionResult.failure(decision.reasoning)

        # max_steps исчерпан
        return ExecutionResult.failure("Max steps exceeded")
```

**Ключевое:** нет `_should_stop()` — Pattern сам решает через FINISH/FAIL

---

### PatternFactory — загрузка стратегий

```python
class PatternFactory:

    def __init__(self, registry: Dict[str, Type[BehaviorPattern]]):
        self.registry = registry

    def create(self, pattern_name: str, **kwargs) -> BehaviorPattern:
        """
        Runtime не знает как загружаются паттерны.
        """
        pattern_class = self.registry.get(pattern_name)
        if not pattern_class:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        return pattern_class(**kwargs)
```

---

### Context — умный источник состояния (с query helpers)

```python
@dataclass
class AgentContext:
    goal: str
    history: List[Step]
    failures: List[Failure]
    state: Dict[str, Any]

    # Запись
    def record_step(self, step: Step): ...
    def record_failure(self, failure: Failure): ...
    
    # Query helpers (НЕ decision logic!)
    def get_last_steps(self, n: int) -> List[Step]:
        return self.history[-n:]
    
    def get_recent_failures(self, n: int) -> List[Failure]:
        return self.failures[-n:]
    
    def count_failures_by_type(self, error_type: ErrorType) -> int:
        return sum(1 for f in self.failures if f.error_type == error_type)
    
    def has_no_progress(self, n_steps: int) -> bool:
        """Проверка: были ли изменения за последние n шагов."""
        if len(self.history) < n_steps:
            return False
        recent = self.history[-n_steps:]
        # Проверяем были ли успешные действия
        return all(step.result.is_empty() for step in recent)
    
    def get_consecutive_failures(self) -> int:
        """Счётчик последовательных ошибок."""
        count = 0
        for step in reversed(self.history):
            if step.result.is_failure():
                count += 1
            else:
                break
        return count
```

**Важно:** query helpers НЕ принимают решения, только агрегируют данные

---

### ExecutionResult — зафиксированная модель

```python
@dataclass
class ExecutionResult:
    success: bool
    data: Any
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, data: Any, **metadata) -> 'ExecutionResult':
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def failure(cls, error: Union[str, Exception], **metadata) -> 'ExecutionResult':
        if isinstance(error, str):
            return cls(success=False, data=None, error=Exception(error), metadata=metadata)
        return cls(success=False, data=None, error=error, metadata=metadata)
    
    def is_failure(self) -> bool:
        return not self.success
    
    def is_empty(self) -> bool:
        """Проверка: результат пустой (для has_no_progress)."""
        return self.data is None or self.data == {}
```

---

### ErrorClassifier — только классификация

```python
class ErrorClassifier:
    
    def classify(self, error: Exception) -> ErrorType:
        """
        ТОЛЬКО классификация.
        Без decision!
        """
        if isinstance(error, (TimeoutError, ConnectionError)):
            return ErrorType.TRANSIENT
        elif isinstance(error, ValidationError):
            return ErrorType.LOGIC
        elif isinstance(error, PermissionError):
            return ErrorType.FATAL
        else:
            return ErrorType.UNKNOWN
```

---

### FailureMemory — только хранение

```python
class FailureMemory:
    
    def __init__(self, max_age_minutes: int = 30):
        self._failures: List[Failure] = []
        self.max_age_minutes = max_age_minutes
    
    def record(self, failure: Failure):
        self._failures.append(failure)
        self._cleanup_old()
    
    def get_failures(self, capability: str = None) -> List[Failure]:
        """Только чтение. Без decision!"""
        failures = self._failures
        if capability:
            failures = [f for f in failures if f.capability == capability]
        return failures
    
    def _cleanup_old(self):
        """Удалить старые записи."""
        cutoff = datetime.now() - timedelta(minutes=self.max_age_minutes)
        self._failures = [f for f in self._failures if f.timestamp > cutoff]
```

---

### RetryPolicy — только лимиты

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 5.0
    
    def get_delay(self, attempt: int) -> float:
        """Экспоненциальная задержка."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
```

---

### ActionExecutor — только выполнение

```python
class ActionExecutor:
    
    async def execute(self, action: Action) -> ExecutionResult:
        """
        ТОЛЬКО выполнение.
        Без обработки ошибок.
        """
        component = self.registry.get(action.name)
        if not component:
            return ExecutionResult.failure(f"Component not found: {action.name}")
        
        return await component.run(action.params)
```

---

### SafeExecutor — только network retry

```python
class SafeExecutor:
    
    def __init__(
        self,
        executor: ActionExecutor,
        retry_policy: RetryPolicy
    ):
        self.executor = executor
        self.retry_policy = retry_policy
    
    async def execute(self, action: Action) -> ExecutionResult:
        """
        ТОЛЬКО network/timeout retry.
        Без decision logic.
        """
        for attempt in range(self.retry_policy.max_retries):
            try:
                return await self.executor.execute(action)
            except (TimeoutError, ConnectionError) as e:
                if attempt == self.retry_policy.max_retries - 1:
                    return ExecutionResult.failure(e)
                await asyncio.sleep(self.retry_policy.get_delay(attempt))
        
        return ExecutionResult.failure("Max retries exceeded")
```

---

## 📝 ПЛАН РАБОТ (ПО ЭТАПАМ, ВЕРСИЯ 5.0)

### Этап 0: Базовый тег (Критичный)

**Команда:**
```bash
git tag refactor/before-start
git push origin refactor/before-start
```

---

### Этап 1: Удалить BehaviorManager (Высокий приоритет)

**Git-тег:** `refactor/stage-1-behavior-manager-removed`

**Файлы:**
- ❌ `core/agent/components/behavior_manager.py` (удалить)
- 📝 `core/agent/runtime.py` (изменения)
- 📝 `core/agent/behaviors/base_behavior_pattern.py` (изменения)

**Задачи:**

1.1. Удалить BehaviorManager из Runtime:
```python
# БЫЛО
self.behavior_manager = BehaviorManager(...)
decision = await self.behavior_manager.generate_next_decision(...)

# СТАЛО
self.pattern = ReActPattern(...)
decision = await self.pattern.decide(context)
```

1.2. Переименовать методы паттерна:
```python
# БЫЛО
async def analyze_context(...) -> Dict
async def generate_decision(...) -> BehaviorDecision

# СТАЛО
async def decide(context: AgentContext) -> Decision
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 1 - BehaviorManager удалён

- Pattern напрямую в Runtime
- Переименовано: generate_decision() → decide()
- Decision — единственный контракт
- Удалён behavior_manager.py
"
git tag refactor/stage-1-behavior-manager-removed
git push origin main && git push origin --tags
```

---

### Этап 2: Удалить decision из ErrorHandler (Высокий приоритет)

**Git-тег:** `refactor/stage-2-error-handler-simplified`

**Файлы:**
- 📝 `core/agent/components/error_handler.py` (изменения)
- ❌ `core/agent/components/error_handler.py` (переименовать в `error_classifier.py`)

**Задачи:**

2.1. Переименовать ErrorHandler в ErrorClassifier:
```python
# БЫЛО
class ErrorHandler:
    async def handle_error(...) -> ErrorHandlingResult:
        # Решение о retry/switch/fail

# СТАЛО
class ErrorClassifier:
    def classify(error: Exception) -> ErrorType:
        # ТОЛЬКО классификация
```

2.2. Переместить decision в Pattern:
```python
# Pattern анализирует failures в context
errors = context.get_failures()
if len(errors) >= 3:
    return Decision(type=DecisionType.SWITCH_STRATEGY)
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 2 - Decision перемещён в Pattern

- ErrorHandler → ErrorClassifier (только классификация)
- Pattern решает retry/switch/fail
- Удалён handle_error()
"
git tag refactor/stage-2-error-handler-simplified
git push origin main && git push origin --tags
```

---

### Этап 3: Удалить should_switch_pattern из FailureMemory (Средний приоритет)

**Git-тег:** `refactor/stage-3-failure-memory-simplified`

**Файлы:**
- 📝 `core/agent/components/failure_memory.py` (изменения)

**Задачи:**

3.1. Удалить should_switch_pattern():
```python
# БЫЛО
def should_switch_pattern(self, capability: str) -> bool:
    # Решение о переключении

# СТАЛО
def get_failures(self, capability: str = None) -> List[Failure]:
    # ТОЛЬКО чтение
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 3 - FailureMemory упрощён

- Удалён should_switch_pattern()
- Pattern читает failures напрямую
- FailureMemory только хранит данные
"
git tag refactor/stage-3-failure-memory-simplified
git push origin main && git push origin --tags
```

---

### Этап 4: Упростить AgentPolicy (Средний приоритет)

**Git-тег:** `refactor/stage-4-policy-simplified`

**Файлы:**
- 📝 `core/agent/components/policy.py` (изменения)

**Задачи:**

4.1. Переименовать в RetryPolicy:
```python
# БЫЛО
class AgentPolicy:
    def evaluate(...) -> RetryResult
    def should_fallback(...) -> bool

# СТАЛО
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 5.0
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 4 - AgentPolicy упрощён

- Переименовано: AgentPolicy → RetryPolicy
- Удалены: should_fallback(), should_stop_no_progress(), detect_loop()
- Осталось: только retry limits
"
git tag refactor/stage-4-policy-simplified
git push origin main && git push origin --tags
```

---

### Этап 5: Упростить Runtime до цикла (Высокий приоритет)

**Git-тег:** `refactor/stage-5-runtime-simplified`

**Файлы:**
- 📝 `core/agent/runtime.py` (значительные изменения)
- ✨ `core/agent/pattern_factory.py` (новый)

**Задачи:**

5.1. Удалить _should_stop():
```python
# БЫЛО
while not self._should_stop(context):
    decision = await self.pattern.decide(context)

# СТАЛО
for step in range(self.max_steps):
    decision = await self.pattern.decide(context)
    
    if decision.type == FINISH:
        return result
    elif decision.type == FAIL:
        return ExecutionResult.failure(...)
```

5.2. Вынести загрузку pattern в factory:
```python
# БЫЛО
elif decision.type == SWITCH_STRATEGY:
    self.pattern = self._load_pattern(decision.next_pattern)

# СТАЛО
elif decision.type == SWITCH_STRATEGY:
    self.pattern = self.pattern_factory.create(decision.next_pattern)
```

5.3. Создать PatternFactory:
```python
class PatternFactory:
    def create(self, pattern_name: str, **kwargs) -> BehaviorPattern:
        pattern_class = self.registry.get(pattern_name)
        return pattern_class(**kwargs)
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 5 - Runtime упрощён до цикла

- Удалён _should_stop()
- Pattern решает когда остановиться (FINISH/FAIL)
- Вынесена загрузка pattern в PatternFactory
- Runtime не знает как загружаются паттерны
- ~200 строк вместо 1206
"
git tag refactor/stage-5-runtime-simplified
git push origin main && git push origin --tags
```

---

### Этап 6: Усилить Context query helpers (Средний приоритет)

**Git-тег:** `refactor/stage-6-context-enhanced`

**Файлы:**
- 📝 `core/agent/context.py` (новый) или `core/session_context/session_context.py`

**Задачи:**

6.1. Добавить query helpers:
```python
class AgentContext:
    def get_recent_failures(self, n: int) -> List[Failure]: ...
    def count_failures_by_type(self, error_type: ErrorType) -> int: ...
    def has_no_progress(self, n_steps: int) -> bool: ...
    def get_consecutive_failures(self) -> int: ...
```

6.2. Обновить Pattern для использования helpers:
```python
# БЫЛО (ручная агрегация)
errors = [s for s in context.history if s.is_failure()]
if len(errors) >= 3:
    ...

# СТАЛО
if context.get_consecutive_failures() >= 3:
    return Decision(SWITCH_STRATEGY)
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 6 - Context усилен query helpers

- Добавлены: get_recent_failures(), count_failures_by_type()
- Добавлены: has_no_progress(), get_consecutive_failures()
- Pattern использует helpers вместо ручной агрегации
- Без decision logic в Context
"
git tag refactor/stage-6-context-enhanced
git push origin main && git push origin --tags
```

---

### Этап 7: Зафиксировать ExecutionResult (Низкий приоритет)

**Git-тег:** `refactor/stage-7-execution-result-fixed`

**Файлы:**
- 📝 `core/models/data/execution.py` (изменения)

**Задачи:**

7.1. Зафиксировать модель:
```python
@dataclass
class ExecutionResult:
    success: bool
    data: Any
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, data: Any, **metadata) -> 'ExecutionResult': ...
    
    @classmethod
    def failure(cls, error: Union[str, Exception], **metadata) -> 'ExecutionResult': ...
    
    def is_failure(self) -> bool: ...
    def is_empty(self) -> bool: ...
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 7 - ExecutionResult зафиксирован

- Добавлены: success, data, error, metadata
- Добавлены: success(), failure() factory методы
- Добавлены: is_failure(), is_empty() helpers
- Единая модель для всех компонентов
"
git tag refactor/stage-7-execution-result-fixed
git push origin main && git push origin --tags
```

---

### Этап 8: Убрать RETRY как DecisionType (Низкий приоритет)

**Git-тег:** `refactor/stage-8-retry-type-removed`

**Файлы:**
- 📝 `core/agent/behaviors/base.py` (изменения)

**Задачи:**

8.1. Удалить RETRY из DecisionType:
```python
# БЫЛО
class DecisionType(Enum):
    ACT = "act"
    RETRY = "retry"      # ← Удалить
    FINISH = "finish"
    FAIL = "fail"
    SWITCH_STRATEGY = "switch"

# СТАЛО
class DecisionType(Enum):
    ACT = "act"
    FINISH = "finish"
    FAIL = "fail"
    SWITCH_STRATEGY = "switch"
```

8.2. Обновить Pattern (RETRY = ACT с тем же действием):
```python
# БЫЛО
return Decision(type=DecisionType.RETRY)

# СТАЛО
return Decision(type=DecisionType.ACT, action=previous_action)
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 8 - RETRY удалён из DecisionType

- RETRY = ACT с тем же действием
- Упрощена модель Decision
- Pattern возвращает ACT для повторных попыток
"
git tag refactor/stage-8-retry-type-removed
git push origin main && git push origin --tags
```

---

### Этап 9: Упростить Executor (Низкий приоритет)

**Git-тег:** `refactor/stage-9-executor-simplified`

**Файлы:**
- 📝 `core/agent/components/action_executor.py` (изменения)
- 📝 `core/agent/components/safe_executor.py` (изменения)

**Задачи:**

9.1. Удалить обработку ошибок из ActionExecutor:
```python
# БЫЛО
try:
    return await component.run(params)
except Exception as e:
    return ExecutionResult.failure(e)

# СТАЛО
return await component.run(params)
```

9.2. SafeExecutor только network retry:
```python
class SafeExecutor:
    async def execute(self, action: Action):
        for attempt in range(MAX_RETRIES):
            try:
                return await self.executor.execute(action)
            except TransientError:
                continue
        raise ExecutionError()
```

**Команда для коммита:**
```bash
git add .
git commit -m "refactor: Этап 9 - Executor упрощён

- ActionExecutor только выполнение
- SafeExecutor только network retry
- Удалена классификация ошибок
- Удалены decision logic
"
git tag refactor/stage-9-executor-simplified
git push origin main && git push origin --tags
```

---

## 📅 ДОРОЖНАЯ КАРТА С GIT-ТЕГАМИ (ВЕРСИЯ 5.0)

| Этап | Компонент | Приоритет | Оценка (часы) | Git-тег |
|------|-----------|-----------|---------------|---------|
| 0 | **Базовый тег** | Критичный | 5 мин | `refactor/before-start` |
| 1 | **BehaviorManager удалён** | Высокий | 6 | `refactor/stage-1-behavior-manager-removed` |
| 2 | **ErrorHandler → ErrorClassifier** | Высокий | 4 | `refactor/stage-2-error-handler-simplified` |
| 3 | **FailureMemory упрощён** | Средний | 3 | `refactor/stage-3-failure-memory-simplified` |
| 4 | **AgentPolicy → RetryPolicy** | Средний | 3 | `refactor/stage-4-policy-simplified` |
| 5 | **Runtime: цикл без _should_stop** | Высокий | 8 | `refactor/stage-5-runtime-simplified` |
| 6 | **Context: query helpers** | Средний | 4 | `refactor/stage-6-context-enhanced` |
| 7 | **ExecutionResult зафиксирован** | Низкий | 2 | `refactor/stage-7-execution-result-fixed` |
| 8 | **RETRY удалён из DecisionType** | Низкий | 2 | `refactor/stage-8-retry-type-removed` |
| 9 | **Executor упрощён** | Низкий | 4 | `refactor/stage-9-executor-simplified` |
| **Финал** | **Завершение** | - | 5 мин | `refactor/complete` |
| **Итого** | | | **36 часов** | |

---

## 🛡️ БЕЗОПАСНОСТЬ: КАК ОТКАТИТЬСЯ

### Сценарий 1: Откат после этапа 5

```bash
git reset --hard refactor/stage-4-policy-simplified
git push --force origin main
```

### Сценарий 2: Аварийный откат

```bash
git reset --hard refactor/before-start
git clean -fd
git push --force origin main
```

---

## 🧪 ТЕСТОВАНИЕ

### Чек-лист перед коммитом этапа

```markdown
## Чек-лист этапа №X

- [ ] Все тесты проходят (`pytest -xvs`)
- [ ] Интеграционный тест проходит (`python main.py`)
- [ ] Нет `TODO` и `FIXME` в коде этапа
- [ ] Нет unused imports
- [ ] Нет dead code (удалить!)
- [ ] Git-тег создан и отправлен
```

---

## 🎯 КАК ИЗБЕЖАТЬ GOD-OBJECT В PATTERN

### Риск

Pattern стал единственным decision-maker → риск разрастания до 2000+ строк

### Решение: внутреннее разделение

```python
class BehaviorPattern:
    """Единый интерфейс, но внутреннее разделение."""
    
    def __init__(
        self,
        reasoning_engine: ReasoningEngine,
        strategy_selector: StrategySelector,
        action_generator: ActionGenerator
    ):
        self.reasoning_engine = reasoning_engine
        self.strategy_selector = strategy_selector
        self.action_generator = action_generator
    
    async def decide(self, context: AgentContext) -> Decision:
        # 1. Анализ ситуации
        analysis = await self.reasoning_engine.analyze(context)
        
        # 2. Выбор стратегии
        strategy = self.strategy_selector.choose(analysis)
        
        # 3. Генерация действия
        action = await self.action_generator.generate(analysis, strategy)
        
        return Decision(type=ACT, action=action)
```

### Компоненты внутри Pattern

| Компонент | Ответственность |
|-----------|-----------------|
| **ReasoningEngine** | Анализ context, извлечение insights |
| **StrategySelector** | Выбор стратегии на основе analysis |
| **ActionGenerator** | Генерация конкретного действия |

**Важно:** это **внутренняя** структура Pattern, не отдельные слои архитектуры!

---

## 📊 СРАВНЕНИЕ ВЕРСИЙ

| Аспект | Версия 3.0 | Версия 4.0 | Версия 5.0 |
|--------|------------|------------|------------|
| **Decision** | В ErrorHandler | В Pattern | В Pattern |
| **_should_stop()** | Есть | Есть | ❌ **Удалить** |
| **SWITCH_STRATEGY** | Runtime загружает | Runtime загружает | ✅ **PatternFactory** |
| **Context** | Только хранение | Только хранение | ✅ **Query helpers** |
| **ExecutionResult** | Не определён | Не определён | ✅ **Зафиксирован** |
| **DecisionType.RETRY** | Есть | Есть | ❌ **Удалить** |
| **Время** | 40 часов | 28 часов | **36 часов** |

---

## 🎯 ИТОГОВЫЕ ПРИНЦИПЫ (ВЕРСИЯ 5.0)

1. **Единая ответственность:** Pattern думает, Runtime управляет, Executor делает
2. **Decision в одном месте:** Pattern — единственный decision-maker
3. **Runtime без решений:** нет `_should_stop()`, нет загрузки pattern
4. **Context с query helpers:** агрегация данных, не decision
5. **ExecutionResult зафиксирован:** единая модель для всех
6. **Нет RETRY типа:** RETRY = ACT с тем же действием
7. **PatternFactory:** Runtime не знает как загружаются паттерны
8. **Чистый код:** никакого legacy, никаких deprecated
9. **Безопасный откат:** Git-тег после каждого этапа

---

## 🚀 БЫСТРЫЙ СТАРТ

```bash
# 1. Создать базовый тег
git tag refactor/before-start
git push origin refactor/before-start

# 2. Начать Этап 1 (BehaviorManager)
# ... работа ...

# 3. Завершить Этап 1
git add .
git commit -m "refactor: Этап 1 - BehaviorManager удалён"
git tag refactor/stage-1-behavior-manager-removed
git push origin main && git push origin --tags

# 4. Продолжить следующий этап...
```

---

**Статус:** Готов к реализации (Версия 5.0 — ФИНАЛЬНАЯ)

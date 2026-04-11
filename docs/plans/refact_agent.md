Вот архитектурно выверенный, детализированный и готовый к исполнению план рефакторинга. Он учитывает реальную структуру файлов из вашего снапшота, минимизирует риски регрессии и разбит на атомарные шаги с чёткими критериями приёмки.

---

# 🛠️ Уточнённый план рефакторинга `Agent_v5`

## 📌 Принципы исполнения
| Принцип | Что это значит на практике |
|---|---|
| **🔪 Инкрементальность** | Никаких `big-bang` переписываний. Каждая фаза компилируется и проходит тесты. |
| **🧱 Обратная совместимость** | Публичные API не ломаются. Старые вызовы помечаются `@deprecated` с алертами в логах. |
| **🧪 Тесты впереди** | Перед каждым шагом пишется/дописывается интеграционный тест на текущее поведение. |
| **🚫 `SessionContext` не трогаем** | Контекст сессии стабилен. Все изменения проходят через него, а не внутрь него. |

---

## 🗺️ Приоритетная матрица фаз

| Фаза | Область | Сложность | Влияние на систему | Статус |
|---|---|---|---|---|
| `Phase 0` | Инфраструктура тестов & CI | ⭐ | 🔴 Критично для безопасности изменений | ✅ Подготовка |
| `Phase 1` | DI `AgentRuntime` | ⭐⭐ | 🔴 Высокое | 🔥 Приоритет 1 |
| `Phase 2` | Унификация `DialogueState` | ⭐⭐⭐ | 🟡 Среднее (риск WebUI) | 🔥 Приоритет 2 |
| `Phase 3` | Чёткие границы Retry/Error | ⭐⭐ | 🟡 Среднее | ⚡ Приоритет 3 |
| `Phase 4` | Инкапсуляция `StepContext` | ⭐ | 🟢 Низкое (поддержка) | 🧱 Приоритет 4 |
| `Phase 5` | Разделение SQL-сервисов | ⭐⭐ | 🟢 Низкое (локализация) | 🧱 Приоритет 5 |

---

## 📦 Детализация по фазам

### 🟢 Phase 0: Подготовка и страховка
**Цель:** Обеспечить безопасную почву для рефакторинга.
1. **Добавить интеграционный тест `test_agent_lifecycle.py`**
   - Запуск `AgentFactory.create_agent()` → `agent.run()` → проверка возврата `ExecutionResult`.
   - Моки: `LLMOrchestrator`, `DBProvider`, `EventBus`.
2. **Настроить линтер/форматтер**
   - `ruff` (проверка неиспользуемых импортов, сложных конструкций).
   - `mypy` (строгая типизация конструкторов компонентов).
3. **Создать ветку `refactor/runtime-decoupling`**
   - Защита от случайных мержей в `main`.

✅ **Критерий приёмки:** Тесты зелёные, линтер проходит, ветка готова.

---

### 🔴 Phase 1: Вынос зависимостей из `AgentRuntime` (DI)
**Файлы:** `core/agent/runtime.py`, `core/agent/factory.py`, `core/agent/bootstrap/runtime_factory.py` (новый)

#### 📍 Сейчас (проблема)
```python
# runtime.py
class AgentRuntime:
    def __init__(self, ...):
        self.executor = ActionExecutor(app_ctx)  # ❌ Создание внутри
        self.failure_memory = FailureMemory()    # ❌ Создание внутри
        self.policy = RetryPolicy()              # ❌ Создание внутри
        self.safe_executor = SafeExecutor(...)   # ❌ Сборка внутри
```

#### 🎯 Цель
`AgentRuntime` принимает только готовые зависимости. Сборка вынесена в фабрику.

#### 🛠️ Пошаговый план
1. Создать `core/agent/bootstrap/runtime_factory.py`:
   ```python
   class AgentRuntimeFactory:
       @staticmethod
       def build(app_ctx: ApplicationContext, goal: str, config: AgentConfig, dialogue_history=None) -> AgentRuntime:
           executor = ActionExecutor(app_ctx)
           failure_memory = FailureMemory(max_age_minutes=30)
           policy = RetryPolicy(max_retries=config.max_retries)
           
           safe_executor = SafeExecutor(
               executor=executor,
               failure_memory=failure_memory,
               max_retries=policy.max_retries,
               base_delay=policy.retry_base_delay,
               max_delay=policy.retry_max_delay
           )
           
           return AgentRuntime(
               application_context=app_ctx,
               goal=goal,
               safe_executor=safe_executor,
               policy=policy,
               dialogue_history=dialogue_history,
               agent_config=config
           )
   ```
2. Упростить `AgentRuntime.__init__`: убрать `new ...`, оставить только присваивание.
3. Обновить `AgentFactory.create_agent` → использовать `AgentRuntimeFactory.build()`.
4. Написать тест на инстанцирование: `test_runtime_factory_creates_with_deps`.

⚠️ **Риск:** `AgentFactory` вызывается из CLI и WebUI. Нужно обновить только точку вызова, внутренняя логика `Agent` не меняется.
✅ **Критерий приёмки:** В `runtime.py` нет вызовов конструкторов компонентов. Все тесты проходят.

---

### 🟠 Phase 2: Унификация состояния диалога
**Файлы:** `core/agent/runtime.py`, `core/session_context/session_context.py`, `web_ui/agent_holder.py`, `web_ui/app.py`

#### 📍 Сейчас
- `_shared_dialogue_history` хранится в Runtime.
- `session_context.dialogue_history` копируется при старте.
- `_sync_dialogue_history_back()` вручную пушит изменения обратно в WebUI.

#### 🎯 Цель
Единый источник: `session_context.dialogue_history`. WebUI получает историю через явный метод или коллбэк.

#### 🛠️ Пошаговый план
1. **Модифицировать `SessionContext.__init__`:**
   ```python
   def __init__(self, ..., dialogue_history: Optional[DialogueHistory] = None):
       self.dialogue_history = dialogue_history or DialogueHistory(max_rounds=10)
   ```
2. **Убрать `_shared_dialogue_history` из `AgentRuntime`.**
3. **Заменить `_sync_dialogue_history_back()` на явный вызов:**
   - В конце `AgentRuntime._run_async()` вызывать `self.session_context.dialogue_history`.
   - WebUI (`agent_holder.py`) будет читать историю из `agent.session_context.dialogue_history` после `agent.run()`.
4. **Обновить WebUI:**
   ```python
   # Было
   agent = await factory.create_agent(..., dialogue_history=shared_history)
   # Стало
   agent = await factory.create_agent(..., dialogue_history=shared_history)
   await agent.run(goal)
   shared_history.messages = agent.session_context.dialogue_history.messages.copy()
   ```

⚠️ **Риск:** Если WebUI подписан на события в реальном времени, прямое чтение после `run()` может давать задержку. Решение: публиковать событие `EventType.DIALOGUE_UPDATED` с обновлённым списком сообщений.
✅ **Критерий приёмки:** История сохраняется между запросами. Нет дублирования памяти. WebUI корректно отображает чат.

---

### 🟡 Phase 3: Чёткие границы Retry & Error Handling
**Файлы:** `core/agent/components/safe_executor.py`, `core/agent/components/error_classifier.py`, `core/agent/components/failure_memory.py`

#### 📍 Сейчас
`SafeExecutor` делает всё: retry-цикл, классификацию, запись в память, возврат результата. `ErrorClassifier` возвращает строки.

#### 🎯 Цель
Разделение ответственностей по паттерну `Chain of Responsibility`.

#### 🛠️ Пошаговый план
1. **Типизировать `ErrorClassifier`:**
   ```python
   class ErrorType(Enum): TRANSIENT, LOGIC, VALIDATION, FATAL
   class ErrorDecision(Enum): RETRY, ABORT, SWITCH_PATTERN, FAIL_IMMEDIATELY
   
   def classify(error: Exception, capability: str) -> Tuple[ErrorType, ErrorDecision]
   ```
2. **Вынести retry-цикл в `RetryManager`:**
   ```python
   class RetryManager:
       async def execute_with_retry(self, action: Callable, context: ExecutionContext) -> ExecutionResult:
           for attempt in range(self.policy.max_retries):
               try: return await action()
               except Exception as e:
                   err_type, decision = self.classifier.classify(e, ...)
                   self.memory.record(err_type, ...)
                   if decision != ErrorDecision.RETRY: raise
                   await asyncio.sleep(self.policy.backoff(attempt))
   ```
3. **Упростить `SafeExecutor`:** оставить только делегирование `RetryManager` + логирование.
4. **Убрать строковые сравнения** (`"retry"`, `"switch"`) из кода, заменить на `Enum`.

⚠️ **Риск:** Паттерны поведения (`ReActPattern`, `PlanningPattern`) читают `FailureMemory`. Нужно убедиться, что API `get_failures()` не сломается.
✅ **Критерий приёмки:** Retry срабатывает только для `TRANSIENT`. `LOGIC/VALIDATION` сразу пишут в память и возвращают `FAILED`. Тесты на retry-логику проходят.

---

### 🟢 Phase 4: Инкапсуляция `StepContext`
**Файлы:** `core/session_context/step_context.py`, `core/agent/behaviors/base_behavior_pattern.py`, `core/components/skills/handlers/base_handler.py`

#### 📍 Сейчас
Фильтрация шагов размазана: `[s for s in context.steps if s.status == FAILED]`.

#### 🎯 Цель
Все запросы к шагам идут через методы `StepContext`.

#### 🛠️ Пошаговый план
1. Добавить в `StepContext`:
   ```python
   def get_steps_by_status(self, status: ExecutionStatus) -> List[AgentStep]: ...
   def get_last_n_steps(self, n: int) -> List[AgentStep]: ...
   def has_consecutive_failures(self, threshold: int = 3) -> bool: ...
   ```
2. Заменить ручные фильтрации в `PromptBuilderService` и `Runtime` на вызовы методов.
3. Добавить `__slots__` или `@property` к `steps` для защиты от прямой модификации вне `register_step()`.

✅ **Критерий приёмки:** В кодовой базе нет прямых обращений к `context.steps[...]`. Промпты собираются корректно.

---

### 🔵 Phase 5: Разделение SQL-сервисов (Опционально, по времени)
**Файлы:** `core/components/services/sql_generation/service.py`, `core/components/services/sql_query/service.py`

#### 📍 Сейчас
`SQLGenerationService` генерирует, валидирует, исправляет ошибки и публикует метрики. ~7K строк.

#### 🎯 Цель
`SQLGenerationService` как фасад. Внутрь внедрены `SQLValidator`, `SQLErrorAnalyzer`, `SQLCorrectionEngine`.

#### 🛠️ Пошаговый план
1. Вынести `_validate_query()` → `SQLValidatorService.validate()`.
2. Вынести `_analyze_and_correct()` → `SQLCorrectionEngine.correct()`.
3. Внедрить через `__init__`.
4. Упростить `generate_query()` до конвейера: `generate → validate → (if fail) correct → return`.

✅ **Критерий приёмки:** Сервис < 3K строк. Тесты на генерацию/валидацию/коррекцию изолированы.

---

## 🔄 Стратегия применения (без Big Bang)

| Шаг | Действие | Безопасность |
|---|---|---|
| 1 | Создать `Phase 1` в отдельной ветке | 🔒 Ветка не мерджится, пока не пройдут тесты |
| 2 | Включить `runtime_factory` параллельно со старой логикой через флаг `USE_RUNTIME_FACTORY=True` | 🔁 Canary-деплой на dev-среде |
| 3 | Удалить старый код, запустить полный регресс | 🧪 CI/CD pipeline |
| 4 | Перейти к `Phase 2` (WebUI sync) | 🌐 Тестировать через локальный Streamlit |

**Правило отката:** Если фаза не укладывается в 2-3 дня или ломает >5% интеграционных тестов → откат и декомпозиция на более мелкие шаги.

---

## 📊 Метрики успеха (Definition of Done)

| Метрика | До рефакторинга | После рефакторинга |
|---|---|---|
| `AgentRuntime.__init__` | Создает 4 объекта, 120 строк | Принимает 2 зависимости, 15 строк |
| Дублирование диалога | 2 копии + ручной sync | 1 источник, автоматический merge |
| Retry-логика | Смешана с классификацией | Выделена в `RetryManager`, типизирована |
| Прямые обращения к `context.steps` | 14 мест | 0 мест (только методы `StepContext`) |
| Покрытие тестами (критичные пути) | ~30% | >85% |

---

## 🛡️ Главные риски и митигации

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| WebUI теряет историю после миграции Phase 2 | 🟡 Средняя | 🔴 Высокое | Добавить промежуточный `DialogueSyncAdapter`, который читает из старого и нового поля, пока WebUI не обновлён. |
| `ErrorClassifier` меняет семантику решений | 🔴 Высокая | 🟡 Средняя | Написать параметризованные тесты на 50+ кейсов ошибок (timeout, syntax, auth, logic) до рефакторинга. |
| Промпты ломаются из-за изменения формата шагов | 🟡 Средняя | 🔴 Высокое | Ввести контракт `StepSummary` (dict), который `StepContext` отдаёт промпт-билдерам. Не менять структуру LLM-промпта. |
| Рефакторинг затягивается | 🟢 Низкая | 🟡 Средняя | Жёсткий таймбокс: 3 дня на фазу. Если не укладываемся → замораживаем, пишем документацию по техдолгу, идём дальше. |

---

## ✅ Чек-лист перед стартом

- [ ] Создана ветка `refactor/runtime-di`
- [ ] Написан интеграционный тест `test_agent_full_cycle`
- [ ] Добавлен `ruff` + `mypy` в CI
- [ ] Зафиксированы текущие метрики покрытия (`pytest --cov=core/agent`)
- [ ] Согласован план с командой (если есть)

---

💡 **Рекомендация:** Начните с **Phase 1**. Это даст максимальный выигрыш в читаемости и тестируемости `AgentRuntime` без затрагивания UI и бизнес-логики навыков. Если нужно, я могу сразу сгенерировать:
1. Полный код `AgentRuntimeFactory` + обновлённый `AgentRuntime.__init__`
2. Набор из 5 параметризованных тестов для `ErrorClassifier`
3. Патч для `web_ui/agent_holder.py` под новую синхронизацию диалога
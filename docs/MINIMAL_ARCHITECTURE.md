# Минималистичная архитектура агента

## 📊 Сравнение архитектур

### Было (старая архитектура)
```
~10-12 компонентов:
- Pattern
- StepExecutor
- SafeExecutor  
- ActionExecutor
- Policy
- FailureMemory
- FallbackStrategy
- Observer
- AgentMetrics
- SessionContext (сложный)
- Runtime (толстый, создаёт зависимости)

Проблемы:
- Дублирующие слои
- Сложные связи
- Runtime знает слишком много
- Ручной sync state
```

### Стало (новая архитектура)
```
5 компонентов:
1. AgentRuntime — тонкий оркестратор
2. AgentLoop — decide → execute → observe → control
3. Executor (+ RetryExecutor middleware)
4. Controller — policy + fallback
5. Observer — анализ результатов
+ AgentMetrics (отдельно)
+ AgentState (упрощённый)

Преимущества:
- Прямой pipeline
- Каждый компонент отвечает за своё
- Нет дублирования
- Легко тестировать
```

---

## 🏗️ Компоненты

### 1. AgentRuntime

**Ответственность:**
- Управление циклом выполнения
- Создание session state
- Сбор метрик

**НЕ знает про:**
- Детали executor / policy / fallback
- Создание зависимостей

```python
runtime = AgentRuntime(
    loop=agent_loop,
    metrics=AgentMetrics(),
    application_context=app_context,
    goal="моя цель",
    max_steps=10
)

result = await runtime.run()
```

---

### 2. AgentLoop

**Ответственность:**
1. `DecisionMaker.decide()` — выбор действия
2. `Executor.execute()` — выполнение действия
3. `Observer.observe()` — анализ результата
4. `State.apply()` — обновление состояния
5. `Controller.evaluate()` — policy + fallback решения

**Заменяет:**
- Pattern (частично)
- StepExecutor
- часть Runtime
- часть Policy

```python
loop = AgentLoop(
    decision_maker=pattern,
    executor=executor,
    observer=observer,
    controller=controller
)

result = await loop.step(state)
```

---

### 3. Executor

**Ответственность:**
- Получение инструмента из registry
- Выполнение инструмента
- Публикация событий в event bus
- Возврат ExecutionResult

**Заменяет:**
- ActionExecutor
- SafeExecutor (частично)
- StepExecutor (частично)

```python
executor = Executor(
    tool_registry=registry,
    event_bus=event_bus,
    session_id="session_123",
    agent_id="agent_001"
)

result = await executor.execute("search.database", state)
```

---

### 4. RetryExecutor (Middleware)

**Ответственность:**
- Повторное выполнение при ошибках
- Экспоненциальная задержка между попытками

**Заменяет:**
- SafeExecutor (retry логику)

```python
retry_executor = RetryExecutor(
    executor=base_executor,
    max_retries=3,
    base_delay=0.5
)

# Обёртываем базовый executor
result = await retry_executor.execute("action", state)
```

---

### 5. Controller

**Ответственность:**
- Проверка условий остановки
- Обработка ошибок
- Fallback логика

**Заменяет:**
- Policy
- FailureMemory
- FallbackStrategy

```python
controller = Controller(
    max_steps=10,
    max_failures=3,
    max_empty_results=3
)

decision = controller.evaluate(state, result)
# → StepResult.done(state)
# → StepResult.fail(error, state)
# → StepResult.continue_(state)
```

---

### 6. Observer

**Ответственность:**
- Анализ результата (success/error/empty)
- Извлечение ключевой информации

**Упрощённая версия** — без LLM (можно расширить)

```python
observer = Observer()

observation = await observer.observe(result, state)
# → {"success": True, "status": "success", ...}
```

---

### 7. AgentState

**Ответственность:**
- Хранение состояния сессии
- История выполненных шагов
- Счётчики ошибок

**Упрощает:**
- SessionContext (убираем sync, копирование)

```python
state = AgentState(
    goal="моя цель",
    max_steps=10
)

state.apply(action, result, observation)
# steps += 1
# history.append(...)
# failures update
```

---

### 8. AgentMetrics

**Ответственность:**
- Подсчёт шагов
- Подсчёт ошибок
- Проверка условий остановки

```python
metrics = AgentMetrics()

metrics.update(step_result)
# steps += 1
# errors += 1 (если error)

should_stop, reason = metrics.should_stop(max_errors=10)
```

---

## 🔄 Поток данных

```
┌─────────────────┐
│  AgentRuntime   │
│  (orchestrator) │
└────────┬────────┘
         │ run()
         ▼
┌─────────────────┐
│   AgentLoop     │
│  (core cycle)   │
└────────┬────────┘
         │ step(state)
         ▼
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
    ▼         ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│ Decide │ │ Execute│ │ Observe│ │ Control  │
│ Pattern│ │Executor│ │Observer│ │Controller│
└────────┘ └────┬───┘ └────────┘ └────┬─────┘
                │                     │
                │  ┌──────────────┐   │
                └─►│ RetryExecutor│   │
                   │ (middleware) │   │
                   └──────────────┘   │
                                      │
         ┌────────────────────────────┘
         │
         ▼
    ┌─────────┐
    │  State  │◄──── apply(action, result, obs)
    └─────────┘
```

---

## ✅ Сохранённый функционал

| Функция | Реализация |
|---------|------------|
| decide → execute → observe | ✔ AgentLoop.step() |
| retry | ✔ RetryExecutor middleware |
| fallback | ✔ Controller.evaluate() |
| metrics | ✔ AgentMetrics |
| event bus | ✔ Executor.publish() |
| policy checks | ✔ Controller |
| failure tracking | ✔ AgentState.failures |

---

## 📉 Убрано

| Компонент | Причина удаления |
|-----------|------------------|
| StepExecutor | Встроен в Executor |
| SafeExecutor (как слой) | Retry → middleware |
| FallbackStrategy | В Controller |
| половина Policy | В Controller |
| ручной sync state | Убран |
| часть runtime логики | Перенесено в Loop |

---

## 🚀 План миграции

### Этап 1: Создать новые компоненты
- [x] `runtime_minimal.py` — все 5 компонентов
- [x] Тесты для каждого компонента

### Этап 2: Постепенная замена
1. Использовать новый Executor вместо старого стека
2. Заменить Policy + Fallback на Controller
3. Упростить SessionContext → AgentState
4. Сделать текущий Runtime тонким

### Этап 3: Полная миграция
1. Переключить все точки входа на новый runtime
2. Удалить старые компоненты
3. Обновить документацию

---

## 🧪 Тестирование

Все компоненты покрыты тестами:
- `tests/unit/agent/test_runtime_minimal.py`

Запуск тестов:
```bash
pytest tests/unit/agent/test_runtime_minimal.py -v
```

---

## 📝 Пример использования

```python
from core.agent.runtime_minimal import (
    AgentRuntime, AgentLoop, Executor, 
    Controller, Observer, AgentMetrics,
    AgentState, StepResult
)

# 1. Создаём компоненты
executor = Executor(tool_registry, event_bus)
retry_executor = RetryExecutor(executor, max_retries=3)

controller = Controller(
    max_steps=10,
    max_failures=3
)

observer = Observer()

# 2. Создаём цикл
loop = AgentLoop(
    decision_maker=pattern,  # твой Pattern
    executor=retry_executor,
    observer=observer,
    controller=controller
)

# 3. Создаём runtime
runtime = AgentRuntime(
    loop=loop,
    metrics=AgentMetrics(),
    application_context=app_context,
    goal="найти информацию о X",
    max_steps=10
)

# 4. Запускаем
result = await runtime.run()

if result.success:
    print(f"✅ Успех за {result.result['steps']} шагов")
else:
    print(f"❌ Ошибка: {result.error}")
```

---

## 💡 Ключевые принципы

1. **Один слой = одна ответственность**
   - Executor только выполняет
   - Controller только решает
   - Observer только анализирует

2. **Runtime не создаёт зависимости**
   - Все зависимости инжектятся извне
   - Runtime только оркестрирует

3. **Middleware для cross-cutting concerns**
   - Retry → отдельный класс
   - Logging → через event bus
   - Metrics → отдельный компонент

4. **State — простой dataclass**
   - Нет сложной логики
   - Нет инфраструктурных зависимостей
   - Легко сериализовать

---

## 🎯 Итог

**Было:** ~10-12 компонентов, сложные связи, дублирование  
**Стало:** 5 компонентов, прямой pipeline, чёткие границы

**Функционал:** сохранён полностью  
**Код:** стал проще, легче тестировать и поддерживать

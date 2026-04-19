# 📋 План реализации архитектуры v2.0

## ✅ Выполнено (PHASE 0-4)

### PHASE 0 — Подготовка
- ✅ **Шаг 0.1**: Схемы уже существуют в `data/contracts/behavior/`
  - `behavior.react.think_output_v1.0.0.yaml` — для ReAct thinking
  - `behavior.react.observe_output_v1.0.0.yaml` — для Observer
- ✅ **Шаг 0.2**: LLM wrapper поддерживает `response_schema` через `StructuredOutputConfig`

---

### PHASE 1 — State как центр системы
- ✅ **Шаг 1.1**: Создан `AgentMetrics` (`core/agent/components/agent_metrics.py`)
  - `step_number`, `errors`, `empty_results_count`, `repeated_actions_count`
  - `last_observation`, `recent_actions`
  - Методы: `add_step()`, `add_error()`, `update_observation()`, `check_repeated_action()`
- ✅ **Шаг 1.2**: Интеграция с runtime через `self.metrics`

---

### PHASE 2 — ReActEngine (ядро)
- ✅ **Шаг 2.1**: Генерация через schema уже работает в `ReActPattern.generate_decision()`
- ✅ **Шаг 2.2**: JSON parsing не требуется — используется `StructuredOutputConfig`
- ⚠️ **Шаг 2.3**: `build_prompt()` требует доработки (добавить метрики в prompt)

---

### PHASE 3 — Reflection как gate
- ✅ **Шаг 3.1**: Логика валидации готова к внедрению
- ⚠️ **Шаг 3.2**: Требуется интеграция в `ReActPattern._make_decision()`

---

### PHASE 4 — Policy (второй фильтр)
- ✅ **Шаг 4.1**: Расширен `AgentPolicy` (`core/agent/components/policy.py`)
  - `check_repeat_action()` — детектирование повторов
  - `check_empty_loop()` — детектирование пустых результатов
  - `check_max_errors()` — лимит ошибок
- ✅ **Шаг 4.2**: Интеграция в `runtime.py` перед выполнением действия

---

### PHASE 5 — Execution + Skills
- ✅ Ничего не сломано — executor работает как прежде

---

### PHASE 6 — Observation (LLM-анализ результата)
- ✅ **Шаг 6.1**: Создан `Observer` (`core/agent/components/observer.py`)
  - `analyze()` — LLM-анализ результата
  - Использует контракт `behavior.react.observe_output_v1.0.0`
- ✅ **Шаг 6.2**: Prompt для анализа реализован
- ✅ **Шаг 6.3**: Обновление `state.last_observation` → `metrics.update_observation()`
- ✅ **Шаг 6.4**: Влияние на state через `metrics.add_step()` и `metrics.update_observation()`

---

### PHASE 7 — ErrorClassifier + FailureMemory
- ✅ Уже существуют:
  - `core/agent/components/error_classifier.py`
  - `core/agent/components/failure_memory.py`
- ⚠️ Требуется интеграция в runtime

---

### PHASE 8 — Anti-loop & stop logic
- ✅ **Шаг 8.1**: Реализовано в `AgentMetrics.should_stop()`
  - `max_errors >= 10`
  - `max_empty_results >= 3`
  - `max_repeated_actions >= 3`
- ✅ **Шаг 8.2**: Fallback через `ExecutionResult.failure()`

---

### PHASE 9 — EventBus
- ✅ Добавлены события:
  - `POLICY_BLOCK` — при блокировке действия политикой
  - `OBSERVATION` — после анализа Observer
  - `AGENT_STOP_METRICS` — при остановке по метрикам

---

## 🔧 Требуется доработать

### 1. ReActPattern — Reflection Validation
**Файл**: `core/agent/behaviors/react/pattern.py`

Добавить валидацию reflection перед возвратом решения:

```python
def validate_reflection(self, reasoning_result, session_context) -> Tuple[bool, str]:
    # Проверка на повторы действий
    last_steps = session_context.get_last_steps(5)
    if reasoning_result.decision.next_action:
        recent_actions = [s.skill_name for s in last_steps]
        if reasoning_result.decision.next_action in recent_actions:
            return False, "repeated_action"
    
    # Проверка stop_condition без final_analysis
    if reasoning_result.stop_condition and not reasoning_result.analysis_final:
        return False, "stop_without_final"
    
    return True, None
```

Интегрировать в `generate_decision()` после получения ответа от LLM.

---

### 2. ReActPattern — build_prompt с метриками
**Файл**: `core/agent/behaviors/react/pattern.py`

Обновить промпт чтобы включать метрики:

```python
def build_reasoning_prompt(...):
    # Добавить в контекст:
    metrics_info = f"""
METRICS:
- step: {session_context.step_context.count()}
- errors: {metrics.errors[-3:]}
- empty_results: {metrics.empty_results_count}
- repeated_actions: {metrics.repeated_actions_count}
"""
```

---

### 3. Runtime — интеграция ErrorClassifier
**Файл**: `core/agent/runtime.py`

После выполнения действия:

```python
from core.agent.components.error_classifier import ErrorClassifier

error_classifier = ErrorClassifier()
if result.status == ExecutionStatus.FAILED:
    error_type = error_classifier.classify(result.error)
    self.failure_memory.add(
        action=decision.action,
        error_type=error_type,
        parameters=decision.parameters
    )
```

---

## 📊 Итоговая архитектура v2.0

```text
Agent.run
  ↓
[Check Metrics.should_stop()]
  ↓
ReActPattern.decide(session_context, available_caps)
  ↓
LLM(prompt + METRICS_CONTEXT, response_schema=THINK_SCHEMA)
  ↓
[Reflection Validation] ← НОВОЕ
  ↓
Policy.check(action, metrics) ← УСИЛЕНО
  ↓
Executor.execute(skill, params)
  ↓
Observer.analyze(action, result, error) ← НОВОЕ
  ↓
Metrics.update(observation) ← НОВОЕ
  ↓
ErrorClassifier + FailureMemory ← ИНТЕГРАЦИЯ
  ↓
EventBus.publish(OBSERVATION, POLICY_BLOCK, etc.)
  ↓
Next step (с обновлёнными метриками в prompt)
```

---

## 🎯 Ключевые улучшения

| Компонент | Было | Стало |
|-----------|------|-------|
| **State** | SessionContext только данные | + AgentMetrics для качества |
| **Policy** | Только retry лимиты | + repeat_action, empty_loop |
| **Observation** | Форматирование текста | + LLM-анализ качества |
| **Reflection** | Нет явной валидации | + validation gate |
| **Stop Logic** | По max_steps | + по метрикам качества |
| **EventBus** | Базовые события | + POLICY_BLOCK, OBSERVATION |

---

## 🚀 Следующие шаги

1. **Reflection Validation** — добавить в ReActPattern
2. **Metrics в prompt** — обновить build_reasoning_prompt
3. **ErrorClassifier интеграция** — подключить в runtime
4. **Тесты** — проверить anti-loop логику

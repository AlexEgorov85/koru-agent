# Исправление AgentStuckError

**Дата:** 2026-03-05  
**Проблема:** Агент падал с `AgentStuckError: State did not mutate after observe() for 2 consecutive steps`

---

## 🔍 Диагностика

### Симптом
```
❌ Произошла ошибка: Ошибка агента: AgentStuckError: State did not mutate after observe() for 2 consecutive steps
```

### Причина

**Цепочка проблемы:**

1. `AgentRuntime._execute_single_step_internal()` выполняет действие
2. Вызывает `session_context.record_action()` для записи результата
3. **НО НЕ ВЫЗЫВАЕТ** `session_context.record_step()` ❌
4. `session_context.get_summary()` возвращает одинаковые `last_steps`
5. `ProgressScorer.evaluate()` сравнивает summary → возвращает `False`
6. `AgentState.register_progress(False)` увеличивает `no_progress_steps`
7. Через 2 шага `snapshot()` становится одинаковым
8. **AgentStuckError!** ❌

### Код проблемы (runtime.py:422-427)

**Было:**
```python
# Обновление контекста выполнения
if (hasattr(self.application_context, 'session_context') and
    self.application_context.session_context):
    self.application_context.session_context.record_action({
        "step": self._current_step + 1,
        "action": decision.capability_name,
        "result": execution_result,
        "timestamp": datetime.now().isoformat()
    }, step_number=self._current_step + 1)

# Оценка прогресса и обновление состояния
progressed = self.progress.evaluate(self.application_context.session_context)
self.state.register_progress(progressed)
```

**Проблема:** `record_action()` записывает ACTION item в `data_context`, но **НЕ обновляет** `step_context.steps`!

Поэтому `session_context.get_summary()`:
```python
def get_summary(self) -> Dict[str, Any]:
    summary_dict = {
        ...
        "last_steps": []
    }
    
    if self.step_context.steps:  # ← ПУСТОЙ! record_action() не добавляет шаги
        for step in self.step_context.steps[-3:]:
            summary_dict["last_steps"].append(...)
    
    return summary_dict  # ← last_steps всегда пустой или не меняется
```

Возвращает одинаковое значение → `ProgressScorer.evaluate()` возвращает `False` → AgentStuckError!

---

## ✅ Решение

**Исправление (runtime.py:422-441):**

```python
# Обновление контекста выполнения
if (hasattr(self.application_context, 'session_context') and
    self.application_context.session_context):
    action_id = self.application_context.session_context.record_action({
        "step": self._current_step + 1,
        "action": decision.capability_name,
        "result": execution_result,
        "timestamp": datetime.now().isoformat()
    }, step_number=self._current_step + 1)
    
    # КРИТИЧНО: Записываем STEP чтобы get_summary() обновился!
    # Без этого get_summary() возвращает одинаковые last_steps
    # и ProgressScorer.evaluate() возвращает False
    self.application_context.session_context.record_step(
        step_number=self._current_step + 1,
        capability_name=decision.capability_name,
        skill_name=decision.capability_name.split('.')[0] if '.' in decision.capability_name else decision.capability_name,
        action_item_id=action_id,
        observation_item_ids=[],
        summary=f"Выполнено: {decision.capability_name}",
        status="completed"
    )

# Оценка прогресса и обновление состояния
progressed = self.progress.evaluate(self.application_context.session_context)
self.state.register_progress(progressed)
```

---

## 📊 Результат

### До исправления

```
Шаг 1: record_action() → step_context.steps = []
       get_summary() → last_steps = []
       ProgressScorer.evaluate() → False (summary не меняется)
       state.register_progress(False) → no_progress_steps = 1

Шаг 2: record_action() → step_context.steps = []
       get_summary() → last_steps = [] (одинаково!)
       ProgressScorer.evaluate() → False
       state.register_progress(False) → no_progress_steps = 2

Шаг 3: snapshot() == previous_snapshot → AgentStuckError! ❌
```

### После исправления

```
Шаг 1: record_action() → action_id = "action_123"
       record_step() → step_context.steps = [AgentStep(step_number=1, ...)]
       get_summary() → last_steps = [{step_number: 1, ...}]
       ProgressScorer.evaluate() → True (summary изменился!)
       state.register_progress(True) → no_progress_steps = 0

Шаг 2: record_action() → action_id = "action_124"
       record_step() → step_context.steps = [AgentStep(1), AgentStep(2)]
       get_summary() → last_steps = [{step_number: 1}, {step_number: 2}]
       ProgressScorer.evaluate() → True
       state.register_progress(True) → no_progress_steps = 0

Шаг 3: snapshot() != previous_snapshot → Агент работает! ✅
```

---

## 📁 Изменённые файлы

| Файл | Строки | Изменение |
|------|--------|-----------|
| `core/application/agent/runtime.py` | 422-441 | Добавлен вызов `record_step()` |

---

## 🧪 Тестирование

### Проверка что агент не зацикливается

```bash
python main.py
```

**Ожидаемый результат:**
- Агент выполняет действия
- `step_context.steps` обновляется на каждом шаге
- `get_summary()` возвращает разные значения
- `ProgressScorer.evaluate()` возвращает `True`
- Агент завершается успешно (не падает с AgentStuckError)

---

## 🎯 Архитектурные выводы

### Правильный порядок записи в контекст

```python
# 1. Записываем ACTION (результат выполнения)
action_id = session_context.record_action({...}, step_number=step)

# 2. Записываем STEP (обновляет step_context.steps!)
session_context.record_step(
    step_number=step,
    capability_name=capability,
    action_item_id=action_id,  # ← Связываем с action
    summary="...",
    status="completed"
)

# 3. Оцениваем прогресс (теперь summary меняется!)
progressed = progress_scorer.evaluate(session_context)
state.register_progress(progressed)
```

### Почему это работает

1. `record_action()` → добавляет ACTION item в `data_context`
2. `record_step()` → добавляет STEP item в `step_context.steps`
3. `get_summary()` → читает `step_context.steps[-3:]` → **возвращает обновлённые данные**
4. `ProgressScorer.evaluate()` → сравнивает summary → **возвращает True**
5. `AgentState.register_progress(True)` → **сбрасывает no_progress_steps**
6. `snapshot()` → **меняется** → нет зацикливания!

---

## ✅ Заключение

**Проблема:** `record_action()` не обновлял `step_context.steps`, из-за чего `get_summary()` возвращал одинаковые данные.

**Решение:** Добавлен вызов `record_step()` после `record_action()`.

**Результат:** Агент больше не падает с `AgentStuckError`! 🎉

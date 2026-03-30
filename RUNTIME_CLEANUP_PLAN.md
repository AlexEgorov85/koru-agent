# 🧹 ПЛАН ОЧИСТКИ runtime.py

**Текущий размер:** 1076 строк  
**Целевой размер:** ~200 строк

---

## 🔍 ПРОБЛЕМЫ

### 1. ProgressMetrics внутри runtime.py
**Строк:** ~15  
**Решение:** Вынести в `core/agent/components/progress.py`

---

### 2. _execute_single_step_internal (460 строк!)
**Проблема:** Это decision logic!

**Что делает:**
- Проверка `if decision.action == DecisionType.STOP на step 0`
- Возврат `Decision(action=DecisionType.SWITCH)`
- Обработка ошибок с decision logic

**Решение:**
- ✅ Удалить SAFEGUARD — Pattern сам решает когда STOP
- ✅ Упростить до простого execute
- ✅ Переместить decision logic в Pattern

---

### 3. _run_async (320 строк)
**Проблема:** Слишком большой для простого цикла

**Что делает:**
- Цикл `while self._running`
- Логирование каждого шага
- Проверка loop detection
- Проверка no progress

**Решение:**
- ✅ Удалить loop detection — Pattern сам детектирует
- ✅ Удалить no progress checks — Pattern сам детектирует
- ✅ Оставить только цикл

---

### 4. TODO комментарии
**Количество:** ~50  
**Решение:** Удалить (это технический долг)

---

### 5. Дублированное логирование
**Проблема:**
```python
logger.debug(...)  # logging
self.event_bus_logger.debug(...)  # EventBus
```

**Решение:** Оставить только EventBus

---

## ✅ ЦЕЛЕВАЯ СТРУКТУРА

```python
class AgentRuntime:
    def __init__(self, ...):
        # Инициализация компонентов
        pass

    async def run(self, goal: str) -> ExecutionResult:
        """Запуск цикла."""
        return await self._run_async(goal)

    async def _run_async(self, goal: str) -> ExecutionResult:
        """
        Простой цикл:
        1. Pattern.decide()
        2. Executor.execute()
        3. Запись в context
        4. Если FINISH/FAIL → возврат
        """
        pattern = self._create_pattern()
        
        for step in range(self.max_steps):
            # 1. Pattern решает
            decision = await pattern.decide(context)
            
            # 2. Pattern решил FINISH?
            if decision.type == DecisionType.FINISH:
                return decision.result
            
            # 3. Pattern решил FAIL?
            if decision.type == DecisionType.FAIL:
                return ExecutionResult.failure(decision.error)
            
            # 4. Pattern решил ACT?
            if decision.type == DecisionType.ACT:
                result = await self.executor.execute(decision.action)
                context.record_step(result)
            
            # 5. Pattern решил SWITCH?
            if decision.type == DecisionType.SWITCH_STRATEGY:
                pattern = self.pattern_factory.create(decision.next_pattern)
        
        # Max steps exceeded
        return ExecutionResult.failure("Max steps exceeded")

    async def stop(self):
        """Остановка."""
        self._running = False
```

**Итого:** ~100 строк чистого кода

---

## 📋 ЧТО УДАЛИТЬ

1. ❌ **ProgressMetrics class** (вынести отдельно)
2. ❌ **SAFEGUARD logic** (Pattern решает)
3. ❌ **Loop detection** (Pattern решает)
4. ❌ **No progress checks** (Pattern решает)
5. ❌ **_should_stop()** (удалено в Этапе 5)
6. ❌ **_should_stop_early()** (удалено в Этапе 5)
7. ❌ **TODO комментарии** (~50 строк)
8. ❌ **Дублированное logging** (~100 строк)

---

## 📊 ОЖИДАЕМЫЙ РАЗМЕР

| Секция | Было | Станет |
|--------|------|--------|
| Imports | 40 | 20 |
| ProgressMetrics | 15 | 0 (вынести) |
| `__init__` | 80 | 40 |
| `_init_event_bus_logger` | 20 | 10 |
| `run` | 15 | 10 |
| `_execute_single_step_internal` | 460 | 50 |
| `_extract_final_result` | 75 | 20 |
| `_run_async` | 320 | 40 |
| `stop` | 5 | 5 |
| `_update_state` | 15 | 5 |
| **ИТОГО** | **1076** | **~200** |

---

## 🚀 СЛЕДУЮЩИЙ ЭТАП: Runtime Cleanup

**Название:** Этап 10: Runtime упрощён до цикла

**Git-тег:** `refactor/stage-10-runtime-cleanup`

**Время:** ~4 часа

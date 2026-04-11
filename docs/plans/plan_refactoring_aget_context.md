Ниже представлен детальный, пошаговый план рефакторинга. Он разбит на 5 фаз, каждая из которых содержит: **что менять**, **как менять** и **как проверять результат**. В начале показана целевая архитектура, к которой мы придём.

---
## 🏗️ Целевая архитектура (Target Architecture)

```
SessionContext (1 сессия = 1 чат)
 │
 ├─ dialogue_history: List[User/Assistant turns]
 ├─ turns: Dict[turn_id -> TurnMeta]       ← Ходы диалога
 │    └─ {goal, start_step, end_step, summary}
 │
 ├─ tasks: TaskContext                     ← Логические единицы работы
 │    └─ tasks: Dict[task_id -> Task]      ← has: id, name, status, deps, result
 │
 ├─ step_context: StepContext              ← Технические шаги агента
 │    └─ steps: List[AgentStep]            ← has: turn_id, task_id, capability, status
 │
 └─ data_context: DataContext              ← Сырые данные (observations)
      └─ items: Dict[item_id -> ContextItem] ← Привязаны к task_id/turn_id
```

**Ключевые принципы:**
1. **Изоляция контекста LLM:** В промпт попадают только `active_tasks` + шаги `текущего хода`. Прошлые ходы передаются как сжатое резюме.
2. **Task ≠ Step:** `Task` = бизнес-цель (например, "Найти книги автора"). `Step` = техническое действие агента (вызов `sql_tool.execute`). Одна задача = N шагов.
3. **Обратная совместимость:** Старые методы `get_goal()`, `register_step()` сохраняются, но делегируют новой структуре. Миграция плавная.

---
## 📋 Детальный план рефакторинга

### 🔹 Фаза 1: Модели данных (`Task`, `TurnMeta`, связь со `Step`)
**Цель:** Ввести типизированные структуры для задач и ходов, не ломая существующий `AgentStep`.

| Шаг | Что делать | Файлы |
|-----|------------|-------|
| 1.1 | Создать `TaskStatus` enum и `Task` модель | `core/session_context/models/task.py` |
| 1.2 | Создать `TurnMeta` модель | `core/session_context/models/turn.py` |
| 1.3 | Добавить `turn_id` и `task_id` в `AgentStep` | `core/session_context/model.py` |

**Как делать:**
```python
# core/session_context/models/task.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    parent_task_id: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

# core/session_context/models/turn.py
class TurnMeta(BaseModel):
    turn_id: str
    user_query: str
    start_step: int
    end_step: Optional[int] = None
    summary: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
```
В `core/session_context/model.py` добавить в `AgentStep`:
```python
turn_id: Optional[str] = None
task_id: Optional[str] = None
```

✅ **Как проверить:**
1. Написать простой тест: создать `Task`, сериализовать в JSON, десериализовать обратно.
2. Убедиться, что `AgentStep` с новыми полями создаётся без ошибок.
3. Запустить `python -m pytest tests/test_session_models.py` (или аналогичный).

---

### 🔹 Фаза 2: Контекстный слой (`TaskContext` + обновление `SessionContext`)
**Цель:** Дать сессии инструменты управления задачами и ходами, сохранив текущие `data_context` и `step_context`.

| Шаг | Что делать | Файлы |
|-----|------------|-------|
| 2.1 | Создать `TaskContext` с методами управления | `core/session_context/task_context.py` |
| 2.2 | Интегрировать `TaskContext` и `turn_id` в `SessionContext` | `core/session_context/session_context.py` |
| 2.3 | Добавить методы `start_turn()`, `end_turn()`, `get_active_tasks_for_prompt()` | `session_context.py` |

**Как делать:**
```python
# core/session_context/task_context.py
class TaskContext:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
    
    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task
    
    def get_ready_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
    
    def complete_task(self, task_id: str, result: Any) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
```
В `SessionContext.__init__`:
```python
self.task_context = TaskContext()
self.current_turn_id: Optional[str] = None
self.turns: Dict[str, TurnMeta] = {}
```
Добавить методы:
```python
def start_turn(self, user_query: str, start_step: int) -> str:
    self.current_turn_id = str(uuid.uuid4())[:8]
    self.turns[self.current_turn_id] = TurnMeta(
        turn_id=self.current_turn_id, user_query=user_query, start_step=start_step
    )
    return self.current_turn_id

def end_turn(self, end_step: int, summary: str = "") -> None:
    if self.current_turn_id and self.current_turn_id in self.turns:
        self.turns[self.current_turn_id].end_step = end_step
        self.turns[self.current_turn_id].summary = summary
```

✅ **Как проверить:**
1. Запустить скрипт-сэндбокс: создать `SessionContext`, вызвать `start_turn()`, добавить 2 задачи, вызвать `end_turn()`.
2. Проверить, что `data_context` и `step_context` не затронуты.
3. Убедиться, что `session_context.turns` заполняется корректно.

---

### 🔹 Фаза 3: Интеграция в `AgentRuntime` и `PlanningPattern`
**Цель:** Заставить агента работать в рамках ходов и задач, а не в бесконечном цикле шагов.

| Шаг | Что делать | Файлы |
|-----|------------|-------|
| 3.1 | Обернуть цикл выполнения в `start_turn()` / `end_turn()` | `core/agent/runtime.py` |
| 3.2 | Модифицировать `PlanningPattern` для создания `Task` вместо JSON-плана | `core/agent/behaviors/planning/pattern.py` |
| 3.3 | Привязывать `turn_id` и `task_id` при регистрации шага | `session_context.py` / `runtime.py` |

**Как делать:**
В `AgentRuntime._run_async()`:
```python
# Начало хода
self.session_context.start_turn(user_query=self.goal, start_step=0)

# ... существующий цикл ...
for step in range(self.max_steps):
    # Pattern решает -> ACT/FINISH
    decision = await pattern.decide(self.session_context, caps)
    if decision.type == DecisionType.FINISH:
        break
    # Executor выполняет -> результат
    self.session_context.register_step(
        step_number=executed_steps + 1,
        capability_name=decision.action,
        turn_id=self.session_context.current_turn_id,
        task_id=current_task_id  # из TaskContext
    )

# Конец хода
self.session_context.end_turn(end_step=self.step_context.count(), summary="Цикл завершён")
```

В `PlanningPattern._create_initial_plan()`: вместо сохранения JSON в `data_context`, вызывать:
```python
task = Task(id="plan_1", name=plan_data["name"], description=plan_data["goal"])
self.session_context.task_context.add_task(task)
```

✅ **Как проверить:**
1. Запустить `main.py` с запросом `"Найди книги Пушкина"`.
2. В логах/отладке проверить: создан ли `turn_id`, создаются ли `Task`, привязаны ли шаги к `turn_id`.
3. Убедиться, что старый `context.record_plan` не ломает выполнение (оставить как fallback на переходный период).

---

### 🔹 Фаза 4: Пересборка LLM-контекста (`PromptBuilderService`)
**Цель:** Не перегружать окно контекста. Передавать в LLM только релевантные задачи и шаги текущего хода.

| Шаг | Что делать | Файлы |
|-----|------------|-------|
| 4.1 | Добавить `build_llm_context()` в `SessionContext` | `session_context.py` |
| 4.2 | Обновить `PromptBuilderService._build_input_context()` | `core/agent/behaviors/base_behavior_pattern.py` |
| 4.3 | Реализовать фильтрацию шагов по `turn_id` и `task_id` | `step_context.py` |

**Как делать:**
В `SessionContext`:
```python
def build_llm_context(self, max_steps: int = 8) -> Dict[str, Any]:
    # 1. Только шаги текущего хода
    current_steps = [s for s in self.step_context.steps 
                     if s.turn_id == self.current_turn_id][-max_steps:]
    
    # 2. Активные задачи (не completed)
    active_tasks = [t for t in self.task_context.tasks.values() 
                    if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
    
    # 3. Резюме прошлых ходов
    prev_turns = [
        f"[{t.turn_id}] {t.user_query[:50]} → {t.summary}"
        for t in self.turns.values() if t.turn_id != self.current_turn_id
    ]

    return {
        "goal": self.goal,
        "active_tasks": [t.model_dump(exclude={"result", "context"}) for t in active_tasks],
        "current_turn_steps": current_steps,
        "previous_turns_summary": "\n".join(prev_turns[-3:]),
        "dialogue_history": self.dialogue_history.format_for_prompt()
    }
```

В `PromptBuilderService`:
```python
# Заменить вызовы step_context.get_last_steps() на:
context = session_context.build_llm_context(max_steps=8)
variables["step_history"] = self._format_steps_for_prompt(context["current_turn_steps"])
variables["active_tasks"] = self._format_tasks_for_prompt(context["active_tasks"])
```

✅ **Как проверить:**
1. Добавить временный `print(json.dumps(context, indent=2, ensure_ascii=False))` перед вызовом LLM.
2. Убедиться, что в выводе:
   - Нет шагов из предыдущих вопросов
   - Есть только `PENDING/RUNNING` задачи
   - Прошлые вопросы сжаты в 1-2 строки
3. Проверить длину промпта в токенах (должна быть стабильной при 5+ ходах).

---

### 🔹 Фаза 5: Верификация и откат рисков
**Цель:** Гарантировать, что рефакторинг не сломал существующие сценарии.

| Шаг | Что делать | Как проверять |
|-----|------------|---------------|
| 5.1 | Запустить существующие бенчмарки | `python scripts/cli/koru.py bench run --limit 3` |
| 5.2 | Проверить multi-turn диалоги в UI | Задать 3 уточняющих вопроса, проверить историю |
| 5.3 | Нагрузочный тест контекста | 10 ходов подряд → проверить, что память/токены не растут линейно |
| 5.4 | Тест на откат | Если что-то ломается, включить флаг `LEGACY_CONTEXT_MODE=True` в конфиге |

**Чек-лист успешности:**
- [ ] `turn_id` создаётся при каждом `agent.run()`
- [ ] `Task` создаётся при декомпозиции плана
- [ ] `AgentStep` содержит `turn_id` и `task_id`
- [ ] LLM не видит шаги прошлых вопросов (проверено через лог промпта)
- [ ] Уточняющие вопросы корректно добавляют новые ходы, не теряя контекст
- [ ] Бенчмарки показывают `success_rate` ≥ прежнего значения

---
## 🛠️ С чего начать прямо сегодня?

1. **Создайте ветку:** `git checkout -b feature/task-context-refactor`
2. **Реализуйте Фазу 1:** Добавьте `Task`, `TurnMeta`, обновите `AgentStep`. Напишите 3 юнит-теста.
3. **Реализуйте Фазу 2:** Добавьте `TaskContext` в `SessionContext`, методы `start_turn`/`end_turn`. Проверьте интеграцию.
4. **Включите логирование контекста:** Временно выведите `build_llm_context()` в `main.py` и убедитесь, что структура данных соответствует ожиданиям.
5. **Только потом** меняйте `PlanningPattern` и `AgentRuntime`.

Если хотите, я подготовлю:
- Готовые файлы `task_context.py` и обновлённый `session_context.py` с полной обратной совместимостью
- Патч для `PromptBuilderService` с безопасной фильтрацией шагов
- Набор pytest-тестов для проверки изоляции ходов и задач
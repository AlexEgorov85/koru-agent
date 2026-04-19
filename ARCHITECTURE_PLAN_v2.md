# 🧭 Целевая архитектура (финальная, v2.0)

```text
Agent.run
  ↓
ReActEngine (prompt + SessionContext + AgentMetrics)
  ↓
LLM(prompt, response_schema=CONTRACT_YAML)
  ↓
Reflection Validation (self-check)
  ↓
Policy Check (system-check)
  ↓
Executor (skills/capabilities)
  ↓
Observer (LLM + OBS_CONTRACT)
  ↓
Update Metrics + Memory
  ↓
Next step (с учётом истории ошибок и наблюдений)
```

---

# ⚙️ PHASE 0 — Подготовка (адаптация под существующую базу)

## Шаг 0.1 — Использовать существующие контракты ✅

**НЕ СОЗДАВАТЬ** `schemas/` — это дублирование.

📁 `data/contracts/behavior/` — уже есть:

### `behavior.react.think_output_v1.0.0.yaml`

Содержит:
```yaml
stop_condition: boolean
analysis_final: string
analysis_alternatives: string
analysis_confidence: float
decision:
  next_action: string
  parameters: object
```

👉 **Действие:** Проверить, что контракт покрывает поля для reflection:
- Добавить `analysis_self_critique: string`
- Добавить `analysis_is_redundant: boolean`

---

### Новый контракт: `behavior.observe.output_v1.0.0.yaml`

📁 Создать: `data/contracts/behavior/behavior.observe.output_v1.0.0.yaml`

```yaml
status: enum[success, empty, error, partial]
quality: enum[high, low, useless]
issues: list[string]
insight: string
next_step_hint: string
confidence: float
```

👉 Это будет использоваться Observer компонентом.

---

## Шаг 0.2 — Проверить LLM wrapper ✅

Убедиться, что `LLMProvider.generate()` поддерживает:

```python
await llm.generate(
    prompt=prompt,
    response_schema=contract_dict  # из YAML через ContractService
)
```

📁 Проверить: `core/infrastructure/providers/llm/`

---

# PHASE 1 — AgentMetrics (вместо нового AgentState)

📁 Создать: `core/agent/metrics.py`

## Шаг 1.1 — класс AgentMetrics

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class AgentMetrics:
    step_number: int = 0
    errors: List[str] = field(default_factory=list)
    empty_results_count: int = 0
    repeated_actions_count: int = 0
    recent_actions: List[str] = field(default_factory=list)
    last_observation: Optional[Dict[str, Any]] = None
    
    def add_step(self, action_name: str, observation: Optional[Dict] = None):
        self.step_number += 1
        self.recent_actions.append(action_name)
        if len(self.recent_actions) > 10:
            self.recent_actions.pop(0)
        
        if observation:
            self.last_observation = observation
            if observation.get("status") == "empty":
                self.empty_results_count += 1
            if observation.get("quality") == "useless":
                self.errors.append("USELESS_RESULT")
    
    def add_error(self, error: str):
        self.errors.append(error)
        if len(self.errors) > 20:
            self.errors.pop(0)
    
    def check_repeat(self, action_name: str, window: int = 5) -> bool:
        recent = self.recent_actions[-window:]
        return action_name in recent
    
    def get_recent_actions(self, window: int = 5) -> List[str]:
        return self.recent_actions[-window:]
```

---

## Шаг 1.2 — Интеграция в SessionContext

📁 `core/session_context/session_context.py`

Добавить:

```python
from core.agent.metrics import AgentMetrics

class SessionContext:
    # ... существующие поля ...
    
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    
    def reset_metrics(self):
        self.metrics = AgentMetrics()
```

---

## Шаг 1.3 — Обновление в runtime

📁 `core/agent/runtime.py`

После выполнения шага:

```python
# После получения observation
session_context.metrics.add_step(
    action_name=step.decision.next_action,
    observation=observation
)
```

---

# PHASE 2 — ReActEngine (ядро с валидацией)

📁 `core/agent/behaviors/react/pattern.py`

## Шаг 2.1 — Расширить build_prompt

Убрать описание JSON структуры из prompt.

```python
def build_prompt(self, goal: str, session_context: SessionContext) -> str:
    metrics = session_context.metrics
    
    prompt = f"""
ЦЕЛЬ:
{goal}

ТЕКУЩЕЕ СОСТОЯНИЕ:
- шаг: {metrics.step_number}
- последние ошибки: {metrics.errors[-3:] if metrics.errors else 'нет'}
- пустых результатов: {metrics.empty_results_count}
- последних действий: {metrics.get_recent_actions(5)}

ПОСЛЕДНЕЕ НАБЛЮДЕНИЕ:
{metrics.last_observation or 'пока нет'}

ПРЕДЫДУЩИЕ НЕУДАЧИ (из FailureMemory):
{self.failure_memory.get_summary()}

ИНСТРУКЦИИ:
- не повторяй действия из последних 5 шагов
- если было 2+ пустых результата — меняй стратегию
- учитывай предыдущие ошибки
- проанализируй своё решение перед выполнением
"""
    
    return prompt
```

---

## Шаг 2.2 — generate_decision с валидацией

```python
async def generate_decision(self, session_context: SessionContext) -> ThinkOutput:
    prompt = self.build_prompt(session_context.goal, session_context)
    
    # Генерация через контракт
    result = await self.llm.generate(
        prompt=prompt,
        response_schema=self.contract  # из YAML
    )
    
    # Валидация reflection
    is_valid, reason = self.validate_reflection(result, session_context)
    
    if not is_valid:
        session_context.metrics.add_error(f"REFLECTION:{reason}")
        await self.event_bus.publish(EventType.DEBUG, {
            "event": "REFLECTION_BLOCK",
            "reason": reason,
            "step": session_context.metrics.step_number
        }, session_id=session_context.session_id, agent_id=self.agent_id)
        
        # Попытка перегенерировать (1 раз)
        if session_context.metrics.step_number < 3:
            return await self.generate_decision(session_context)
        
        raise ValueError(f"Reflection validation failed: {reason}")
    
    return result
```

---

## Шаг 2.3 — validate_reflection

```python
def validate_reflection(self, result: ThinkOutput, session_context: SessionContext) -> Tuple[bool, str]:
    metrics = session_context.metrics
    
    # Проверка на повтор действия
    if metrics.check_repeat(result.decision.next_action):
        return False, f"repeated_action:{result.decision.next_action}"
    
    # Проверка: stop без финального анализа
    if result.stop_condition and not result.analysis_final:
        return False, "stop_without_final_analysis"
    
    # Проверка на явный self-critique (если добавлено в контракт)
    if hasattr(result, 'analysis_self_critique'):
        if 'не уверен' in result.analysis_self_critique.lower() and result.analysis_confidence < 0.3:
            return False, "low_confidence_without_alternative"
    
    return True, None
```

---

# PHASE 3 — Policy (системный фильтр)

📁 `core/agent/components/policy.py`

## Шаг 3.1 — Расширить AgentPolicy

```python
class AgentPolicy:
    def __init__(self, config: PolicyConfig):
        self.config = config
    
    def check(self, step: ThinkOutput, metrics: AgentMetrics) -> Tuple[bool, str]:
        # Повтор действия (дублирующая проверка для надёжности)
        if metrics.check_repeat(step.decision.next_action, window=5):
            return False, "policy:repeat_action"
        
        # Empty loop detection
        if metrics.empty_results_count >= 2:
            last_two_actions = metrics.get_recent_actions(2)
            if len(set(last_two_actions)) == 1:
                return False, "policy:empty_loop"
        
        # Лимит ошибок
        if len(metrics.errors) >= self.config.max_errors:
            return False, "policy:max_errors_reached"
        
        # Лимит шагов
        if metrics.step_number >= self.config.max_steps:
            return False, "policy:max_steps_reached"
        
        return True, None
```

---

## Шаг 3.2 — Интеграция в runtime

📁 `core/agent/runtime.py`

```python
# После генерации шага
policy_allowed, policy_reason = self.policy.check(step, session_context.metrics)

if not policy_allowed:
    session_context.metrics.add_error(policy_reason)
    await self.event_bus.publish(EventType.DEBUG, {
        "event": "POLICY_BLOCK",
        "reason": policy_reason,
        "step": session_context.metrics.step_number
    }, session_id=session_context.session_id, agent_id=self.agent_id)
    
    # Попытка альтернативного действия
    step = await self.request_alternative(step, session_context)
```

---

# PHASE 4 — Execution (без изменений)

📁 `core/agent/runtime.py`

```python
result = await self.executor.execute(
    action_name=step.decision.next_action,
    parameters=step.decision.parameters,
    session_context=session_context
)
```

---

# PHASE 5 — Observer (LLM-анализ результата)

📁 Создать: `core/agent/components/observer.py`

## Шаг 5.1 — класс Observer

```python
from typing import Dict, Any, Optional
from pydantic import BaseModel

class Observation(BaseModel):
    status: str  # success, empty, error, partial
    quality: str  # high, low, useless
    issues: list[str]
    insight: str
    next_step_hint: str
    confidence: float

class Observer:
    def __init__(self, llm: LLMProvider, contract: dict):
        self.llm = llm
        self.contract = contract
    
    async def analyze(
        self,
        action_name: str,
        parameters: dict,
        result: Any,
        error: Optional[str] = None
    ) -> Observation:
        prompt = self._build_prompt(action_name, parameters, result, error)
        
        observation_data = await self.llm.generate(
            prompt=prompt,
            response_schema=self.contract
        )
        
        return Observation(**observation_data)
    
    def _build_prompt(
        self,
        action_name: str,
        parameters: dict,
        result: Any,
        error: Optional[str] = None
    ) -> str:
        result_str = str(result)[:2000] if result else "None"
        error_str = error or "Нет ошибки"
        
        return f"""
ДЕЙСТВИЕ:
{action_name}

ПАРАМЕТРЫ:
{parameters}

РЕЗУЛЬТАТ:
{result_str}

ОШИБКА (если есть):
{error_str}

ЗАДАЧА:
Проанализируй результат выполнения действия и оцени:
1. Статус (успех/пусто/ошибка/частично)
2. Качество результата
3. Проблемы (если есть)
4. Инсайт (что это значит для достижения цели)
5. Подсказку для следующего шага
6. Уверенность в оценке (0.0-1.0)
"""
```

---

## Шаг 5.2 — Интеграция в runtime

📁 `core/agent/runtime.py`

```python
# После выполнения действия
observation = await self.observer.analyze(
    action_name=step.decision.next_action,
    parameters=step.decision.parameters,
    result=execution_result,
    error=execution_error
)

# Обновление метрик
session_context.metrics.add_step(
    action_name=step.decision.next_action,
    observation=observation.dict()
)

# Публикация события
await self.event_bus.publish(EventType.INFO, {
    "event": "OBSERVATION",
    "status": observation.status,
    "quality": observation.quality,
    "insight": observation.insight
}, session_id=session_context.session_id, agent_id=self.agent_id)
```

---

# PHASE 6 — ErrorClassifier + FailureMemory (усиление)

📁 `core/agent/components/error_classifier.py` и `failure_memory.py`

## Шаг 6.1 — Классификация ошибок

```python
def classify(self, error: str, action_name: str) -> str:
    error_lower = error.lower()
    
    if "empty" in error_lower or "no results" in error_lower:
        return f"{action_name}:EMPTY_RESULT"
    
    if "timeout" in error_lower:
        return f"{action_name}:TIMEOUT"
    
    if "permission" in error_lower or "access" in error_lower:
        return f"{action_name}:PERMISSION_DENIED"
    
    if "syntax" in error_lower or "invalid" in error_lower:
        return f"{action_name}:INVALID_INPUT"
    
    return f"{action_name}:GENERAL_ERROR"
```

---

## Шаг 6.2 — Добавление в FailureMemory

```python
error_type = self.error_classifier.classify(execution_error, step.decision.next_action)
self.failure_memory.add(
    action=step.decision.next_action,
    error_type=error_type,
    context=session_context.goal
)
```

---

## Шаг 6.3 — Использование в prompt

В `build_prompt()` добавить:

```python
PREVIOUS_FAILURES:
{self.failure_memory.get_summary()}
```

Пример вывода:
```
- sql_query → EMPTY_RESULT (2 раза)
- api_call → TIMEOUT (1 раз)
```

---

# PHASE 7 — Anti-loop & Stop Logic

📁 `core/agent/runtime.py`

## Шаг 7.1 — Проверка условий остановки

```python
def should_stop(self, session_context: SessionContext) -> Tuple[bool, str]:
    metrics = session_context.metrics
    
    if metrics.repeated_actions_count >= 3:
        return True, "max_repeated_actions"
    
    if metrics.empty_results_count >= 3:
        return True, "max_empty_results"
    
    if len(metrics.errors) >= self.policy.config.max_errors:
        return True, "max_errors"
    
    if metrics.step_number >= self.policy.config.max_steps:
        return True, "max_steps"
    
    return False, None
```

---

## Шаг 7.2 — Fallback ответ

```python
def build_fallback_response(self, session_context: SessionContext) -> dict:
    return {
        "final_answer": f"Не удалось завершить задачу после {session_context.metrics.step_number} шагов",
        "errors": session_context.metrics.errors,
        "steps_taken": session_context.metrics.step_number,
        "last_observation": session_context.metrics.last_observation,
        "recommendation": self._generate_recommendation(session_context)
    }
```

---

# PHASE 8 — EventBus (полная интеграция)

📁 `core/agent/runtime.py`

## Шаг 8.1 — События для отладки

```python
# На каждом этапе
await self.event_bus.publish(EventType.DEBUG, {
    "event": "AGENT_STEP",
    "step_number": metrics.step_number,
    "action": step.decision.next_action
}, session_id=..., agent_id=...)

await self.event_bus.publish(EventType.DEBUG, {
    "event": "REFLECTION_BLOCK",
    "reason": reason
}, session_id=..., agent_id=...)

await self.event_bus.publish(EventType.DEBUG, {
    "event": "POLICY_BLOCK",
    "reason": reason
}, session_id=..., agent_id=...)

await self.event_bus.publish(EventType.INFO, {
    "event": "OBSERVATION",
    "status": observation.status,
    "quality": observation.quality
}, session_id=..., agent_id=...)

await self.event_bus.publish(EventType.WARN, {
    "event": "AGENT_STOP",
    "reason": stop_reason,
    "total_steps": metrics.step_number
}, session_id=..., agent_id=...)
```

---

# 🧠 Итоговый пайплайн

```text
1. ReActEngine.build_prompt(goal, metrics, failure_memory)
2. LLM.generate(prompt, contract=THINK_CONTRACT)
3. Reflection Validation (self-check)
   └─ Если фейл → retry или ошибка
4. Policy Check (system-check)
   └─ Если фейл → request alternative
5. Executor.execute(action, parameters)
6. Observer.analyze(result) → Observation
7. Update Metrics (errors, empty_count, recent_actions)
8. FailureMemory.add(if error)
9. EventBus.publish(events)
10. Check stop conditions
    └─ Если стоп → fallback
    └─ Иначе → шаг 1
```

---

# 🔥 Ключевые отличия от старого плана

| Было | Стало | Почему лучше |
|------|-------|--------------|
| `schemas/` | `data/contracts/` | Используем существующую инфраструктуру |
| `AgentState` | `AgentMetrics` + `SessionContext` | Не дублируем, расширяем |
| JSON в prompt | YAML контракт | Структура вынесена, prompt чище |
| Нет Observer | `Observer` компонент | Результат → сигнал для обучения |
| Слабый Policy | Расширенный Policy | Проверка на повторы и empty_loop |
| Нет явной Reflection | `validate_reflection()` | Ранний фильтр "глупости" |

---

# ⚠️ Критические правила

✅ **ДЕЛАТЬ:**
- Использовать существующие YAML контракты
- Расширять `SessionContext` через `AgentMetrics`
- Валидировать reflection до выполнения
- Анализировать результат через Observer
- Публиковать все события в EventBus

❌ **НЕ ДЕЛАТЬ:**
- Не создавать `schemas/` (дублирование)
- Не дублировать структуру контракта в prompt
- Не игнорировать `empty_results_count`
- Не пропускать Policy check
- Не забывать обновлять `recent_actions`

---

# 💥 Итог

После реализации агент будет:

### ✔
- Думать структурированно (через YAML контракты)
- Проверять себя (Reflection Validation)
- Контролироваться системой (Policy Check)
- Анализировать результаты (Observer)
- Учиться на ошибках (FailureMemory)
- Избегать циклов (Anti-loop logic)
- Полностью отслеживаться (EventBus)

### ❌ Не будет:
- Зацикливаться на одних действиях
- Игнорировать пустые результаты
- Делать шаги без самопроверки
- Терять контекст ошибок

---

# 🚀 Следующие шаги (опционально)

После завершения этой архитектуры можно добавить:

1. **Adaptive Prompt Builder** — автоматическая смена стиля prompt при repeated failures
2. **Planner + Executor Split** — разделение планирования и выполнения (+50% к качеству)
3. **Tool-Aware Reasoning** — разные стратегии для SQL / API / Search
4. **Human-in-the-Loop** — запрос подтверждения при низком confidence

Готов приступить к реализации?

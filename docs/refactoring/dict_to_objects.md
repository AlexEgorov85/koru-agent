# Места для рефакторинга: dict → объекты

**Дата:** 6 марта 2026 г.  
**Приоритет:** Средний (после критических исправлений)

---

## ✅ Выполнено

### 1. ReAct Pattern — LLM вызовы
**Файл:** `core/application/behaviors/react/pattern.py`

**Было:**
```python
# Обёртка dict вместо объекта
structured_response = {
    'raw_response': response,
    'content': response.content,
    'metadata': response.metadata
}
```

**Стало:**
```python
# Прямое использование StructuredLLMResponse
return True, response, ""  # response — StructuredLLMResponse объект
```

**Коммит:** `593e553`

---

## 📋 Требуют рефакторинга

### 2. validate_reasoning_result
**Файл:** `core/application/agent/strategies/react/validation.py`

**Проблема:** Возвращает `Dict[str, Any]` вместо типизированного объекта

**Текущая сигнатура:**
```python
def validate_reasoning_result(result: Any) -> Dict[str, Any]:
```

**Рекомендация:**
```python
from dataclasses import dataclass

@dataclass
class ReasoningResult:
    thought: str
    decision: Decision
    analysis: Analysis
    confidence: float
    stop_condition: bool
    available_capabilities: List[Capability]

def validate_reasoning_result(result: Any) -> ReasoningResult:
```

**Сложность:** Средняя  
**Риск:** Низкий (внутренний API)

---

### 3. analyze_context
**Файл:** `core/application/agent/strategies/react/utils.py`

**Проблема:** Возвращает dict вместо объекта

**Текущая сигнатура:**
```python
def analyze_context(session_context: 'SessionContext') -> Dict[str, Any]:
```

**Рекомендация:**
```python
@dataclass
class ContextAnalysis:
    current_situation: str
    progress_assessment: str
    confidence: float
    errors_detected: bool
    consecutive_errors: int
    execution_time_seconds: float
    no_progress_steps: int
    goal: str

def analyze_context(session_context: 'SessionContext') -> ContextAnalysis:
```

**Сложность:** Низкая  
**Риск:** Низкий

---

### 4. SchemaValidator
**Файл:** `core/application/agent/strategies/react/schema_validator.py`

**Проблема:** Использует dict для схем

**Текущий код:**
```python
class SchemaValidator:
    _schemas_cache: Dict[str, Dict[str, Any]]
    
    def register_capability_schema(self, capability_name: str, input_schema: Dict[str, Any]):
    
    def get_capability_schema(self, capability_name: str) -> Optional[Dict[str, Any]]:
```

**Рекомендация:**
```python
from pydantic import BaseModel

class CapabilitySchema(BaseModel):
    capability_name: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    parameter_validators: List[ParameterValidator]

class SchemaValidator:
    _schemas_cache: Dict[str, CapabilitySchema]
    
    def register_capability_schema(self, schema: CapabilitySchema):
    
    def get_capability_schema(self, capability_name: str) -> Optional[CapabilitySchema]:
```

**Сложность:** Средняя  
**Риск:** Средний (используется в ActionExecutor)

---

### 5. ActionExecutor.execute_action
**Файл:** `core/application/agent/components/action_executor.py`

**Проблема:** Параметры как dict

**Текущая сигнатура:**
```python
async def execute_action(
    self,
    action_name: str,
    parameters: Dict[str, Any],  # ❌ dict
    context: ExecutionContext
) -> ActionResult:
```

**Рекомендация:**
```python
from pydantic import BaseModel

class ActionParameters(BaseModel):
    capability_name: str
    parameters: Dict[str, Any]
    validation_schema: Optional[Dict[str, Any]] = None

async def execute_action(
    self,
    action_name: str,
    parameters: ActionParameters,  # ✅ объект
    context: ExecutionContext
) -> ActionResult:
```

**Сложность:** Высокая  
**Риск:** Высокий (центральный компонент)

---

### 6. ActionExecutor._execute_context_action
**Файл:** `core/application/agent/components/action_executor.py`

**Проблема:** Множество методов с `parameters: Dict[str, Any]`

**Методы:**
- `_context_record_plan(parameters: Dict[str, Any], ...)`
- `_context_get_current_plan(parameters: Dict[str, Any], ...)`
- `_context_get_context_item(parameters: Dict[str, Any], ...)`
- `_context_get_all_items(parameters: Dict[str, Any], ...)`
- `_context_get_step_history(parameters: Dict[str, Any], ...)`
- `_context_record_action(parameters: Dict[str, Any], ...)`
- `_context_record_observation(parameters: Dict[str, Any], ...)`

**Рекомендация:** Создать классы параметров для каждого действия:

```python
@dataclass
class RecordPlanParams:
    plan_data: Any
    plan_type: str = "initial"
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class GetContextItemParams:
    item_id: str
    raise_on_missing: bool = False
```

**Сложность:** Средняя  
**Риск:** Средний

---

### 7. ActionExecutor._execute_llm_action
**Файл:** `core/application/agent/components/action_executor.py`

**Проблема:** Параметры LLM как dict

**Текущий код:**
```python
async def _llm_generate(
    self,
    llm_provider,
    parameters: Dict[str, Any],  # ❌
    orchestrator: Any = None,
    context: ExecutionContext = None
) -> ActionResult:
    prompt = parameters.get("prompt", "")
    temperature = parameters.get("temperature", 0.7)
```

**Рекомендация:**
```python
# Уже есть LLMRequest в core/models/types/llm_types.py
async def _llm_generate(
    self,
    llm_provider,
    request: LLMRequest,  # ✅
    orchestrator: Any = None,
    context: ExecutionContext = None
) -> ActionResult:
```

**Сложность:** Низкая  
**Риск:** Низкий (LLMRequest уже существует)

---

### 8. AgentState.snapshot
**Файл:** `core/application/agent/components/state.py`

**Проблема:** Возвращает dict

**Текущая сигнатура:**
```python
def snapshot(self) -> Dict[str, Any]:
```

**Рекомендация:**
```python
@dataclass
class AgentStateSnapshot:
    step: int
    error_count: int
    consecutive_errors: int
    no_progress_steps: int
    strategy_switches: int
    plan_corrections: int
    finished: bool

def snapshot(self) -> AgentStateSnapshot:
```

**Сложность:** Низкая  
**Риск:** Низкий

---

## 📊 Сводка

| Компонент | Файл | Сложность | Риск | Приоритет |
|-----------|------|-----------|------|-----------|
| ✅ ReAct LLM | pattern.py | Низкая | Низкий | ✅ Выполнено |
| validate_reasoning_result | validation.py | Средняя | Низкий | Средний |
| analyze_context | utils.py | Низкая | Низкий | Средний |
| SchemaValidator | schema_validator.py | Средняя | Средний | Низкий |
| ActionExecutor.execute_action | action_executor.py | Высокая | Высокий | Низкий |
| ActionExecutor context actions | action_executor.py | Средняя | Средний | Низкий |
| ActionExecutor LLM actions | action_executor.py | Низкая | Низкий | Средний |
| AgentState.snapshot | state.py | Низкая | Низкий | Низкий |

---

## 🎯 План рефакторинга

### Этап 1: Низкий риск (1-2 часа)
1. ✅ ReAct Pattern LLM — **ВЫПОЛНЕНО**
2. `analyze_context` → `ContextAnalysis` dataclass
3. `AgentState.snapshot` → `AgentStateSnapshot` dataclass

### Этап 2: Средний риск (3-4 часа)
4. `validate_reasoning_result` → `ReasoningResult` dataclass
5. `_llm_generate` → использовать `LLMRequest`
6. `SchemaValidator` → `CapabilitySchema`

### Этап 3: Высокий риск (6-8 часов)
7. `ActionExecutor.execute_action` → `ActionParameters`
8. Context actions → отдельные классы параметров

---

## 🔍 Как искать подобные места

### grep паттерны:
```bash
# Поиск функций возвращающих Dict
grep -r "-> Dict\[" core/application/agent/

# Поиск параметров dict
grep -r "parameters: Dict\[str, Any\]" core/application/agent/

# Поиск 'raw_response', 'parsed_content' как ключей dict
grep -r "'raw_response'" core/application/agent/
```

### Индикаторы проблем:
- `Dict[str, Any]` в сигнатурах
- `parameters.get("...")` вместо `parameters.field`
- Обёртки dict вокруг объектов
- `hasattr()` проверки вместо type hints

---

## 📝 Принципы

### ✅ Используйте объекты когда:
- Есть повторяющаяся структура данных
- Нужна типобезопасность
- Данные передаются между компонентами
- Требуется валидация

### ⚠️ Dict допустимы когда:
- Простые ключ-значение пары
- Динамическая структура (неизвестна заранее)
- Временные данные внутри функции
- Интеграция с внешним API

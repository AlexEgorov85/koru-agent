# 📋 Архитектурный Рефакторинг: Сохранение Типизации Pydantic Моделей

## 🎯 Цель

Устранить критическое архитектурное нарушение — потерю типизации Pydantic моделей после первого компонента в конвейере выполнения.

---

## ❌ Проблема (До Рефакторинга)

### Поток Данных:
```
LLMOrchestrator
    ↓ StructuredLLMResponse[PydanticModel]  ✅ Типизировано
    ↓
ActionExecutor
    ↓ dict (model_dump())  ❌ ПОТЕРЯ ТИПОВ!
    ↓
Component (Skill/Tool)
    ↓ dict  ❌ Нет гарантии полей!
    ↓
Business Logic
    ↓ data.get('field')  ❌ Runtime ошибки!
```

### Конкретные Места Потери Типов:

| Файл | Строка | Проблема |
|------|--------|----------|
| `action_executor.py` | ~632 | `response.parsed_content.model_dump()` |
| `react/pattern.py` | ~843 | `response.parsed_content.model_dump()` |
| `evaluation/pattern.py` | ~271 | `result.model_dump()` |

### Последствия:

| Проблема | Последствие |
|----------|-------------|
| **Потеря валидации** | Поля могут отсутствовать или иметь неверный тип |
| **Runtime ошибки** | `KeyError`, `AttributeError` в бизнес-логике |
| **Нет IDE поддержки** | Автокомплит не работает для dict |
| **Неявные контракты** | Типы данных не документированы |
| **Сложный рефакторинг** | Невозможно отследить где какие поля используются |

---

## ✅ Решение (После Рефакторинга)

### Архитектурный Принцип:
```
┌─────────────────────────────────────────────────────────────┐
│  ВНУТРИ ПРИЛОЖЕНИЯ (Application Layer)                     │
│  → Pydantic модели (типизировано, валидировано)            │
└─────────────────────────────────────────────────────────────┘
                          ↓
              [ГРАНИЦА СЕРИАЛИЗАЦИИ]
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  НА ГРАНИЦАХ (EventBus/Storage/API)                        │
│  → dict/JSON (только для сериализации)                     │
└─────────────────────────────────────────────────────────────┘
```

### Новый Поток Данных:
```
LLMOrchestrator
    ↓ StructuredLLMResponse[T]  ✅ Generic тип сохранён
    ↓
ActionExecutor
    ↓ ActionResult[T]  ✅ Pydantic модель типа T
    ↓
Component.execute()
    ↓ ExecutionResult.result: BaseModel  ✅ Типизировано
    ↓
Business Logic
    ↓ result.data.field  ✅ IDE автокомплит, валидация
```

---

## 🛠️ Внесённые Изменения

### 1. `ActionResult` — Generic Тип для Сохранения Моделей

**Файл:** `core/application/agent/components/action_executor.py`

```python
# ❌ БЫЛО:
class ActionResult:
    def __init__(self, success: bool, data: Any = None, ...):
        self.data = data or {}  # dict

# ✅ СТАЛО:
T = TypeVar('T')

class ActionResult(Generic[T]):
    def __init__(
        self, 
        success: bool, 
        data: Optional[T] = None,  # ← Сохраняем тип T!
        metadata: Dict[str, Any] = None, 
        error: str = None,
        llm_called: bool = False
    ):
        self.data = data  # ← Pydantic модель или None
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация ТОЛЬКО для границ приложения"""
        return {
            'success': self.success,
            'data': self.data.model_dump() if isinstance(self.data, BaseModel) else self.data,
            'metadata': self.metadata,
            'error': self.error,
            'llm_called': self.llm_called
        }
```

**Преимущества:**
- `ActionResult[BookLibrarySearchOutput]` сохраняет тип
- IDE поддерживает автокомплит полей
- Сериализация только при вызове `to_dict()`

---

### 2. `SkillResult` / `ExecutionResult` — Сохранение Моделей

**Файл:** `core/models/data/execution.py`

```python
# ❌ БЫЛО:
@dataclass
class SkillResult:
    data: Optional[Any] = None  # dict
    
    def to_dict(self) -> Dict[str, Any]:
        return {"technical_success": ..., "data": self.data}  # data уже dict

# ✅ СТАЛО:
@dataclass
class SkillResult:
    data: Optional[Any] = None  # ← Может быть Pydantic моделью!
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация ТОЛЬКО на границах"""
        return {
            "technical_success": self.technical_success,
            "data": self.data.model_dump() if isinstance(self.data, BaseModel) else self.data,
            ...
        }
```

---

### 3. `ActionExecutor._llm_generate_structured` — Убрана Преждевременная Сериализация

**Файл:** `core/application/agent/components/action_executor.py`

```python
# ❌ БЫЛО:
return ActionResult(
    success=True,
    data={
        "parsed_content": response.parsed_content.model_dump(),  # ❌ ПОТЕРЯ ТИПОВ!
        "raw_content": response.raw_response.content
    },
    ...
)

# ✅ СТАЛО:
return ActionResult.success_result(
    data=response.parsed_content,  # ← Pydantic модель типа T
    metadata={
        "model": response.raw_response.model,
        "tokens_used": response.raw_response.tokens_used,
        "raw_content": response.raw_response.content
    }
)
```

---

### 4. `BaseComponent` — Типизированная Валидация

**Файл:** `core/components/base_component.py`

#### Новые Методы:

```python
def validate_input_typed(self, capability_name: str, data: Dict) -> Optional[BaseModel]:
    """
    Возвращает валидированную Pydantic модель вместо bool.
    
    EXAMPLE:
        validated: BookLibrarySearchInput = self.validate_input_typed('search', data)
        if validated:
            query = validated.query  # ✅ IDE знает тип
    """

def validate_output_typed(self, capability_name: str, data: Any) -> Optional[BaseModel]:
    """
    Возвращает валидированную Pydantic модель вместо bool.
    
    EXAMPLE:
        validated: BookLibrarySearchOutput = self.validate_output_typed('search', result)
        if validated:
            rows = validated.rows  # ✅ IDE знает тип
    """
```

#### Обновлённый `execute()`:

```python
async def execute(self, capability, parameters, execution_context) -> ExecutionResult:
    # ✅ Валидация входа с возвратом модели
    validated_input = self.validate_input_typed(capability.name, parameters)
    if validated_input is None:
        return ExecutionResult.failed(...)
    
    # ✅ Передаём модель в бизнес-логику
    result = await self._execute_impl(capability, validated_input, execution_context)
    
    # ✅ Валидация выхода с возвратом модели
    validated_output = self.validate_output_typed(capability.name, result)
    if validated_output is None:
        return ExecutionResult.failed(...)
    
    # ✅ Возвращаем модель (сохраняется типизация)
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        result=validated_output,  # ← Pydantic модель, не dict!
        metadata={...}
    )
```

---

### 5. `react/pattern.py` — Сохранение Модели Рассуждения

**Файл:** `core/application/behaviors/react/pattern.py`

```python
# ❌ БЫЛО:
if response.parsed_content:
    if hasattr(response.parsed_content, 'model_dump'):
        result = response.parsed_content.model_dump()  # ❌ ПОТЕРЯ ТИПОВ!

# ✅ СТАЛО:
if response.parsed_content:
    result = response.parsed_content  # ← Pydantic модель, не dict!
```

---

### 6. `validation.py` — Поддержка Pydantic Моделей

**Файл:** `core/application/agent/strategies/react/validation.py`

```python
def validate_reasoning_result(result: Any) -> ReasoningResult:
    # ✅ Принимает Pydantic модель напрямую
    elif hasattr(result, 'model_fields') and hasattr(result, 'model_dump'):
        validated_dict = result.model_dump()  # Конвертируем только для валидации
```

---

## 📊 Сравнение До/После

| Аспект | До | После |
|--------|-----|-------|
| **Тип данных в конвейере** | `dict` | `BaseModel[T]` |
| **IDE автокомплит** | ❌ Нет | ✅ Да |
| **Валидация полей** | Runtime | Compile-time + Runtime |
| **Сериализация** | Везде | Только на границах |
| **Ошибки типов** | Runtime | Type checker + Runtime |
| **Рефакторинг** | Сложный | Безопасный |

---

## 🎯 Пример Использования

### До Рефакторинга:
```python
# ❌ Нет гарантии что поле существует
result = await executor.execute_action(...)
query = result.data.get('query')  # Может вернуть None!
books = result.data.get('rows', [])  # Runtime ошибка если нет поля
```

### После Рефакторинга:
```python
# ✅ Типизированный доступ к полям
result: ActionResult[BookLibrarySearchOutput] = await executor.execute_action(...)

# IDE автокомплит + валидация типов
query: str = result.data.query  # ✅ Тип известен
books: List[Dict] = result.data.rows  # ✅ Тип известен
count: int = result.data.rowcount  # ✅ Тип известен

# Сериализация только на границе
await event_bus.publish(
    EventType.SKILL_EXECUTED,
    data=result.to_dict()  # ← model_dump() вызывается здесь
)
```

---

## 📋 Чеклист Миграции Компонентов

Для каждого компонента (Skill/Tool/Service):

- [ ] **Входные параметры:** Использовать `validate_input_typed()` вместо `validate_input()`
- [ ] **Выходные данные:** Использовать `validate_output_typed()` вместо `validate_output()`
- [ ] **Возвращаемое значение:** Возвращать Pydantic модель из `_execute_impl()`
- [ ] **Сериализация:** Вызывать `model_dump()` только в `_publish_metrics()` для EventBus

---

## 🔍 Проверка Изменений

### Запуск Типового Чекера:
```bash
mypy core/
```

### Запуск Тестов:
```bash
pytest tests/unit/components/ -v
pytest tests/integration/ -v
```

### Проверка Отсутствия `model_dump()` в Конвейере:
```bash
# Ищем model_dump() вне границ (storage, event_bus)
rg "model_dump\(\)" --type py \
  --glob "!*storage*" \
  --glob "!*event_bus*" \
  --glob "!*__pycache__*"
```

---

## 🚀 Следующие Шаги

1. **Обновить все компоненты** с использованием `validate_input_typed()`/`validate_output_typed()`
2. **Добавить INPUT_MODEL/OUTPUT_MODEL** атрибуты в каждый компонент
3. **Настроить mypy** для строгой проверки типов
4. **Документировать типы** в контрактах компонентов

---

## 📚 Связанная Документация

- [STRUCTURED_OUTPUT_ROADMAP.md](docs/plans/STRUCTURED_OUTPUT_ROADMAP.md)
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md)
- [DI_MIGRATION_REPORT.md](DI_MIGRATION_REPORT.md)

# Руководство по использованию существующих типов

**Дата:** 6 марта 2026 г.  
**Принцип:** Не создавать новые классы если уже есть подходящие

---

## ✅ Существующие типы (использовать их!)

### 1. LLM типы

**Файл:** `core/models/types/llm_types.py`

```python
from core.models.types.llm_types import (
    LLMRequest,              # Запрос к LLM
    LLMResponse,             # Ответ LLM
    StructuredOutputConfig,  # Конфигурация структурированного вывода
    StructuredLLMResponse,   # Структурированный ответ
    LLMHealthStatus          # Статус здоровья провайдера
)

# Пример использования
request = LLMRequest(
    prompt="Объясни квантовые вычисления",
    system_prompt="Ты — эксперт по физике",
    temperature=0.7,
    max_tokens=500,
    structured_output=StructuredOutputConfig(
        output_model="ExplanationOutput",
        schema_def=schema,
        max_retries=3
    )
)

response = await provider.generate(request)
```

**НЕ СОЗДАВАТЬ:** `LLMInterface`, `LLMConfig`, `LLMResult`

---

### 2. Типы выполнения

**Файл:** `core/models/data/execution.py`

```python
from core.models.data.execution import (
    SkillResult,              # Результат выполнения skill
    ExecutionResult,          # Результат выполнения задачи
    ExecutionContextSnapshot  # Снимок контекста
)

# Пример использования
result = SkillResult.success(
    data={"books": [...]},
    metadata={"tokens": 100},
    side_effect=False
)

if not result.technical_success:
    logger.error(result.error)
```

**НЕ СОЗДАВАТЬ:** `ActionResult`, `SkillOutput`, `ExecutionData`

---

### 3. Метрики

**Файл:** `core/models/data/metrics.py`

```python
from core.models.data.metrics import (
    MetricType,
    MetricPoint,
    MetricSeries
)
```

**НЕ СОЗДАВАТЬ:** `Metric`, `MetricData`, `MetricsResult`

---

### 4. Benchmark типы

**Файл:** `core/models/data/benchmark.py`

```python
from core.models.data.benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkMetrics,
    BenchmarkComparison
)
```

**НЕ СОЗДАВАТЬ:** `BenchmarkData`, `BenchmarkStats`

---

### 5. Capability и Prompt

**Файл:** `core/models/data/capability.py`, `core/models/data/prompt.py`

```python
from core.models.data.capability import Capability
from core.models.data.prompt import Prompt, PromptStatus
```

**НЕ СОЗДАВАТЬ:** `CapabilityData`, `PromptConfig`

---

## 📋 Правила

### ✅ Делайте

1. **Проверяйте `core/models/` перед созданием нового класса**
   ```bash
   # Поиск существующих типов
   grep -r "class.*Result" core/models/
   grep -r "@dataclass" core/models/
   ```

2. **Используйте существующие типы даже если они не идеальны**
   ```python
   # Лучше использовать существующий с доп. полем
   result = SkillResult(...)
   result.custom_field = "value"  # Расширение
   
   # Чем создавать новый класс
   class MyResult:  # ❌
       ...
   ```

3. **Расширяйте через наследование если нужно**
   ```python
   from core.models.data.execution import SkillResult
   
   @dataclass
   class ExtendedSkillResult(SkillResult):
       extra_field: str = ""
   ```

### ❌ Не делайте

1. **Не создавайте дублирующие классы**
   ```python
   # ❌ ПЛОХО
   class LLMResult:  # Уже есть LLMResponse!
       content: str
   
   # ✅ ХОРОШО
   from core.models.types.llm_types import LLMResponse
   ```

2. **Не создавайте Protocol если есть конкретная реализация**
   ```python
   # ❌ ПЛОХО
   class LLMInterface(Protocol):
       async def generate(...) -> str: ...
   
   # ✅ ХОРОШО
   from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
   ```

3. **Не оборачивайте существующие типы без необходимости**
   ```python
   # ❌ ПЛОХО
   class MyLLMRequest:
       def __init__(self, request: LLMRequest):
           self._request = request  # Лишняя обёртка
   
   # ✅ ХОРОШО
   # Используйте LLMRequest напрямую
   ```

---

## 🔍 Поиск существующих типов

### Команды для поиска

```bash
# Поиск dataclass
grep -r "@dataclass" core/models/

# Поиск классов с определёнными полями
grep -r "content: str" core/models/

# Поиск по имени
grep -r "class.*Result" core/models/
```

### Структура `core/models/`

```
core/models/
├── types/           # Типы данных (LLM, DB, Vector)
│   ├── llm_types.py
│   └── db_types.py
├── data/            # Модели данных
│   ├── execution.py
│   ├── metrics.py
│   ├── benchmark.py
│   ├── capability.py
│   └── prompt.py
├── schemas/         # Схемы валидации
└── errors/          # Типы ошибок
```

---

## 📊 Таблица соответствия

| Задача | Существующий класс | Файл |
|--------|-------------------|------|
| Запрос к LLM | `LLMRequest` | `types/llm_types.py` |
| Ответ LLM | `LLMResponse` | `types/llm_types.py` |
| Структурированный вывод | `StructuredOutputConfig` | `types/llm_types.py` |
| Результат skill | `SkillResult` | `data/execution.py` |
| Результат выполнения | `ExecutionResult` | `data/execution.py` |
| Метрика | `MetricPoint` | `data/metrics.py` |
| Benchmark результат | `BenchmarkResult` | `data/benchmark.py` |
| Capability | `Capability` | `data/capability.py` |
| Prompt | `Prompt` | `data/prompt.py` |
| Конфигурация БД | `DBConnectionConfig` | `types/db_types.py` |

---

## 🎯 Рефакторинг: замена новых классов на существующие

### Было (создали новый класс)

```python
@dataclass
class MyLLMResult:
    content: str
    model: str
    tokens: int
```

### Стало (используем существующий)

```python
from core.models.types.llm_types import LLMResponse

# Используем напрямую
response: LLMResponse = await provider.generate(request)
print(response.content, response.model, response.tokens_used)
```

---

## 📝 Чек-лист перед созданием класса

- [ ] Проверил `core/models/types/`?
- [ ] Проверил `core/models/data/`?
- [ ] Поискал через `grep -r "class.*"`?
- [ ] Можно использовать существующий с расширением?
- [ ] Не дублирует ли функциональность?

Если на все вопросы "Да" — создавайте новый класс.

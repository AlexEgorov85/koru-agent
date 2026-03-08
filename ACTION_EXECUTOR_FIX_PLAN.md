# 📋 План исправления использования ActionExecutor

**Дата создания:** 7 марта 2026  
**Статус:** Утверждён  
**Приоритет:** Критический  

---

## 📊 Текущее состояние

| Метрика | Значение |
|---------|----------|
| **Всего проанализировано файлов** | 50 |
| **Используют executor правильно** | 10 (20%) |
| **Смешанный стиль** | 12 (24%) |
| **Нарушают изоляцию** | 28 (56%) |

### Критические нарушения

| Тип нарушения | Файлов | Примеры |
|--------------|--------|---------|
| Прямые вызовы компонентов | 10 | `components.get()`, `.execute()` |
| Прямой доступ к инфраструктуре | 19 | `get_provider()`, `db_provider.execute()` |
| Прямой доступ к session_context | 48 | `session_context.record_action()`, `get_goal()` |

---

## 🎯 Архитектурные принципы

### ✅ Правильные паттерны

```python
# 1. LLM вызовы через executor
llm_result = await self.executor.execute_action(
    action_name="llm.generate_structured",
    parameters={"prompt": rendered_prompt, ...},
    context=execution_context
)

# 2. Контекст через executor
save_result = await self.executor.execute_action(
    action_name="context.record_plan",
    parameters={"plan_data": plan_data},
    context=execution_context
)

# 3. SQL через executor
query_result = await self.executor.execute_action(
    action_name="sql_query.execute",
    parameters={"sql": query},
    context=execution_context
)
```

### ❌ Запрещённые паттерны

```python
# 1. Прямые вызовы компонентов
file_tool = self.application_context.components.get(ComponentType.TOOL, "file_tool")
result = await file_tool.execute(input_data)  # ЗАПРЕЩЕНО

# 2. Прямой доступ к инфраструктуре
llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
db_provider = self.application_context.infrastructure_context.get_provider("default_db")

# 3. Прямая работа с session_context
self.application_context.session_context.record_action({...})
session_context.get_goal()
```

---

## 🔴 Фаза 1: Критические исправления (Week 1)

### 1.1 Behaviors: Прямой доступ к session_context

#### Файл: `core/application/behaviors/react/pattern.py`

**Проблема:** Прямой доступ к `session_context` и `infrastructure_context`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 109, 768 | `infrastructure_context.get_provider("default_llm")` | `executor.execute_action("llm.generate", ...)` |
| 671 | `session_context.current_step` | `executor.execute_action("context.get_step", ...)` |
| 801, 804 | `session_context.get_goal()` | `executor.execute_action("context.get_goal", ...)` |
| 1185, 1242, 1272 | `session_context.*` | `executor.execute_action("context.*", ...)` |

**План исправления:**

```python
# ❌ БЫЛО (строка 768)
llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")

# ✅ СТАЛО
llm_result = await self.executor.execute_action(
    action_name="llm.generate_structured",
    parameters={
        "prompt": reasoning_prompt,
        "structured_output": {
            "output_model": "ReasoningResult",
            "schema_def": self.reasoning_schema,
            "max_retries": 3,
            "strict_mode": False
        },
        "temperature": 0.3,
        "max_tokens": 1000
    },
    context=execution_context
)
```

```python
# ❌ БЫЛО (строка 801)
goal = session_context.get_goal()

# ✅ СТАЛО
goal_result = await self.executor.execute_action(
    action_name="context.get_goal",
    parameters={},
    context=execution_context
)
goal = goal_result.data.get("goal", "unknown") if goal_result.success else "unknown"
```

**Требуемые изменения в ActionExecutor:**

Добавить новые действия контекста в `action_executor.py`:

```python
# В метод _execute_context_action добавить:
elif action_name == "context.get_goal":
    return self._context_get_goal(parameters, session_context)
elif action_name == "context.get_summary":
    return self._context_get_summary(parameters, session_context)
elif action_name == "context.get_recent_errors":
    return self._context_get_recent_errors(parameters, session_context)
```

---

#### Файл: `core/application/behaviors/planning/pattern.py`

**Проблема:** Прямой доступ к `session_context`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 41 | `session_context.get_current_plan()` | `executor.execute_action("context.get_current_plan", ...)` |
| 58-59 | `session_context.get_goal()`, `get_summary()` | `executor.execute_action("context.get_*", ...)` |
| 167 | `session_context.execute_capability()` | `executor.execute_capability(...)` |

**План исправления:**

```python
# ❌ БЫЛО (строка 41)
current_plan = session_context.get_current_plan()

# ✅ СТАЛО
plan_result = await self.executor.execute_action(
    action_name="context.get_current_plan",
    parameters={},
    context=execution_context
)
current_plan = plan_result.data if plan_result.success else None
```

---

#### Файл: `core/application/behaviors/evaluation/pattern.py`

**Проблема:** Прямой доступ к `session_context` и `infrastructure_context`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 150, 156-157 | `session_context.get_summary()`, `get_goal()` | `executor.execute_action("context.get_*", ...)` |
| 212 | `infrastructure_context.get_provider("default_llm")` | `executor.execute_action("llm.generate", ...)` |

---

#### Файл: `core/application/behaviors/fallback/pattern.py`

**Проблема:** Прямой доступ к `session_context`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 42-44 | `session_context.get_recent_errors()`, `get_summary()` | `executor.execute_action("context.get_*", ...)` |
| 150 | `session_context.get_summary()` | `executor.execute_action("context.get_summary", ...)` |

---

### 1.2 Skills: Прямые вызовы компонентов

#### Файл: `core/application/skills/data_analysis/skill.py`

**Проблема:** Прямые вызовы `file_tool` и `sql_tool`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 471-485 | `file_tool = components.get(...); await file_tool.execute()` | `executor.execute_action("file_tool.read", ...)` |
| 510-527 | `sql_tool = components.get(...); await sql_tool.execute()` | `executor.execute_action("sql_tool.execute", ...)` |

**План исправления:**

```python
# ❌ БЫЛО (строки 471-485)
file_tool = self.application_context.components.get(ComponentType.TOOL, "file_tool")
input_data = FileToolInput(operation="read", path=file_path)
result = await file_tool.execute(input_data)

# ✅ СТАЛО
result = await self.executor.execute_action(
    action_name="file_tool.read",
    parameters={"path": file_path},
    context=execution_context
)
content = result.data.get("content", "") if result.success else ""
```

```python
# ❌ БЫЛО (строки 510-527)
sql_tool = self.application_context.components.get(ComponentType.TOOL, "sql_tool")
input_data = SQLToolInput(sql=sql, parameters=None, max_rows=max_rows)
result = await sql_tool.execute(input_data)

# ✅ СТАЛО
result = await self.executor.execute_action(
    action_name="sql_tool.execute",
    parameters={
        "sql": sql,
        "parameters": None,
        "max_rows": max_rows
    },
    context=execution_context
)
rows = result.data.get("rows", []) if result.success else []
```

**Требуемые изменения в ActionExecutor:**

Добавить поддержку действий для tools в `_resolve_component_for_action`:

```python
# В метод _resolve_capability добавить поддержку tool действий
def _resolve_capability(self, action_name: str) -> Optional[Capability]:
    from core.models.data.capability import Capability
    
    # Для tool действий создаём capability на лету
    if action_name.startswith("file_tool."):
        return Capability(
            name=action_name,
            description=f"File operation: {action_name}",
            input_schema={"path": {"type": "string"}, "operation": {"type": "string"}},
            output_schema={"content": {"type": "string"}}
        )
    elif action_name.startswith("sql_tool."):
        return Capability(
            name=action_name,
            description=f"SQL operation: {action_name}",
            input_schema={"sql": {"type": "string"}, "max_rows": {"type": "integer"}},
            output_schema={"rows": {"type": "array"}, "columns": {"type": "array"}}
        )
    
    # ... остальная логика
```

---

### 1.3 Services: Прямые вызовы компонентов

#### Файл: `core/application/services/sql_query/service.py`

**Проблема:** Прямой вызов `sql_generation_service`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 255 | `sql_gen_service = components.get("sql_generation")` | `executor.execute_action("sql_generation.generate", ...)` |

**План исправления:**

```python
# ❌ БЫЛО (строка 255)
sql_gen_service = self._application_context.components.get(ComponentType.SERVICE, "sql_generation")
result = await sql_gen_service.execute_with_auto_correction(generation_input, context=None)

# ✅ СТАЛО
result = await self.executor.execute_action(
    action_name="sql_generation.generate_with_correction",
    parameters={
        "user_question": user_question,
        "tables": tables,
        "max_rows": max_rows,
        "context": f"Цель: выполнение безопасного SQL-запроса. Максимум {max_rows} строк."
    },
    context=execution_context
)
```

**Требуемые изменения в SQLGenerationService:**

Добавить поддержку вызова через executor:

```python
# В SQLGenerationService добавить execute_action метод
async def execute_action(self, capability: Capability, parameters: Dict[str, Any], context) -> ExecutionResult:
    if capability.name == "sql_generation.generate_with_correction":
        generation_input = SQLGenerationInput(
            user_question=parameters.get("user_question"),
            tables=parameters.get("tables"),
            max_rows=parameters.get("max_rows"),
            context=parameters.get("context")
        )
        return await self.execute_with_auto_correction(generation_input, context)
```

---

#### Файл: `core/application/services/sql_generation/service.py`

**Проблема:** Прямой вызов `table_description_service` и доступ к `event_bus`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 467 | `components.get("table_description_service")` | `executor.execute_action("table_description.get", ...)` |
| 515, 540, 567 | `event_bus.publish()` | `executor.execute_action("event.publish", ...)` |

---

### 1.4 Tools: Прямой доступ к инфраструктуре

#### Файл: `core/application/tools/sql_tool.py`

**Проблема:** Прямой вызов `db_provider.execute()`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 154-161 | `db_provider.execute(query=..., params=...)` | `executor.execute_action("db.execute", ...)` |

**План исправления:**

```python
# ❌ БЫЛО (строки 154-161)
result = await db_provider.execute(
    query=input_data.sql,
    params=input_data.parameters,
    max_rows=input_data.max_rows
)

# ✅ СТАЛО
db_result = await self.executor.execute_action(
    action_name="db.execute",
    parameters={
        "query": input_data.sql,
        "params": input_data.parameters,
        "max_rows": input_data.max_rows
    },
    context=execution_context
)
result = db_result.data if db_result.success else None
```

**Требуемые изменения в ActionExecutor:**

Добавить поддержку действий БД:

```python
# В execute_action добавить обработку "db.*"
if action_name.startswith("db."):
    return await self._execute_db_action(action_name, parameters, context)

async def _execute_db_action(self, action_name, parameters, context):
    # Получаем БД провайдер
    db_provider = self.application_context.infrastructure_context.get_provider("default_db")
    if not db_provider:
        return ActionResult(success=False, error="DB провайдер не найден")
    
    if action_name == "db.execute":
        result = await db_provider.execute(
            query=parameters.get("query"),
            params=parameters.get("params"),
            max_rows=parameters.get("max_rows", 1000)
        )
        return ActionResult(
            success=True,
            data={"rows": result.rows, "columns": result.columns, "rowcount": result.rowcount}
        )
```

---

#### Файл: `core/application/tools/file_tool.py`

**Проблема:** Прямой доступ к `infrastructure_context.config.data_dir`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 134 | `infrastructure_context.config.data_dir` | Параметр из `component_config` |

**План исправления:**

```python
# ❌ БЫЛО (строка 134)
data_dir = self.application_context.infrastructure_context.config.data_dir

# ✅ СТАЛО
data_dir = self.component_config.config.get("data_dir", "./data")
# Или через dependency injection в конструкторе
```

---

### 1.5 Agent Runtime: Прямой доступ к session_context

#### Файл: `core/application/agent/runtime.py`

**Проблема:** Прямой доступ к `session_context` и `components`

| Строки | Текущий код | Требуемое исправление |
|--------|-------------|----------------------|
| 405 | `components.get(comp_type, component_name)` | `executor.execute_action()` |
| 448 | `session_context.record_action()` | `executor.execute_action("context.record_action", ...)` |
| 473 | `session_context.record_observation()` | `executor.execute_action("context.record_observation", ...)` |
| 116, 163 | `infrastructure_context.*` | Через executor или dependency injection |

**План исправления:**

```python
# ❌ БЫЛО (строка 448)
action_id = self.application_context.session_context.record_action({...}, step_number=step)

# ✅ СТАЛО
action_result = await self.executor.execute_action(
    action_name="context.record_action",
    parameters={
        "action_data": {...},
        "step_number": step
    },
    context=execution_context
)
action_id = action_result.data.get("item_id") if action_result.success else None
```

```python
# ❌ БЫЛО (строка 473)
observation_id = self.application_context.session_context.record_observation({...})

# ✅ СТАЛО
obs_result = await self.executor.execute_action(
    action_name="context.record_observation",
    parameters={
        "observation_data": obs_data,
        "source": decision.capability_name,
        "step_number": step
    },
    context=execution_context
)
observation_id = obs_result.data.get("item_id") if obs_result.success else None
```

---

## 🟡 Фаза 2: Расширение ActionExecutor (Week 2)

### 2.1 Новые действия контекста

Добавить в `action_executor.py`:

```python
async def _execute_context_action(self, action_name, parameters, context):
    session_context = context.session_context
    
    # ... существующие действия
    
    # НОВЫЕ ДЕЙСТВИЯ
    elif action_name == "context.get_goal":
        return self._context_get_goal(parameters, session_context)
    elif action_name == "context.get_summary":
        return self._context_get_summary(parameters, session_context)
    elif action_name == "context.get_recent_errors":
        return self._context_get_recent_errors(parameters, session_context)
    elif action_name == "context.get_step":
        return self._context_get_step(parameters, session_context)
```

### 2.2 Новые действия для инструментов

```python
async def execute_action(self, action_name, parameters, context):
    # ... существующая логика
    
    # НОВЫЕ ДЕЙСТВИЯ ДЛЯ TOOLS
    if action_name.startswith("file_tool."):
        return await self._execute_file_tool_action(action_name, parameters, context)
    elif action_name.startswith("sql_tool."):
        return await self._execute_sql_tool_action(action_name, parameters, context)
    elif action_name.startswith("db."):
        return await self._execute_db_action(action_name, parameters, context)
```

### 2.3 Унификация интерфейса

**Проблема:** Два метода `execute_action()` и `execute_capability()`

**Решение:** Оставить только `execute()`:

```python
class ActionExecutor:
    async def execute(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ActionResult:
        """Единый метод для всех действий"""
        # ... логика
```

---

## 🟢 Фаза 3: Валидация и документация (Week 3)

### 3.1 Скрипт валидации

Создать `scripts/validation/check_executor_usage.py`:

```python
#!/usr/bin/env python3
"""
Проверка соблюдения изоляции компонентов.

НАРУШЕНИЯ:
1. Прямые вызовы components.get()
2. Прямой доступ к infrastructure_context.get_provider()
3. Прямой доступ к session_context.*
"""
import ast
import sys
from pathlib import Path

class ArchitectureViolationVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.violations = []
    
    def visit_Call(self, node):
        # Проверка components.get()
        if self._is_components_get_call(node):
            self.violations.append({
                'type': 'DIRECT_COMPONENT_CALL',
                'line': node.lineno,
                'code': ast.unparse(node)
            })
        
        # Проверка get_provider()
        if self._is_get_provider_call(node):
            self.violations.append({
                'type': 'DIRECT_INFRASTRUCTURE_ACCESS',
                'line': node.lineno,
                'code': ast.unparse(node)
            })
        
        # Проверка session_context.*
        if self._is_session_context_access(node):
            self.violations.append({
                'type': 'DIRECT_SESSION_CONTEXT_ACCESS',
                'line': node.lineno,
                'code': ast.unparse(node)
            })
        
        self.generic_visit(node)
    
    def _is_components_get_call(self, node):
        # Проверка на application_context.components.get(...)
        ...
    
    def _is_get_provider_call(self, node):
        # Проверка на infrastructure_context.get_provider(...)
        ...
    
    def _is_session_context_access(self, node):
        # Проверка на session_context.record_*, get_*, etc.
        ...

def check_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename=filepath)
    
    visitor = ArchitectureViolationVisitor(filepath)
    visitor.visit(tree)
    return visitor.violations

def main():
    core_dir = Path('core/application')
    all_violations = []
    
    for py_file in core_dir.rglob('*.py'):
        violations = check_file(py_file)
        if violations:
            all_violations.append({
                'file': str(py_file),
                'violations': violations
            })
    
    if all_violations:
        print("❌ НАЙДЕНЫ НАРУШЕНИЯ ИЗОЛЯЦИИ КОМПОНЕНТОВ\n")
        for item in all_violations:
            print(f"📁 {item['file']}")
            for v in item['violations']:
                print(f"   Строка {v['line']}: {v['type']}")
                print(f"   {v['code'][:100]}...")
        sys.exit(1)
    else:
        print("✅ Все компоненты соблюдают изоляцию")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

### 3.2 Интеграция в CI/CD

Добавить в `.github/workflows/ci.yml` или аналогичный:

```yaml
- name: Check component isolation
  run: python scripts/validation/check_executor_usage.py
```

### 3.3 Обновление документации

Создать `docs/ARCHITECTURE/COMPONENT_ISOLATION.md`:

```markdown
# Изоляция компонентов

## Принципы

1. **Все взаимодействия только через ActionExecutor**
2. **Нет прямых вызовов между компонентами**
3. **Нет прямого доступа к инфраструктуре**
4. **Нет прямой работы с session_context**

## Правильные паттерны

### LLM вызовы
```python
result = await self.executor.execute_action(
    action_name="llm.generate_structured",
    parameters={...},
    context=execution_context
)
```

### Работа с контекстом
```python
result = await self.executor.execute_action(
    action_name="context.record_plan",
    parameters={...},
    context=execution_context
)
```

### SQL запросы
```python
result = await self.executor.execute_action(
    action_name="sql_query.execute",
    parameters={...},
    context=execution_context
)
```

## Запрещённые паттерны

❌ Прямые вызовы компонентов
❌ Прямой доступ к инфраструктуре
❌ Прямая работа с session_context
```

---

## 📅 Дорожная карта

| Фаза | Задачи | Срок | Ответственные |
|------|--------|------|---------------|
| **Фаза 1** | Критические исправления | Week 1 | Core Team |
| 1.1 | Behaviors: session_context → executor | 2 дня | |
| 1.2 | Skills: component calls → executor | 2 дня | |
| 1.3 | Services: component calls → executor | 2 дня | |
| 1.4 | Tools: infrastructure → executor | 1 день | |
| 1.5 | Runtime: session_context → executor | 1 день | |
| **Фаза 2** | Расширение ActionExecutor | Week 2 | Core Team |
| 2.1 | Новые действия контекста | 1 день | |
| 2.2 | Новые действия для tools | 2 дня | |
| 2.3 | Унификация интерфейса | 2 дня | |
| **Фаза 3** | Валидация и документация | Week 3 | QA Team |
| 3.1 | Скрипт валидации | 2 дня | |
| 3.2 | Интеграция в CI/CD | 1 день | |
| 3.3 | Документация | 2 дня | |

---

## ✅ Критерии приёмки

### Фаза 1
- [ ] Все файлы из раздела 1.1-1.5 исправлены
- [ ] Тесты проходят
- [ ] Нет регрессий в функциональности

### Фаза 2
- [ ] ActionExecutor поддерживает все новые действия
- [ ] Интерфейс унифицирован
- [ ] Обновлены тесты для ActionExecutor

### Фаза 3
- [ ] Скрипт валидации обнаруживает нарушения
- [ ] Валидация интегрирована в CI/CD
- [ ] Документация обновлена

---

## 📊 Ожидаемые результаты

| Метрика | До | После |
|---------|-----|-------|
| Соблюдение изоляции | 20% | 95%+ |
| Прямых вызовов компонентов | 10 | 0 |
| Прямых доступов к инфраструктуре | 19 | 0 |
| Прямых доступов к session_context | 48 | 0 |

---

## ⚠️ Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Регрессии в функциональности | Средняя | Высокое | Покрытие тестами, постепенное внедрение |
| Производительность executor | Низкая | Среднее | Кэширование, оптимизация |
| Сопротивление команды | Низкая | Низкое | Обучение, документация |

---

## 📝 Приложения

### A. Список файлов для исправления

#### Behaviors (4 файла)
- `core/application/behaviors/react/pattern.py`
- `core/application/behaviors/planning/pattern.py`
- `core/application/behaviors/evaluation/pattern.py`
- `core/application/behaviors/fallback/pattern.py`

#### Skills (1 файл)
- `core/application/skills/data_analysis/skill.py`

#### Services (3 файла)
- `core/application/services/sql_query/service.py`
- `core/application/services/sql_generation/service.py`
- `core/application/services/table_description_service.py`

#### Tools (2 файла)
- `core/application/tools/sql_tool.py`
- `core/application/tools/file_tool.py`

#### Agent (1 файл)
- `core/application/agent/runtime.py`

### B. Примеры правильных паттернов

См. файлы:
- `core/application/skills/planning/skill.py` (строки 200-260)
- `core/application/skills/final_answer/skill.py` (строки 206-252)
- `core/application/services/prompt_service.py` (внедрение зависимостей)

---

**Документ утверждён:** [Ожидает подтверждения]  
**Следующий пересмотр:** После завершения Фазы 1

# 📝 Руководство по разработке нового навыка (Skill)

> **Версия проекта:** 5.46.8
> **Статус:** Active
> **Дата создания:** 2026-05-05

---

## 📋 Содержание

1. [Из чего состоит навык](#из-чего-состоит-навык)
2. [Иерархия базовых классов](#иерархия-базовых-классов)
3. [Что даёт базовый класс](#что-даёт-базовый-класс)
4. [Что нужно реализовать самостоятельно](#что-нужно-реализовать-самостоятельно)
5. [Обязательные компоненты](#обязательные-компоненты)
6. [Пошаговый процесс разработки](#пошаговый-процесс-разработки)
7. [Минимальный пример навыка](#минимальный-пример-навыка)
8. [Чеклист перед коммитом](#чеклист-перед-коммитом)

---

## 🏗️ Из чего состоит навык (Skill)

Навык (Skill) — это компонент, отвечающий за **логику принятия решений** («как думать и что делать»). Один навык может предоставлять несколько возможностей (`Capability`).

### Структура файлов навыка

```
core/components/skills/my_skill/
├── skill.py              # Основной класс навыка (наследник Skill)
├── handlers/             # Обработчики для каждой capability (опционально)
│   ├── __init__.py
│   └── some_handler.py
├── __init__.py
└── utils/               # Вспомогательные утилиты (опционально)
```

### Ресурсы навыка (в `data/`)

```
data/
├── prompts/skill/my_skill/
│   ├── my_skill.do_something.system_v1.0.0.yaml
│   └── my_skill.do_something.user_v1.0.0.yaml
└── contracts/skill/my_skill/
    ├── my_skill.do_something_input_v1.0.0.yaml
    └── my_skill.do_something_output_v1.0.0.yaml
```

---

## 🧬 Иерархия базовых классов

```
Component (core/components/component.py)
    └── Skill (core/components/skills/skill.py)
            └── Ваш навык (MySkill)
```

### Что даёт `Component` (через `Skill`):

| Что получаете | Как использовать | Описание |
|---------------|------------------|-----------|
| **Логирование** | `self.log.info(msg, extra={"event_type": LogEventType.XXX})` | Стандартный `logging`, автоматически пишет в файл + терминал |
| **Executor** | `self.executor.execute_action(...)` | Единственный способ взаимодействия с другими компонентами |
| **Промпты** | `self.prompts`, `self.get_prompt(name)` | Загружены автоматически при инициализации |
| **Контракты** | `self.input_contracts`, `self.output_contracts` | Валидация входа/выхода через YAML-схемы |
| **Жизненный цикл** | `initialize()`, `shutdown()` | Состояния: CREATED → INITIALIZING → READY → SHUTDOWN |
| **Валидация** | `validate_input_typed()`, `validate_output_typed()` | Автоматически в `execute()` |

---

## ✍️ Что нужно реализовать самостоятельно

### 1. Объявление capability (`get_capabilities`)

```python
def get_capabilities(self) -> List[Capability]:
    return [
        Capability(
            name="my_skill.do_something",
            description="Описание того, что делает эта capability",
            skill_name=self.name,
            supported_strategies=["react", "planning"],  # Или конкретные
            visible=True,  # Видна ли в списке доступных
            meta={
                "requires_llm": True,  # Нужен ли LLM
                "execution_type": "llm-powered",
                "formats": ["detailed"]  # Специфичные метаданные
            }
        )
    ]
```

### 2. Бизнес-логика (`_execute_impl`)

```python
async def _execute_impl(
    self,
    capability: Capability,
    parameters: Dict[str, Any],  # Уже валидированы через Pydantic!
    execution_context: ExecutionContext
) -> Dict[str, Any]:  # ❗ Возвращаем ДАННЫЕ, не ExecutionResult!
    
    # 1. Проверка capability
    if capability.name != "my_skill.do_something":
        raise ValueError(f"Неподдерживаемая capability: {capability.name}")
    
    # 2. Извлечение параметров (уже валидированы!)
    query = parameters.get("query")
    
    # 3. Взаимодействие через executor
    result = await self.executor.execute_action(
        action_name="sql_tool.execute",
        parameters={"query": query},
        context=execution_context
    )
    
    # 4. Возврат данных
    return {"result": result.data.get("rows", [])}
```

### 3. Инициализация (опционально)

```python
async def initialize(self) -> bool:
    # 1. ВЫЗЫВАЙТЕ super() в начале!
    success = await super().initialize()
    if not success:
        return False
    
    # 2. Проверка ресурсов (если требуются)
    capability_name = "my_skill.do_something"
    if capability_name not in self.prompts:
        self.log.error(f"Промпт {capability_name} не загружен")
        return False
    
    # 3. Логирование
    self.log.info(f"{self.name} инициализирован", extra={"event_type": LogEventType.SYSTEM_INIT})
    return True
```

---

## ⚙️ Обязательные компоненты

### ✅ Код навыка
- Наследование от `Skill` (или `BaseSkill` для старых версий)
- Реализация `get_capabilities()`
- Реализация `_execute_impl()`
- Аннотации типов на все методы

### ✅ YAML контракты (в `data/contracts/skill/my_skill/`)
- **Input контракт**: валидация входных параметров
- **Output контракт**: валидация выходных данных
- Статус: `status: active` (или `draft` для sandbox)

Пример input контракта:
```yaml
capability: my_skill.do_something
version: v1.0.0
status: active
component_type: skill
direction: input
schema_data:
  type: object
  properties:
    query:
      type: string
      description: Поисковый запрос
    max_results:
      type: integer
      default: 10
  required:
    - query
  additionalProperties: false
```

### ✅ Промпты (в `data/prompts/skill/my_skill/`)
- Системный промпт: `my_skill.do_something.system_v1.0.0.yaml`
- Пользовательский промпт: `my_skill.do_something.user_v1.0.0.yaml`
- Или совмещённый: `my_skill.do_something.v1.0.0.yaml`

### ✅ Логирование
- Через `self.log` + `extra={"event_type": LogEventType.XXX}`
- Никаких `print()` или `EventBusLogger`

### ✅ Взаимодействие
- ТОЛЬКО через `self.executor.execute_action()`
- Никакого прямого доступа к другим компонентам

---

## 🚀 Пошаговый процесс разработки

1. **Создайте структуру папок**
   ```
   core/components/skills/my_skill/
   data/prompts/skill/my_skill/
   data/contracts/skill/my_skill/
   ```

2. **Опишите контракты** (input/output YAML)

3. **Напишите промпты** (если нужен LLM)

4. **Реализуйте класс навыка** (skill.py)

5. **Зарегистрируйте зависимости**
   ```python
   DEPENDENCIES = ["sql_tool", "prompt_service"]
   ```

6. **Напишите тесты**
   ```bash
   python -m pytest tests/unit/test_my_skill.py -v
   ```

7. **Проверьте архитектуру**
   ```bash
   python scripts/validation/check_skill_architecture.py
   python scripts/validation/check_yaml_syntax.py
   ```

---

## 📝 Минимальный пример навыка

```python
# core/components/skills/my_skill/skill.py
import asyncio
from typing import Dict, Any, List

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.infrastructure.logging.event_types import LogEventType


class MySkill(Skill):
    """Навык для выполнения чего-то."""

    @property
    def description(self) -> str:
        return "Описание навыка"

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="my_skill.do_something",
                description="Делает что-то полезное",
                skill_name=self.name,
                supported_strategies=["react"],
                visible=True,
                meta={"requires_llm": False}
            )
        ]

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        # Ваша логика здесь
        self.log.info("Выполнение навыка", extra={"event_type": LogEventType.TOOL_CALL})
        return {"result": "done"}
```

---

## ✅ Чеклист перед коммитом

- [ ] Наследуется от `Skill` (или `BaseSkill`)
- [ ] `get_capabilities()` реализован
- [ ] `_execute_impl()` возвращает `Dict[str, Any]` (не `ExecutionResult`)
- [ ] Взаимодействие только через `ActionExecutor`
- [ ] Логирование через `self.log` + `LogEventType`
- [ ] Есть input/output контракты в `data/contracts/`
- [ ] Есть промпты в `data/prompts/` (если используется LLM)
- [ ] `check_skill_architecture.py` пройден
- [ ] Тесты написаны и проходят

---

> **Помни:** Цель этих требований — не ограничить творчество, а обеспечить согласованность архитектуры.

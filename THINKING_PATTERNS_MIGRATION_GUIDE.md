# Перенос паттернов мышления в PromptRepository

## Обзор

Все паттерны мышления, ранее использовавшиеся агентами и навыками, теперь хранятся в едином PromptRepository. Это позволяет:

- Централизованно управлять всеми паттернами мышления
- Обеспечивать версионность паттернов
- Внедрить строгую валидацию переменных
- Обеспечить полную видимость выполнения через снапшоты
- Защитить от деградации поведения

## Перенесенные паттерны мышления

### 1. ReAct Pattern (Reasoning and Acting)

**Файл:** `prompts/thinking_react_pattern.md`
**Capability:** `thinking.react`
**Описание:** Паттерн чередования рассуждения и действия

**Структура:**
- ID: `thinking_react_pattern_v1`
- Домен: `reasoning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `task` (обязательная): Задача, которую нужно решить
- `context` (опциональная): Контекст задачи
- `available_tools` (опциональная): Доступные инструменты для использования
- `previous_steps` (опциональная): Предыдущие шаги выполнения

**Ожидаемая схема ответа:**
```json
{
  "thought": "Рассуждение о следующем шаге",
  "action": "Название действия или инструмента",
  "action_input": "Входные данные для действия"
}
```

### 2. PlanAndExecute Pattern

**Файл:** `prompts/thinking_plan_and_execute_pattern.md`
**Capability:** `thinking.plan_and_execute`
**Описание:** Паттерн сначала планирования, затем выполнения

**Структура:**
- ID: `thinking_plan_and_execute_pattern_v1`
- Домен: `reasoning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `task` (обязательная): Задача, которую нужно решить
- `context` (опциональная): Контекст задачи
- `available_tools` (опциональная): Доступные инструменты для использования

**Ожидаемая схема ответа:**
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Описание шага",
      "action": "Название действия или инструмента",
      "action_input": "Входные данные для действия"
    }
  ],
  "execution_results": [
    {
      "step_number": 1,
      "result": "Результат выполнения шага"
    }
  ]
}
```

### 3. Reflection Pattern

**Файл:** `prompts/thinking_reflection_pattern.md`
**Capability:** `thinking.reflection`
**Описание:** Паттерн выполнения с рефлексией и самоанализом

**Структура:**
- ID: `thinking_reflection_pattern_v1`
- Домен: `reasoning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `task` (обязательная): Задача, которую нужно решить
- `context` (опциональная): Контекст задачи
- `current_solution` (опциональная): Текущее решение или подход
- `feedback` (опциональная): Обратная связь или ошибки

**Ожидаемая схема ответа:**
```json
{
  "reflection": "Размышления о текущем решении",
  "critique": "Критика текущего подхода",
  "improved_solution": "Улучшенное решение",
  "reasoning_trace": [
    "Шаг 1 рассуждения",
    "Шаг 2 рассуждения"
  ]
}
```

### 4. Chain of Thought Pattern

**Файл:** `prompts/thinking_chain_of_thought_pattern.md`
**Capability:** `thinking.chain_of_thought`
**Описание:** Паттерн цепочки рассуждений

**Структура:**
- ID: `thinking_chain_of_thought_pattern_v1`
- Домен: `reasoning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `task` (обязательная): Задача, которую нужно решить
- `context` (опциональная): Контекст задачи
- `examples` (опциональная): Примеры решения подобных задач

**Ожидаемая схема ответа:**
```json
{
  "reasoning_steps": [
    "Шаг 1 рассуждения",
    "Шаг 2 рассуждения"
  ],
  "final_answer": "Окончательный ответ на задачу"
}
```

## Использование в агентах и навыках

Теперь агенты и навыки получают паттерны мышления из PromptRepository через Capability:

```python
from application.services.prompt_renderer import PromptRenderer
from domain.value_objects.provider_type import LLMProviderType

# Создаем рендерер с репозиторием
renderer = PromptRenderer(prompt_repository, snapshot_manager)

# Определяем capability с указанием версий промтов
capability = Capability(
    name="thinking.react",
    description="Паттерн ReAct (Reasoning and Acting)",
    skill_name="reasoning_skill",
    prompt_versions={
        "openai:system": "thinking_react_pattern_v1"  # ID версии промта
    }
)

# Рендерим промт с валидацией переменных
rendered_prompts, snapshot, errors = await renderer.render_and_create_snapshot(
    capability=capability,
    provider_type=LLMProviderType.OPENAI,
    template_context={
        "task": "Решить математическую задачу",
        "context": "Необходимо использовать инструмент калькулятора",
        "available_tools": "calculator, search"
    },
    session_id="session_123"
)
```

## Структура файлов паттернов мышления

Все паттерны мышления хранятся в формате Markdown с frontmatter:

```yaml
---
id: уникальный_id_паттерна
semantic_version: "1.0.0"
domain: "reasoning"
provider_type: "openai"
capability_name: "thinking.название_паттерна"
role: "system"
status: "active"  # draft, active, shadow, deprecated, archived
variables_schema:
  - name: "имя_переменной"
    type: "string"  # string, integer, boolean, array, object
    required: true
    description: "Описание переменной"
    default_value: "значение_по_умолчанию"
expected_response_schema:
  type: "object"
  properties:
    ...
---
Содержимое промта с переменными в формате {{variable_name}}
```

## Преимущества

1. **Централизованное управление:** Все паттерны мышления в одном месте
2. **Версионность:** Возможность откатов и отслеживания изменений
3. **Метрики:** Отслеживание эффективности паттернов
4. **Безопасность:** Защита от инъекций в шаблонах
5. **Аудит:** Полная история использования паттернов
6. **Гибкость:** Поддержка разных провайдеров и ролей
7. **Валидация:** Строгая проверка переменных перед вызовом LLM
8. **Адаптивность:** Возможность тонкой настройки под разные задачи
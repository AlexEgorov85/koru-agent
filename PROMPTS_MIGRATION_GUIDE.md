# Перенос промтов в PromptRepository

## Обзор

Все промты, ранее использовавшиеся агентами и навыками, теперь хранятся в едином PromptRepository. Это позволяет:

- Централизованно управлять всеми промтами
- Обеспечивать версионность промтов
- Внедрить строгую валидацию переменных
- Обеспечить полную видимость выполнения через снапшоты
- Защитить от деградации поведения

## Перенесенные промты

### 1. LLM Decision Prompt

**Файл:** `prompts/llm_decision_prompt.md`
**Capability:** `llm_decision`
**Описание:** Промт для принятия решений LLM

**Структура:**
- ID: `llm_decision_prompt_v1`
- Домен: `problem_solving`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `goal` (обязательная): Цель, которую нужно достичь
- `tools` (обязательная): Доступные инструменты для выполнения задачи
- `last_steps_summary` (опциональная): Резюме предыдущих шагов

### 2. Planning Plan Generation Prompt

**Файл:** `prompts/planning_plan_generation_prompt.md`
**Capability:** `planning.plan_generation`
**Описание:** Промт для генерации плана реализации требований

**Структура:**
- ID: `planning_plan_generation_prompt_v1`
- Домен: `planning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `requirements` (обязательная): Требования для реализации
- `project_context` (обязательная): Контекст проекта
- `constraints` (опциональная): Ограничения проекта
- `priority` (опциональная): Приоритет задач
- `estimated_effort_hours` (опциональная): Оценка трудозатрат в часах

### 3. Planning Code Generation Prompt

**Файл:** `prompts/planning_code_generation_prompt.md`
**Capability:** `planning.code_generation`
**Описание:** Промт для генерации кода

**Структура:**
- ID: `planning_code_generation_prompt_v1`
- Домен: `planning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `requirements` (обязательная): Требования для генерации кода
- `target_language` (обязательная): Целевой язык программирования
- `target_framework` (опциональная): Целевая технология/фреймворк
- `existing_code_context` (опциональная): Контекст существующего кода
- `style_guidelines` (опциональная): Руководства по стилю
- `security_requirements` (опциональная): Требования безопасности

### 4. Planning Task Breakdown Prompt

**Файл:** `prompts/planning_task_breakdown_prompt.md`
**Capability:** `planning.task_breakdown`
**Описание:** Промт для разбиения задач на подзадачи

**Структура:**
- ID: `planning_task_breakdown_prompt_v1`
- Домен: `planning`
- Провайдер: `openai`
- Роль: `system`
- Статус: `active`

**Переменные:**
- `task_description` (обязательная): Описание задачи для разбиения
- `project_context` (обязательная): Контекст проекта
- `required_skills` (опциональная): Необходимые навыки
- `time_constraints` (опциональная): Временные ограничения

## Паттерны мышления

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

## Структура файлов промтов

Все промты хранятся в формате Markdown с frontmatter:

```yaml
---
id: уникальный_id_промта
semantic_version: "1.0.0"
domain: "домен_приложения"
provider_type: "типы_провайдера"
capability_name: "имя_capability"
role: "system"  # или "user", "assistant"
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

## Использование в агентах и навыках

Теперь агенты и навыки получают промты из PromptRepository через Capability:

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

## Инициализация системы

При старте системы все промты из директории `./prompts` автоматически синхронизируются в репозиторий:

```python
from application.services.prompt_system_initializer import PromptSystemInitializer

initializer = PromptSystemInitializer(db_provider, fs_directory="./prompts")
prompt_repository = await initializer.initialize()
```

## Контроль качества

- Все промты проходят валидацию переменных перед использованием
- Все вызовы промтов логируются в снапшоты
- Поддерживаются метрики использования и производительности
- Реализован полный жизненный цикл промтов

## Преимущества

1. **Централизованное управление:** Все промты в одном месте
2. **Версионность:** Возможность откатов и отслеживания изменений
3. **Метрики:** Отслеживание эффективности промтов
4. **Безопасность:** Защита от инъекций в шаблонах
5. **Аудит:** Полная история использования промтов
6. **Гибкость:** Поддержка разных провайдеров и ролей
7. **Валидация:** Строгая проверка переменных перед вызовом LLM
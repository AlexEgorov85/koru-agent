# Структура хранения промтов

## Обзор

Эта директория содержит все промты, используемые системой, организованные по доменам и возможностям.

## Структура файлов

```
prompts/
├── _registry.yaml          # Глобальный реестр доменов и возможностей
├── {domain}/               # Домен (например, problem_solving, code_generation)
│   └── {capability}/       # Возможность (например, llm_decision, planning)
│       ├── _index.yaml     # Индекс всех версий для этой возможности
│       ├── {role}/         # Роль (system, user, assistant, tool)
│       │   └── v{version}.md  # Файл промта с метаданными
│       └── ...
```

### Пример структуры:
```
prompts/
├── _registry.yaml
├── problem_solving/
│   └── llm_decision/
│       ├── _index.yaml
│       ├── system/
│       │   └── v1.0.0.md
│       └── user/
│           └── v1.0.0.md
```

## Формат файла промта

Каждый файл промта использует формат Markdown с YAML frontmatter:

```yaml
---
role: "system"
status: "active"
provider: "openai"
variables:
  - name: "goal"
    type: "string"
    required: true
    description: "Цель, которую нужно достичь"
expected_response:
  format: "json"
  schema:
    type: "object"
    # ...
---
Содержимое промта с переменными в формате {{variable_name}}
```

## Роли промтов

- `system`: Системные промты для настройки поведения LLM
- `user`: Пользовательские промты для запросов к LLM
- `assistant`: Промты для модели ассистента
- `tool`: Промты для инструментов и утилит

## Версионирование

Файлы промтов следуют семантическому версионированию (vX.Y.Z):
- X: Мажорные изменения, нарушающие обратную совместимость
- Y: Минорные изменения, добавляющие новую функциональность
- Z: Патчи, исправляющие ошибки

## Индексные файлы

Каждая capability содержит `_index.yaml` файл с информацией о доступных версиях:

```yaml
capability:
  description: Описание возможности
  domain: домен
  latest_active_version: 1.0.0
  name: имя_возможности
versions:
  1.0.0:
    path: ./system/v1.0.0.md
    provider: openai
    role: system
    status: active
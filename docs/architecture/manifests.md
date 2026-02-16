# Манифесты Компонентов

## Обзор

Манифесты компонентов предоставляют единую точку истины для метаданных всех компонентов системы.

## Структура манифеста

```yaml
component_id: planning
component_type: skill
version: v1.0.0
owner: team-planning
status: active

contract:
  input: planning.create_plan.input.v1.0.0
  output: planning.create_plan.output.v1.0.0

constraints:
  max_steps: 15
  timeout_seconds: 300

quality_metrics:
  success_rate_target: 0.95
  avg_execution_time_ms: 500
  error_rate_threshold: 0.05

dependencies:
  components: []
  tools:
    - sql_tool
  services:
    - prompt_service

changelog:
  - version: v1.0.0
    date: "2026-02-16"
    author: alexey
    changes:
      - "Initial release"
```

## Статусы компонентов

| Статус | Описание | Prod | Sandbox |
|--------|----------|------|---------|
| `draft` | Черновик | ❌ | ✅ |
| `active` | Активная версия | ✅ | ✅ |
| `deprecated` | Устаревает | ⚠️ | ✅ |
| `archived` | Архивирован | ❌ | ❌ |

## Расположение файлов

```
data/manifests/
├── skills/
├── tools/
├── services/
└── behaviors/
```
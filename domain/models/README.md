# Модели доменного слоя

## Структура
Все файлы в этой директории содержат **только модели данных** (DTO, Pydantic модели, dataclasses, перечисления), без бизнес-логики.

### `agent/` — Модели состояния агента
- `agent_state.py` — состояние агента
- `agent_runtime_state.py` — состояние выполнения агента
- `progress.py` — прогресс выполнения

### `session/` — Модели сессии
- `agent_step.py` — шаг агента
- `context_item.py` — элемент контекста

### `execution/` — Модели выполнения
- `execution_result.py` — результат выполнения
- `execution_status.py` — статус выполнения

### `prompt/` — Модели версионности промтов (ЯДРО СИСТЕМЫ)
- `prompt_version.py` — версия промта
- `prompt_execution_snapshot.py` — снапшот выполнения промта

### `benchmark/` — Модели оценки качества (ЯДРО СИСТЕМЫ)
- `benchmark_question.py` — вопрос бенчмарка
- `benchmark_result.py` — результат бенчмарка
- `benchmark_session.py` — сессия бенчмарка
- `solution_algorithm.py` — алгоритм решения
- `solution_step.py` — шаг решения

### `system/` — Системные модели
- `config.py` — конфигурация системы
- `capability.py` — capability системы
- `skill_metadata.py` — метаданные навыков
- `tool_metadata.py` — метаданные инструментов

### `react/` — Модели ReAct паттерна
- `react_state.py` — состояние ReAct
- `react_responses.py` — ответы ReAct

### Корневые файлы
- `domain_type.py` — перечисления типов доменов
- `provider_type.py` — перечисления типов провайдеров
- `resource.py` — модель ресурса
- `capability.py` — модель capability
- `composable_pattern_state.py` — состояние компонуемого паттерна
- `thinking_pattern_result.py` — результат паттерна мышления
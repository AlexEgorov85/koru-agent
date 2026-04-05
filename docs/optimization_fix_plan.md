# План доработки сервиса оптимизации промптов

> **Дата:** 2026-04-05
> **Статус:** В работе (Этап 1 — в процессе)
> **Цель:** Сделать сервис оптимизации рабочим — от анализа traces до реального улучшения промптов

---

## Выполнено (Этап 1) ✅

| # | Что сделано | Файл | Статус |
|---|-------------|------|--------|
| 1 | Добавлен метод `apply_prompt_content_override()` в ApplicationContext | `application_context.py` | ✅ Работает |
| 2 | Определение метода skill для оптимизации (system промпт) | `run_optimization.py` | ✅ Работает |
| 3 | Исправлен `executor_callback` — использует `get_version(capability, version_id)` | `run_optimization.py` | ✅ Работает |
| 4 | Исправлен вызов `version_manager.promote(baseline_version.id, baseline_prompt_capability)` | `run_optimization.py` | ✅ Работает |
| 5 | `orchestrator.optimize()` вызывается с `baseline_prompt_capability` | `run_optimization.py` | ✅ Работает |

### Что было сложного:
- `Prompt` имеет `frozen=True` → нельзя изменить напрямую → использую `model_copy(update={...})`
- `VersionManager.get_version()` требует `capability` + `version_id`
- Sandbox создаётся один раз, но кандидаты оцениваются много раз → нужен `apply_prompt_content_override()`

### Текущее поведение:
1. Загружается `book_library.search_books.system` как baseline (реальный промпт)
2. Генерируется 6 кандидатов с улучшениями
3. Каждый кандидат оценивается через `executor_callback`
4. `executor_callback` вызывает `apply_prompt_content_override()` → обновляет промпт в компоненте
5. Агент запускается с обновлённым промптом

### Что НЕ работает:
- Оценка занимает слишком много времени (timeout)
- Root causes все ещё "Отсутствие обработки ошибок" (нужен Этап 2)
- Примеры = 0 (нужен Этап 3)

---

## Текущее состояние

### Что работает ✅
| Компонент | Статус | Примечание |
|-----------|--------|------------|
| Сбор traces из session.jsonl | ✅ | Fallback реализован, находит 37+ traces |
| Анализ паттернов | ✅ | PatternAnalyzer находит 7 паттернов |
| Root cause анализ | ✅ | RootCauseAnalyzer находит 6 root causes |
| Генерация кандидатов | ✅ | 6 кандидатов из 6 групп root causes |
| Загрузка benchmark сценариев | ✅ | 7 реальных вопросов из agent_benchmark.json |
| Оценка baseline | ✅ | score ≈ 0.2 |
| Оценка кандидатов | ✅ | score ≈ 0.2 |
| LifecycleManager cleanup | ✅ | clear_resources() после shutdown |
| LLMRequest/LLMResponse.to_dict | ✅ | Сериализация для trace to_dict |
| **apply_prompt_content_override** | ✅ | Обновляет промпт в компонентах |
| **Оптимизация на уровне методов** | ✅ | baseline = book_library.search_books.system |

### Что НЕ работает ❌
| Компонент | Проблема | Причина | Этап |
|-----------|----------|---------|------|
| **Улучшение = 0** | Все кандидаты имеют score ≈ baseline | Оценка занимает слишком долго, возможно промпт не применяется | 1, 4 |
| **Root causes одинаковые** | Все 6 — "Отсутствие обработки ошибок" | RootCauseAnalyzer не различает проблемы | 2 |
| **Примеры = 0/0** | Good и error examples не извлекаются | Слишком строгие критерии | 3 |
| **Timeout при оценке** | Benchmark занимает слишком долго | Нужно оптимизировать или уменьшить benchmark | 4 |

---

## Этап 1: Исправить архитектуру — оптимизация на уровне методов skill ✅ (в процессе)

### Проблема
Сейчас `capability = "book_library"` → создаётся один `PromptVersion` с content = `"Default prompt for book_library_baseline" + "# IMPROVEMENT..."`. Но skill `book_library` использует промпты на уровне методов:
- `book_library.search_books.system@v1.0.0`
- `book_library.execute_script@v1.1.0`
- `book_library.semantic_search@v1.0.0`

Изменение промпта `book_library` не влияет на поведение агента.

### Решение
Оптимизировать промпты на уровне **методов skill**, а не всей capability.

### 1.1. Определить методы skill для оптимизации

**Файлы:**
- `scripts/cli/run_optimization.py` — CLI entry point
- `core/services/skills/book_library/` — skill с методами

**Задачи:**
1. При запуске `--capability book_library` определить все методы skill:
   - Загрузить skill из ApplicationContext
   - Получить список методов (capabilities): `search_books`, `execute_script`, `semantic_search`
2. Для каждого метода найти active промпт через `PromptService`:
   - `book_library.search_books.system@v1.0.0`
   - `book_library.execute_script@v1.1.0`
3. Создать `PromptVersion` для каждого метода с реальным content промпта

**Критерии приемки:**
- [ ] При запуске `--capability book_library` выводятся все методы skill
- [ ] Для каждого метода загружается реальный промпт (не заглушка)
- [ ] `baseline_version.prompt` содержит реальный текст промпта из YAML файла

**Перепроверка:**
```bash
# Запустить с debug выводом
python scripts/cli/run_optimization.py -c book_library --benchmark-size 2 --verbose 2>&1 | Select-String -Pattern "baseline|prompt|method"
# Ожидание: baseline_version.prompt содержит реальный текст промпта (>100 символов)
```

### 1.2. Исправить executor_callback

**Файлы:**
- `scripts/cli/run_optimization.py` — `executor_callback` (строка 724)
- `core/application_context/application_context.py` — `_prompt_overrides`

**Задачи:**
1. `executor_callback` должен обновлять `_prompt_overrides` для конкретного метода, а не всей capability:
   ```python
   # БЫЛО:
   sandbox_for_callback._prompt_overrides = {capability: candidate.prompt}
   
   # СТАЛО:
   sandbox_for_callback._prompt_overrides = {method_key: candidate.prompt}
   # где method_key = "book_library.search_books.system"
   ```
2. Убедиться что `PromptService` проверяет `_prompt_overrides` при загрузке промпта
3. Каждый кандидат должен быть привязан к конкретному методу

**Критерии приемки:**
- [ ] `executor_callback` обновляет `_prompt_overrides` с ключом метода (не capability)
- [ ] При запуске агента с кандидатом используется изменённый промпт метода
- [ ] Лог показывает какой промпт используется

**Перепроверка:**
```bash
# Проверить что промпт кандидата отличается от baseline
python scripts/cli/run_optimization.py -c book_library --benchmark-size 2 --dry-run --verbose
# Ожидание: в логе видно что промпт метода изменён
```

### 1.3. Исправить генерацию кандидатов

**Файлы:**
- `core/agent/components/optimization/prompt_generator.py` — `generate_improvements`
- `scripts/cli/run_optimization.py` — создание baseline

**Задачи:**
1. `generate_improvements` должен принимать `original_prompt` с реальным content метода
2. Кандидаты должны модифицировать реальный промпт, а не заглушку
3. Root causes должны быть привязаны к конкретным методам (уже есть в `affected_capabilities`)

**Критерии приемки:**
- [ ] Каждый кандидат содержит baseline промпт метода + улучшения
- [ ] Длина candidate.prompt > length baseline.prompt (улучшения добавлены)
- [ ] Кандидаты для разных методов имеют разные baseline промпты

**Перепроверка:**
```python
# В debug режиме проверить:
print(f"Baseline prompt length: {len(baseline.prompt)}")
print(f"Candidate prompt length: {len(candidate.prompt)}")
# Ожидание: baseline > 100 символов, candidate > baseline
```

---

## Этап 2: Улучшить Root Cause Analyzer

### Проблема
Все 6 root causes одинаковые: "Отсутствие обработки ошибок в промпте" / "Отсутствие обработки ошибок". Различаются только `affected_capabilities`. Это даёт 6 кандидатов с одинаковыми улучшениями.

### 2.1. Расширить cause_matrix

**Файлы:**
- `core/agent/components/optimization/root_cause_analyzer.py` — `cause_matrix`

**Задачи:**
1. Добавить больше типов причин в `cause_matrix`:
   - `missing_schema` — отсутствие описания выходного формата
   - `missing_tool_guidance` — отсутствие правил выбора инструментов
   - `missing_context_handling` — отсутствие инструкций по работе с контекстом
   - `missing_fallback` — отсутствие fallback стратегий
2. Связать паттерны с более специфичными причинами
3. Добавить причины на основе анализа response_issues (не только prompt_issues)

**Критерии приемки:**
- [ ] При тех же traces root causes имеют разные `cause` тексты
- [ ] Минимум 3 уникальных `cause` значения среди root causes
- [ ] Каждый root cause имеет уникальный `fix` текст

**Перепроверка:**
```bash
python debug_rc.py  # или аналогичный скрипт
# Ожидание: root causes имеют разные cause и fix значения
```

### 2.2. Добавить анализ успешных traces

**Файлы:**
- `core/agent/components/optimization/root_cause_analyzer.py`

**Задачи:**
1. Сравнить успешные и неуспешные traces
2. Найти различия в паттернах выполнения
3. Сгенерировать root causes на основе различий

**Критерии приемки:**
- [ ] Root causes включают различия между success/failure traces
- [ ] Есть root causes типа "В успешных traces используется X, в неуспешных — Y"

---

## Этап 3: Исправить извлечение примеров

### Проблема
`ExampleExtractor` возвращает 0 good и 0 bad примеров из-за строгих критериев:
- `max_steps = 5` — большинство traces имеют > 5 шагов
- `max_time_ms = 5000` — LLM вызовы занимают > 5 сек

### 3.1. Ослабить критерии

**Файлы:**
- `core/agent/components/optimization/example_extractor.py` — `__init__`, `extract_good_examples`

**Задачи:**
1. Увеличить `max_steps` с 5 до 15
2. Увеличить `max_time_ms` с 5000 до 60000 (60 сек — типичное время LLM)
3. Добавить критерий `has_final_answer` вместо `trace.final_answer is not None`
4. Логировать почему примеры отклоняются

**Критерии приемки:**
- [ ] `extract_good_examples` возвращает > 0 примеров
- [ ] `extract_error_examples` возвращает > 0 примеров
- [ ] В логе видно сколько примеров отклонено и почему

**Перепроверка:**
```bash
python scripts/cli/run_optimization.py -c book_library --benchmark-size 2 --verbose 2>&1 | Select-String -Pattern "Примеров|examples"
# Ожидание: Примеров: X good, Y bad (где X > 0 или Y > 0)
```

### 3.2. Использовать примеры в генерации кандидатов

**Файлы:**
- `core/agent/components/optimization/prompt_generator.py` — `_generate_from_examples`

**Задачи:**
1. Если есть good_examples, добавить их как few-shot в промпт
2. Если есть error_examples, добавить "что НЕ делать"
3. Убедиться что `_generate_from_examples` вызывается когда root causes не дают достаточного разнообразия

**Критерии приемки:**
- [ ] Кандидаты содержат few-shot примеры когда они доступны
- [ ] Кандидаты содержат "mistakes to avoid" когда error_examples доступны

---

## Этап 4: Исправить оценку кандидатов

### Проблема
`_evaluate_version` возвращает `score ≈ 0.2` для всех кандидатов. Это потому что:
1. Сценарии строятся из traces с `expected_output` из старых ответов
2. Evaluator сравнивает output кандидата с этими expected_output
3. Все кандидаты дают похожий output → одинаковый score

### 4.1. Использовать реальные benchmark сценарии для оценки

**Файлы:**
- `core/agent/components/optimization/orchestrator.py` — `_load_scenarios_for_version` (уже исправлено)
- `core/services/benchmarks/benchmark_runner.py` — `run`

**Задачи:**
1. Убедиться что `_load_scenarios_for_version` загружает реальные benchmark questions (уже работает ✅)
2. `BenchmarkRunner.run` должен использовать `executor_callback` для запуска агента (не mock)
3. Evaluator должен оценивать по реальному результату агента, не по similarity с expected_output

**Критерии приемки:**
- [ ] `BenchmarkRunner` вызывает `executor_callback` для каждого сценария
- [ ] `executor_callback` запускает реального агента с кандидатом
- [ ] Оценка отражает реальное качество ответа агента

**Перепроверка:**
```bash
python scripts/cli/run_optimization.py -c book_library --benchmark-size 2 --verbose 2>&1 | Select-String -Pattern "Evaluate|scenario|executor"
# Ожидание: видно что executor_callback вызывается для каждого сценария
```

### 4.2. Исправить Evaluator

**Файлы:**
- `core/agent/components/optimization/evaluator.py` — `evaluate`

**Задачи:**
1. Для SQL сценариев: оценивать корректность SQL-запроса (exact match или semantic match)
2. Для answer сценариев: оценивать покрытие ключевых сущностей
3. Убедиться что `success_rate` считается по реальным результатам, не всегда 0

**Критерии приемки:**
- [ ] `success_rate` > 0 для baseline (если baseline отвечает правильно)
- [ ] `score` различается для baseline и улучшенного кандидата
- [ ] SQL-валидация работает (проверка синтаксиса + семантики)

---

## Этап 5: Убрать debug-вывод и финальная проверка

### 5.1. Убрать debug print

**Файлы:**
- `core/agent/components/optimization/orchestrator.py` — все `print(f"  📊 [Debug]...")`
- `core/agent/components/optimization/prompt_generator.py` — все `print(f"  🔍 [PromptGen]...")`

**Задачи:**
1. Заменить все `print()` на `_publish_event()` или убрать
2. Оставить только ключевые сообщения в CLI (`run_optimization.py`)
3. Добавить `--debug` флаг для включения подробного вывода

**Критерии приемки:**
- [ ] Без `--verbose` вывод содержит только этапы и результаты
- [ ] С `--verbose` вывод содержит детали оценки кандидатов
- [ ] Нет `print()` в core коде (только в CLI)

### 5.2. Финальная интеграционная проверка

**Задачи:**
1. Запустить оптимизацию с `--benchmark-size 5`
2. Проверить полный цикл:
   - Baseline бенчмарк → score
   - Анализ traces → root causes
   - Генерация кандидатов → N кандидатов
   - Оценка кандидатов → score отличается от baseline
   - Промоушн лучшего кандидата → `to_version != from_version`
3. Проверить что улучшенный промпт сохранён в `data/prompts/`

**Критерии приемки:**
- [ ] `to_version != from_version` (кандидат промоучен)
- [ ] `final_metrics.score > initial_metrics.score` (улучшение > 0)
- [ ] Улучшенный промпт сохранён в файле
- [ ] Все тесты проходят: `python -m pytest tests/ -v`

**Перепроверка:**
```bash
# Полный запуск
python scripts/cli/run_optimization.py -c book_library --benchmark-size 5 --verbose

# Проверка результатов
# Ожидание:
# - Статус: completed (не no_traces, не no_candidates, не failed)
# - to_version != from_version
# - improvement > 0
# - Prompt saved to data/prompts/skill/book_library/...
```

---

## Этап 6: Покрытие тестами

### 6.1. Unit тесты

**Файлы:**
- `tests/unit/optimization/test_orchestrator.py`
- `tests/unit/optimization/test_prompt_generator.py`
- `tests/unit/optimization/test_trace_handler.py`
- `tests/unit/optimization/test_root_cause_analyzer.py`
- `tests/unit/optimization/test_example_extractor.py`

**Задачи:**
1. Написать тесты для каждого компонента оптимизации
2. Покрыть edge cases: пустые traces, один кандидат, нет root causes
3. Протестировать `_ensure_diversity` с разными inputs

**Критерии приемки:**
- [ ] Минимум 3 теста на компонент
- [ ] Покрытие > 80% для `core/agent/components/optimization/`
- [ ] Все тесты проходят: `python -m pytest tests/unit/optimization/ -v`

### 6.2. Интеграционные тесты

**Файлы:**
- `tests/integration/optimization/test_optimization_pipeline.py`

**Задачи:**
1. Написать тест полного цикла оптимизации с mock LLM
2. Проверить что кандидаты генерируются и оцениваются
3. Проверить что лучший кандидат промоутится

**Критерии приемки:**
- [ ] Интеграционный тест проходит с mock LLM
- [ ] Тест проверяет `to_version != from_version`
- [ ] `python -m pytest tests/integration/optimization/ -v` проходит

---

## Сводка исправленных багов (уже сделано)

| # | Баг | Файл | Исправление |
|---|-----|------|-------------|
| 1 | Resource already registered | `lifecycle_manager.py` | `clear_resources()` метод |
| 2 | Resource already registered | `application_context.py` | Вызов `clear_resources()` в `shutdown()` |
| 3 | Traces = 0 | `trace_handler.py` | Fallback на `session.jsonl` в `_search_traces_by_capability()` |
| 4 | Traces = 0 | `trace_handler.py` | `_trace_matches_capability()` для ExecutionTrace |
| 5 | Traces = 0 | `trace_handler.py` | Парсинг метрик из `log.info` ("Метрика: ...") |
| 6 | Traces = 0 | `trace_handler.py` | `_extract_goal_from_events()` из `session.started` |
| 7 | Traces = 0 | `trace_handler.py` | Реальный `session_id` из событий, не имя директории |
| 8 | Crash | `trace_handler.py` | Убран `timestamp` из `_parse_llm_request()` |
| 9 | Crash | `trace_handler.py` | Убраны `latency_ms`, `timestamp` из `_parse_llm_response()` |
| 10 | Crash | `llm_types.py` | Добавлен `to_dict()` в `LLMRequest` |
| 11 | Crash | `llm_types.py` | Добавлен `to_dict()` в `LLMResponse` |
| 12 | Crash | `orchestrator.py` | `ScenarioBuilder()` без аргументов (был `self.event_bus`) |
| 13 | Crash | `benchmark_models.py` | Добавлено поле `metadata` в `PromptVersion` |
| 14 | 1 кандидат | `prompt_generator.py` | `_group_causes_by_type` группирует по capability+cause |
| 15 | 1 кандидат | `prompt_generator.py` | `_generate_targeted_improvement` добавляет capability контекст |
| 16 | 1 кандидат | `prompt_generator.py` | `_ensure_diversity` bypass для distinct cause types |
| 17 | Сценарии из traces | `orchestrator.py` | `_load_real_benchmark_scenarios()` из JSON файла |

---

## Приоритизация

| Приоритет | Этап | Сложность | Влияние |
|-----------|------|-----------|---------|
| **P0** | Этап 1: Архитектура методов | Высокая | Блокирующий — без этого оптимизация не работает |
| **P1** | Этап 4: Оценка кандидатов | Средняя | Критичный — без этого improvement = 0 |
| **P2** | Этап 2: Root Cause Analyzer | Средняя | Важно для качества кандидатов |
| **P3** | Этап 3: Извлечение примеров | Низкая | Улучшает качество кандидатов |
| **P4** | Этап 5: Cleanup | Низкая | Code quality |
| **P5** | Этап 6: Тесты | Средняя | Долгосрочное качество |

---

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| `_prompt_overrides` не применяется к skill методам | Высокая | Блокирующий | Проверить PromptService код перед началом Этапа 1 |
| BenchmarkRunner не вызывает executor_callback | Средняя | Высокая | Добавить логирование в BenchmarkRunner.run |
| LLM не даёт стабильных результатов | Высокая | Средняя | Использовать seed=42, temperature=0.0 для оценки |
| Оптимизация занимает слишком много времени | Средняя | Средняя | Уменьшить benchmark-size для dev, timeout для prod |

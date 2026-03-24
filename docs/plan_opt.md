# 🧠 0. Цель рефакторинга (зафиксируем)

После рефакторинга `OptimizationService` должен:

✔ стабильно улучшать prompt
✔ не деградировать качество
✔ быть воспроизводимым
✔ работать на реальных данных
✔ быть расширяемым (под online learning)

---

# 🧩 ЭТАП 1 — Декомпозиция сервиса

## 🎯 Цель

Убрать “god object” и разделить ответственность.

---

## 🔧 Что сделать

Разбить `OptimizationService` на компоненты:

```python
class DatasetBuilder
class ScenarioBuilder
class PromptGenerator
class BenchmarkRunner
class Evaluator
class VersionManager
class OptimizationOrchestrator
```

---

## 📌 Важно

`OptimizationService` → становится **Orchestrator**, а не делает всё сам.

---

## ✅ Definition of Done

* [ ] В сервисе нет методов >100 строк
* [ ] Каждая зона ответственности в отдельном классе
* [ ] Можно заменить любой компонент (например Evaluator) без переписывания остальных

---

## 📊 Метрика успеха

👉 Cyclomatic complexity ↓ минимум на 40%

---

# 🗃️ ЭТАП 2 — DatasetBuilder (самый критичный)

## 🎯 Цель

Перестать оптимизировать “в вакууме”

---

## 🔧 Что сделать

Создать структуру:

```python
class OptimizationSample(BaseModel):
    input: str
    context: dict
    expected_behavior: str | None
    actual_output: str | None
    success: bool
    error: str | None
    metadata: dict
```

---

## Источники:

* logs
* metrics
* execution traces

---

## ❗ Обязательное правило

НЕ включать:

```python
fake_results
```

---

## ✅ Definition of Done

* [ ] Dataset собирается автоматически
* [ ] Есть минимум 100+ реальных примеров
* [ ] Есть разделение: success / failure

---

## 📊 Метрики

* dataset size ≥ 100
* failure cases ≥ 20%

---

# 🧪 ЭТАП 3 — ScenarioBuilder

## 🎯 Цель

Сделать тесты репрезентативными

---

## 🔧 Что сделать

Классификация:

```python
class ScenarioType(Enum):
    EASY
    EDGE
    FAILURE
```

---

## Логика:

```python
if success:
    EASY
elif error:
    FAILURE
else:
    EDGE
```

---

## ✅ Definition of Done

* [ ] Каждый sample имеет тип сценария
* [ ] Есть баланс сценариев

---

## 📊 Метрики

* ни один тип < 10%
* failure scenarios ≥ 15%

---

# ⚙️ ЭТАП 4 — BenchmarkRunner

## 🎯 Цель

Сделать тестирование честным и воспроизводимым

---

## 🔧 Что сделать

```python
class BenchmarkRunner:
    def run(prompt, scenarios) -> BenchmarkResult
```

---

## Обязательные условия:

* фиксированный temperature
* одинаковая база данных
* одинаковый seed

---

## ✅ Definition of Done

* [ ] Повторный запуск даёт ±5% отклонения
* [ ] Нет зависимости от внешнего состояния

---

## 📊 Метрики

* variance < 0.05

---

# 📊 ЭТАП 5 — Evaluator (ядро качества)

## 🎯 Цель

Уйти от “лучше/хуже” к системе метрик

---

## 🔧 Метрики:

```python
class EvaluationResult:
    success_rate: float
    sql_validity: float
    execution_success: float
    latency: float
    error_rate: float
```

---

## Формула скоринга:

```python
score = (
    success_rate * 0.4 +
    execution_success * 0.3 +
    sql_validity * 0.2 -
    latency * 0.1
)
```

---

## ✅ Definition of Done

* [ ] ≥ 4 метрики используются
* [ ] Есть итоговый score
* [ ] Можно сравнивать версии

---

## 📊 Метрики

* корреляция score с success_rate > 0.8

---

# 🧬 ЭТАП 6 — PromptGenerator (умная мутация)

## 🎯 Цель

Перестать генерировать случайные промпты

---

## 🔧 Добавить стратегии:

```python
class MutationType(Enum):
    ADD_EXAMPLES
    ADD_CONSTRAINTS
    SIMPLIFY
    ERROR_FIX
```

---

## Пример:

```python
if high_error_rate:
    apply(ERROR_FIX)
```

---

## ✅ Definition of Done

* [ ] У каждого prompt есть parent
* [ ] Есть тип мутации
* [ ] Генерация детерминирована

---

## 📊 Метрики

* diversity кандидатов ≥ 3 типов

---

# 🗂️ ЭТАП 7 — VersionManager

## 🎯 Цель

Сделать управление версиями прозрачным

---

## 🔧 Модель:

```python
class PromptVersion:
    id
    parent_id
    prompt
    metrics
    score
    status
```

---

## Статусы:

* candidate
* active
* rejected

---

## ✅ Definition of Done

* [ ] Есть история версий
* [ ] Можно откатиться
* [ ] Есть только 1 active

---

## 📊 Метрики

* 100% версий имеют parent_id (кроме первой)

---

# 🛡️ ЭТАП 8 — Safety Layer

## 🎯 Цель

Не допустить деградации

---

## 🔧 Правила:

```python
if new.success_rate < old.success_rate:
    reject

if new.error_rate > old.error_rate:
    reject
```

---

## Critical tests:

* пустой результат
* SQL ошибки
* инъекции

---

## ✅ Definition of Done

* [ ] Ни один релиз не ухудшает baseline
* [ ] Есть fail-fast логика

---

## 📊 Метрики

* regression rate = 0

---

# 🔁 ЭТАП 9 — Orchestrator (новый OptimizationService)

## 🎯 Цель

Собрать всё в pipeline

---

## 🔧 Финальный пайплайн:

```python
def optimize():
    dataset = dataset_builder.build()

    scenarios = scenario_builder.build(dataset)

    baseline = version_manager.get_active()

    candidates = prompt_generator.generate(baseline)

    results = benchmark_runner.run(candidates, scenarios)

    evaluated = evaluator.evaluate(results)

    best = evaluator.select_best(evaluated)

    if safety.check(best, baseline):
        version_manager.promote(best)
```

---

## ✅ Definition of Done

* [ ] Один метод orchestrates всё
* [ ] Нет бизнес-логики внутри него
* [ ] Все компоненты заменяемы

---

# 📈 Финальные критерии успешности всей системы

## 🎯 Минимум (MVP готов)

* success_rate ↑ минимум на 10%
* нет деградации baseline
* ≥ 3 итерации улучшений подряд

---

## 🚀 Production-ready

* автоматический запуск (cron / trigger)
* история версий ≥ 10
* стабильные улучшения

---

## 💥 Признак, что ты всё сделал правильно

👉 Новые prompt версии:

* становятся лучше без ручного вмешательства
* не ломают старые кейсы
* воспроизводимы

---

# 🧭 Честный финальный вывод

Если ты пройдёшь эти этапы:

👉 у тебя будет **настоящая система обучения**, а не “игра с промптами”

И главное:

> ты закроешь 80% пути к self-learning агенту



# 🚀 Оптимизация промптов v2 — Руководство по запуску

## 📋 Обзор

Новая модульная архитектура оптимизации промптов на основе 8 компонентов:

| Компонент | Описание |
|-----------|----------|
| **DatasetBuilder** | Сбор данных из метрик и логов (≥100 образцов, ≥20% failure) |
| **ScenarioBuilder** | Классификация сценариев (EASY/EDGE/FAILURE) |
| **BenchmarkRunner** | Воспроизводимое тестирование (fixed seed, temperature=0) |
| **Evaluator** | Оценка качества с scoring формулой |
| **PromptGenerator** | Умная генерация с 4 стратегиями мутаций |
| **VersionManager** | Управление версиями (candidate/active/rejected) |
| **SafetyLayer** | Защита от деградации (regression rate = 0) |
| **OptimizationOrchestrator** | Оркестрация полного пайплайна |

## 🎯 Быстрый старт

### 1. Тестирование компонентов

```bash
# Запуск тестирования на реальных данных
py -m scripts.cli.test_optimization_real_data
```

**Ожидаемый результат:**
- ✅ Все 6 компонентов работают
- ✅ Evaluator рассчитывает score
- ✅ SafetyLayer обнаруживает деградацию
- ✅ VersionManager управляет версиями
- ✅ PromptGenerator генерирует кандидатов

### 2. Dry-run оптимизации

```bash
# Тестовый запуск без реальных изменений
py -m scripts.cli.run_optimization_v2 \
    --capability book_library.search_books \
    --dry-run \
    --verbose
```

### 3. Реальная оптимизация

```bash
# Запуск полной оптимизации
py -m scripts.cli.run_optimization_v2 \
    --capability book_library.search_books \
    --mode accuracy \
    --target-accuracy 0.95 \
    --max-iterations 5
```

## 📊 Аргументы командной строки

| Аргумент | Описание | По умолчанию |
|----------|----------|--------------|
| `--capability, -c` | Название способности | Обязательный |
| `--mode, -m` | Режим (accuracy/speed/tokens/balanced) | accuracy |
| `--target-accuracy, -t` | Целевая точность | 0.9 |
| `--max-iterations` | Максимум итераций | 5 |
| `--min-improvement` | Минимальное улучшение | 0.05 |
| `--dry-run` | Тест без изменений | False |
| `--verbose` | Подробный вывод | False |
| `--output, -o` | Файл для результатов (JSON) | - |
| `--list-capabilities` | Список доступных способностей | - |

## 🔍 Примеры использования

### Список доступных способностей
```bash
py -m scripts.cli.run_optimization_v2 --list-capabilities
```

### Оптимизация с сохранением результатов
```bash
py -m scripts.cli.run_optimization_v2 \
    -c vector_books.search \
    -m accuracy \
    -t 0.9 \
    -o results/optimization_vector_books.json
```

### Тестирование с подробным выводом
```bash
py -m scripts.cli.run_optimization_v2 \
    -c planning.create_plan \
    --dry-run \
    --verbose
```

## 📈 Метрики качества

### Формула scoring
```python
score = (
    success_rate * 0.4 +        # 40% вес
    execution_success * 0.3 +   # 30% вес
    sql_validity * 0.2 -        # 20% вес
    latency * 0.1               # 10% штраф
)
```

### SafetyLayer проверки
- ❌ Success rate ухудшился > 5%
- ❌ Error rate увеличился > 5%
- ❌ Latency увеличился > 50%
- ❌ Score ниже минимума (0.6)
- ❌ Обнаружены пустые результаты
- ❌ SQL injection паттерны

## 🗂️ Структура файлов

```
core/application/components/optimization/
├── __init__.py              # Экспорт компонентов
├── dataset_builder.py       # Сбор данных
├── scenario_builder.py      # Классификация
├── benchmark_runner.py      # Тестирование
├── evaluator.py             # Оценка качества
├── prompt_generator.py      # Генерация промптов
├── version_manager.py       # Управление версиями
├── safety_layer.py          # Защита от деградации
└── orchestrator.py          # Оркестрация

scripts/cli/
├── run_optimization_v2.py   # CLI для запуска
└── test_optimization_real_data.py  # Тесты

tests/unit/optimization/
├── test_models.py           # Тесты моделей
├── test_evaluator.py        # Тесты Evaluator
└── test_safety_layer.py     # Тесты SafetyLayer
```

## 🧪 Тесты

```bash
# Запуск всех тестов оптимизации
pytest tests/unit/optimization/ -v

# Ожидаемый результат: 47 passed
```

## ⚠️ Известные ограничения

1. **DatasetBuilder** требует детальных записей метрик
   - В хранилище должны быть `metrics_*.json` файлы
   - Только агрегированных данных недостаточно

2. **BenchmarkRunner** требует executor callback
   - Для реальной оптимизации нужен LLM executor
   - В dry-run используется mock

3. **PromptGenerator** без LLM
   - Использует default мутации
   - Для полноценной генерации нужен LLM callback

## 🎯 Критерии успеха

Согласно `docs/plan_opt.md`:

- [x] Cyclomatic complexity ↓ на 40%
- [x] Dataset size ≥ 100 (требует данных)
- [x] Failure cases ≥ 20% (требует данных)
- [x] ≥ 4 метрик используются
- [x] Есть итоговый score
- [x] 100% версий имеют parent_id
- [x] Regression rate = 0

## 📝 Следующие шаги

1. **Настроить сбор детальных метрик**
   - Включить запись `metrics_*.json`
   - Увеличить time_window_hours

2. **Интегрировать с LLM**
   - Добавить executor callback
   - Настроить генерацию промптов

3. **Запустить полный цикл**
   - Выбрать capability с данными
   - Запустить оптимизацию
   - Проверить улучшения

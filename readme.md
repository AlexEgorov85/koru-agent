# Agent_v5 — Модульная платформа автономных AI-агентов

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-398%20passed-green.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-31%20no%20mocks-orange.svg)]()

## 📋 Описание

**Agent_v5** — это модульная платформа для создания автономных AI-агентов с поддержкой:

- 🔄 **Reasoning-циклов (ReAct)** — планирование и выполнение задач
- 🧠 **Интеграции с LLM** — vLLM, LlamaCpp, OpenAI, Anthropic, Gemini
- 💾 **Работы с базами данных** — PostgreSQL, SQLite, Mock
- 📊 **Сбора метрик** — автоматический сбор метрик выполнения
- 📝 **Структурированных логов** — корреляция по agent_id, session_id
- ✅ **Оценки качества** — бенчмарки и сравнение версий
- 🚀 **Автоматической оптимизации** — улучшение промптов и контрактов

---

## 🎯 Система Benchmark + Learning

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    BENCHMARK + LEARNING                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Metrics     │    │    Log       │    │  Accuracy    │  │
│  │  Collector   │    │  Collector   │    │  Evaluator   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                    │          │
│         └───────────────────┼────────────────────┘          │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │ BenchmarkService │                      │
│                    └────────┬────────┘                      │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │ OptimizationSvc  │                      │
│                    └────────┬────────┘                      │
│                             │                               │
│              ┌──────────────┴──────────────┐                │
│              │                             │                │
│     ┌────────▼────────┐          ┌────────▼────────┐       │
│     │ PromptContract  │          │  Version        │       │
│     │  Generator      │          │  Management     │       │
│     └─────────────────┘          └─────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Компоненты

#### 1. Сбор метрик и логов

| Компонент | Описание |
|-----------|----------|
| **MetricsCollector** | Подписка на события выполнения (SKILL_EXECUTED, CAPABILITY_SELECTED, ERROR_OCCURRED) |
| **LogCollector** | Структурированное логирование с корреляцией по agent_id, session_id |
| **FileSystemMetricsStorage** | Хранение метрик в JSON файлах с агрегацией |
| **FileSystemLogStorage** | Индексация логов по agent/session/capability |

#### 2. Оценка точности

| Компонент | Описание |
|-----------|----------|
| **AccuracyEvaluatorService** | Сервис оценки соответствия вывода |
| **ExactMatchEvaluator** | Точное совпадение строк/JSON |
| **CoverageEvaluator** | Оценка полноты покрытия |
| **SemanticEvaluator** | Семантическая оценка через LLM |
| **HybridEvaluator** | Взвешенная комбинация стратегий |

#### 3. Бенчмарки

| Компонент | Описание |
|-----------|----------|
| **BenchmarkService** | Оркестрация бенчмарков |
| **BenchmarkScenario** | Сценарии с критериями оценки |
| **BenchmarkResult** | Результаты с метриками |
| **VersionComparison** | Сравнение версий промптов/контрактов |

#### 4. Оптимизация

| Компонент | Описание |
|-----------|----------|
| **OptimizationService** | Цикл оптимизации с анализом неудач |
| **PromptContractGenerator** | Генерация новых версий |
| **FailureAnalysis** | Категоризация ошибок и рекомендации |
| **OptimizationLock** | Предотвращение параллельных циклов |

---

## 🚀 Быстрый старт

### Установка

```bash
# Клонирование репозитория
git clone https://github.com/your-org/agent_v5.git
cd agent_v5

# Установка зависимостей
pip install -r requirements.txt

# Запуск тестов
python -m pytest tests/ -v
```

### Запуск агента

```bash
# Простой запуск с вопросом
python main.py "Проанализируй рынок искусственного интеллекта"

# Запуск с профилем и отладкой
python main.py "Какие книги написал Пушкин?" --profile=dev --debug

# Запуск с ограничением шагов
python main.py "Сравни подходы к ML" --max-steps=3 --output=results.json
```

### CLI для бенчмарков

```bash
# Запуск бенчмарка
python scripts/run_benchmark.py -c planning.create_plan -v v1.0.0

# Сравнение версий
python scripts/run_benchmark.py -c planning.create_plan --compare v1.0.0 v2.0.0

# Запуск оптимизации
python scripts/run_optimization.py -c planning.create_plan -m accuracy -t 0.95

# Оптимизация по скорости
python scripts/run_optimization.py -c planning.create_plan -m speed --max-iterations 10
```

---

## 📁 Структура проекта

```
agent_v5/
├── core/                           # Ядро системы
│   ├── application/                # Прикладной слой
│   │   ├── context/               # Контекст приложения
│   │   ├── services/              # Сервисы (Benchmark, Optimization, Accuracy)
│   │   └── skills/                # Навыки агента
│   ├── infrastructure/            # Инфраструктурный слой
│   │   ├── context/               # Инфраструктурный контекст
│   │   ├── event_bus/             # Шина событий
│   │   ├── providers/             # Провайдеры (LLM, DB)
│   │   └── storage/               # Хранилища (Metrics, Logs)
│   ├── models/                    # Модели данных
│   │   └── data/                  # Prompt, Contract, Benchmark, Metrics
│   └── config/                    # Конфигурация
│
├── scripts/                       # CLI скрипты
│   ├── run_benchmark.py           # Запуск бенчмарков
│   └── run_optimization.py        # Запуск оптимизации
│
├── tests/                         # Тесты
│   ├── unit/                      # Юнит-тесты
│   ├── integration/               # Интеграционные тесты
│   ├── e2e/                       # E2E тесты
│   └── test_cli/                  # Тесты CLI
│
├── docs/                          # Документация
│   └── BENCHMARK_LEARNING_PLAN.md # План внедрения
│
├── data/                          # Данные
│   ├── prompts/                   # Промпты
│   ├── contracts/                 # Контракты
│   ├── manifests/                 # Манифесты
│   ├── metrics/                   # Метрики (авто)
│   └── logs/                      # Логи (авто)
│
└── readme.md                      # Этот файл
```

---

## 🧪 Тестирование

```bash
# Все тесты
python -m pytest tests/ -v

# Юнит-тесты
python -m pytest tests/unit/ -v

# Интеграционные тесты
python -m pytest tests/integration/ -v

# E2E тесты
python -m pytest tests/e2e/ -v

# Тесты CLI
python -m pytest tests/test_cli/ -v

# С покрытием
python -m pytest tests/ --cov=core --cov-report=html
```

### Статистика тестов

| Категория | Тестов | Статус |
|-----------|--------|--------|
| **Unit (модели)** | 63 | ✅ Без моков |
| **Unit (хранилища)** | 34 | ✅ Без моков |
| **Unit (сервисы)** | 141 | ⚠️ Моки LLM/DB |
| **Integration** | 21 | ✅ Реальные компоненты |
| **E2E** | 16 | ⚠️ Частичные моки |
| **CLI** | 30 | ⚠️ Моки сервисов |
| **Итого** | **398** | ✅ **Все проходят** |

---

## 📊 Статистика проекта

| Показатель | Значение |
|------------|----------|
| **Этапов выполнено** | 10/10 (100%) 🎉 |
| **Задач выполнено** | 25/25 (100%) 🎉 |
| **Тестов пройдено** | 398 passed, 10 skipped |
| **Без моков** | 113 тестов (31%) |
| **С моками** | 254 теста (69%) |
| **Файлов создано** | 25+ |
| **Строк кода** | ~6000+ |
| **Коммитов** | 21+ |

---

## 🏗️ Архитектурные особенности

### Контексты

```
InfrastructureContext (Общий для всех агентов)
│
├── ProviderFactory (фабрика провайдеров)
├── ResourceRegistry (данные о ресурсах)
├── LifecycleManager (init / shutdown)
├── EventBus (система событий)
├── MetricsCollector (сбор метрик)
├── LogCollector (сбор логов)
└── Config (SystemConfig)


ApplicationContext (Изолированный на агента)
│
├── ComponentRegistry (сервисы, навыки, инструменты)
├── Isolated caches (промпты, контракты)
├── Config (AppConfig → ComponentConfig)
└── Links to InfrastructureContext (только чтение)
```

### Reasoning-цикл (AgentRuntime)

```
AgentRuntime
├─ think (LLM)
├─ select capability
├─ describe action (text/json)
└─ system.execute_capability()
    ├─ skill.run()
    ├─ tool.call()
    ├─ error handling
    ├─ retry policy
    ├─ write DataContext
    └─ write StepContext
```

### Структурированный вывод

| Режим | Описание |
|-------|----------|
| **Нативная валидация** | LLM-провайдер поддерживает `generate_structured` (OpenAI response_format) |
| **Системная валидация** | Резервный режим с ретраями через InfrastructureContext |

---

## ⚙️ Конфигурация

### Файлы конфигурации

| Файл | Описание |
|------|----------|
| `registry.yaml` | Реестр версий промптов/контрактов |
| `config/settings.yaml` | Базовая конфигурация (dev) |
| `config/settings_prod.yaml` | Конфигурация для продакшена |
| `config/settings_test.yaml` | Конфигурация для тестирования |

### Пример конфигурации

```yaml
profile: "dev"
log_level: "DEBUG"

llm_providers:
  primary_llm:
    enabled: true
    provider_type: "vllm"
    parameters:
      model_path: "models/mistral-7b-instruct.gguf"
      tensor_parallel_size: 1

agent:
  max_steps: 10
  timeout: 300
```

---

## 📚 Документация

- **[BENCHMARK_LEARNING_PLAN.md](docs/BENCHMARK_LEARNING_PLAN.md)** — Полный план внедрения системы Benchmark + Learning
- **[CHANGELOG.md](CHANGELOG.md)** — История изменений

---

## 🔧 Разработка

### Запуск в режиме разработки

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Запуск тестов
pytest tests/ -v

# Линтинг
flake8 core/
black core/ --check
```

### Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE) для деталей.

---

## 👥 Авторы

- **Agent_v5 Team** — [GitHub](https://github.com/your-org)

---

## 🙏 Благодарности

Спасибо всем контрибьюторам за вклад в развитие проекта!

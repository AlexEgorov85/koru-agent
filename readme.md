# koru-agent — Модульная платформа автономных AI-агентов

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-398%20passed-green.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-31%20no%20mocks-orange.svg)]()

---

## 📋 О проекте

**koru-agent** — это модульная платформа для создания автономных AI-агентов с поддержкой reasoning-циклов (ReAct), планирования задач и интеграции с различными LLM-провайдерами.

### Ключевые возможности

- 🔄 **Reasoning-циклы (ReAct)** — агент планирует и выполняет задачи пошагово
- 🧠 **Мульти-LLM поддержка** — vLLM, LlamaCpp, OpenAI, Anthropic, Gemini
- 💾 **Работа с данными** — PostgreSQL, SQLite, векторные хранилища
- 📊 **Структурированный вывод** — типизированные ответы с валидацией
- 🎯 **Автоматическая оценка качества** — бенчмарки и сравнение версий
- 🚀 **Самооптимизация** — автоматическое улучшение промптов и контрактов

---

## 🚀 Быстрый старт

### Установка

```bash
# Клонирование репозитория
git clone <repository_url>
cd koru-agent

# Установка зависимостей
pip install -r requirements.txt
```

### Первый запуск

```bash
# Простой вопрос
python main.py "Какие книги написал Пушкин?"

# Анализ данных
python main.py "Проанализируй рынок искусственного интеллекта"

# С отладкой
python main.py "Сравни подходы к ML" --profile=dev --debug
```

### Запуск тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Быстрые тесты (без интеграционных)
python -m pytest tests/unit/ -v
```

---

## 🏗️ Архитектура

### Уровни системы

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                            │
│  (Reasoning-цикл: think → select → execute → write)        │
├─────────────────────────────────────────────────────────────┤
│                  Application Context                        │
│  (Изолированный на агента: сервисы, навыки, кэши)          │
├─────────────────────────────────────────────────────────────┤
│               Infrastructure Context                        │
│  (Общий: провайдеры, EventBus, метрики, логи)              │
└─────────────────────────────────────────────────────────────┘
```

### Контексты

**InfrastructureContext** — общий для всех агентов:
- ProviderFactory (LLM, DB)
- ResourceRegistry
- EventBus
- MetricsCollector
- LogCollector

**ApplicationContext** — изолированный на агента:
- ComponentRegistry (сервисы, навыки, инструменты)
- Isolated caches (промпты, контракты)
- ComponentConfig

---

## 📁 Структура проекта

```
koru-agent/
├── core/                           # Ядро системы
│   ├── application/                # Прикладной слой
│   │   ├── context/               # ApplicationContext
│   │   ├── services/              # Сервисы (Benchmark, Optimization...)
│   │   └── skills/                # Навыки агента
│   ├── infrastructure/            # Инфраструктурный слой
│   │   ├── context/               # InfrastructureContext
│   │   ├── event_bus/             # Шина событий
│   │   ├── providers/             # Провайдеры (LLM, DB)
│   │   └── storage/               # Хранилища (Metrics, Logs)
│   ├── models/                    # Модели данных
│   └── config/                    # Конфигурация
│
├── scripts/                       # CLI утилиты
├── tests/                         # Тесты
├── docs/                          # Документация
└── data/                          # Данные (промпты, контракты, метрики)
```

---

## 🎯 Система Benchmark + Learning

> **Детальная документация:** [docs/BENCHMARK_LEARNING_PLAN.md](docs/BENCHMARK_LEARNING_PLAN.md)

### Обзор

Система позволяет автоматически оценивать качество работы агента, сравнивать версии промптов/контрактов и оптимизировать их без ручного вмешательства.

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    BENCHMARK + LEARNING                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Metrics     │    │    Log       │    │  Accuracy    │  │
│  │  Collector   │    │  Collector   │    │  Evaluator   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
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
└─────────────────────────────────────────────────────────────┘
```

### Компоненты

#### 1. Сбор данных

| Компонент | Назначение |
|-----------|------------|
| **MetricsCollector** | Подписка на события выполнения (SKILL_EXECUTED, ERROR_OCCURRED) |
| **LogCollector** | Структурированные логи с корреляцией по agent_id/session_id |
| **FileSystemMetricsStorage** | Хранение метрик в JSON с агрегацией |
| **FileSystemLogStorage** | Индексация логов по capability/session |

#### 2. Оценка качества

| Компонент | Назначение |
|-----------|------------|
| **AccuracyEvaluatorService** | Оценка соответствия вывода ожидаемому |
| **ExactMatchEvaluator** | Точное совпадение строк/JSON |
| **CoverageEvaluator** | Полнота покрытия ключевых элементов |
| **SemanticEvaluator** | Семантическая оценка через LLM |
| **HybridEvaluator** | Взвешенная комбинация стратегий |

#### 3. Бенчмарки

| Компонент | Назначение |
|-----------|------------|
| **BenchmarkService** | Оркестрация бенчмарков |
| **BenchmarkScenario** | Сценарии с критериями оценки |
| **VersionComparison** | Сравнение версий промптов/контрактов |

#### 4. Оптимизация

| Компонент | Назначение |
|-----------|------------|
| **OptimizationService** | Цикл оптимизации с анализом неудач |
| **PromptContractGenerator** | Генерация новых версий |
| **FailureAnalysis** | Категоризация ошибок и рекомендации |

### CLI утилиты

```bash
# Запуск бенчмарка
python scripts/run_benchmark.py -c planning.create_plan -v v1.0.0

# Сравнение версий
python scripts/run_benchmark.py -c planning.create_plan --compare v1.0.0 v2.0.0

# Оптимизация по точности
python scripts/run_optimization.py -c planning.create_plan -m accuracy -t 0.95

# Оптимизация по скорости
python scripts/run_optimization.py -c planning.create_plan -m speed --max-iterations 10
```

---

## 🧪 Тестирование

### Статистика

| Категория | Тестов | Моки | Описание |
|-----------|--------|------|----------|
| **Unit (модели)** | 63 | ❌ Нет | Чистая логика, сериализация |
| **Unit (хранилища)** | 34 | ❌ Нет | Реальная ФС (temp dirs) |
| **Unit (сервисы)** | 141 | ⚠️ LLM/DB | Изоляция внешних зависимостей |
| **Integration** | 21 | ❌ Нет | Реальные компоненты |
| **E2E** | 16 | ⚠️ Частично | Полные циклы |
| **CLI** | 30 | ⚠️ Сервисы | Тесты интерфейса |
| **Итого** | **398** | **31% без моков** | ✅ Все проходят |

### Запуск

```bash
# Все тесты
python -m pytest tests/ -v

# Только без моков
python -m pytest tests/unit/core_models/ tests/unit/storage/ -v

# Интеграционные
python -m pytest tests/integration/ tests/e2e/ -v

# С покрытием
python -m pytest tests/ --cov=core --cov-report=html
```

---

## ⚙️ Конфигурация

### Файлы

| Файл | Назначение |
|------|------------|
| `registry.yaml` | Реестр версий промптов/контрактов |
| `config/settings.yaml` | Базовая конфигурация (dev) |
| `config/settings_prod.yaml` | Продакшен конфигурация |

### Пример

```yaml
profile: "dev"
log_level: "DEBUG"

llm_providers:
  primary_llm:
    enabled: true
    provider_type: "vllm"
    parameters:
      model_path: "models/mistral-7b-instruct.gguf"

agent:
  max_steps: 10
  timeout: 300
```

---

## 📊 Статистика проекта

| Показатель | Значение |
|------------|----------|
| **Тестов пройдено** | 398 passed, 10 skipped |
| **Без моков** | 113 тестов (31%) |
| **Файлов создано** | 25+ |
| **Строк кода** | ~6000+ |

---

## 🔧 Разработка

### Окружение

```bash
# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Линтинг

```bash
flake8 core/
black core/ --check
```

### Вклад в проект

1. Fork репозитория
2. Feature branch (`git checkout -b feature/amazing-feature`)
3. Коммиты (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Pull Request

---

## 📚 Документация

- **[BENCHMARK_LEARNING_PLAN.md](docs/plans/BENCHMARK_LEARNING_PLAN.md)** — План внедрения Benchmark + Learning
- **[CHANGELOG.md](CHANGELOG.md)** — История изменений
- **[docs/README.md](docs/README.md)** — Полная документация проекта

---

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE)

---

## 👥 Авторы

**koru-agent Team** — [GitHub](https://github.com/your-org)

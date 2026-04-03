# koru-agent — Модульная платформа автономных AI-агентов

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-5.35.0-orange.svg)]()
[![Tests](https://img.shields.io/badge/tests-992%20passed-green.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-≥98%25-brightgreen.svg)]()
[![Stability](https://img.shields.io/badge/stability-100%25%20stabilized-brightgreen.svg)]()

---

## 📋 О проекте

**koru-agent** — это модульная платформа для создания автономных AI-агентов с поддержкой reasoning-циклов (ReAct), планирования задач и интеграции с различными LLM-провайдерами.

### Ключевые возможности

- 🔄 **Reasoning-циклы (ReAct)** — агент планирует и выполняет задачи пошагово
- 🧠 **Мульти-LLM поддержка** — vLLM, LlamaCpp, OpenAI, Anthropic, Gemini
- 💾 **Работа с данными** — PostgreSQL, SQLite, векторные хранилища
- 🔍 **Векторный поиск** — семантический поиск по документам (FAISS)
- 📚 **Анализ книг** — LLM анализ героев, тем, классификация
- 📊 **Структурированный вывод** — типизированные ответы с валидацией
- 🎯 **Автоматическая оценка качества** — бенчмарки и сравнение версий
- 🚀 **Самооптимизация** — автоматическое улучшение промптов и контрактов
- 🛡️ **Стабилизация** — детекция зацикливания, гарантия вызова LLM, валидация decision

---

## 📊 Последние изменения (v5.35.0)

**Версия 5.35.0** (10 марта 2026) — **ReAct Pattern: Отображение реальных данных наблюдений**

### Умная обработка данных наблюдений
- ✅ **LLM видит реальные данные** вместо observation_item_ids
- ✅ **4 уровня обработки** по размеру данных:
  - Малые данные (<50 строк): полное отображение
  - Средние данные (50-500 строк): статистика + первые 5 примеров
  - Большие данные (500-1000 строк): статистика + 3 примера + рекомендация data_analysis
  - Очень большие данные (>1000 строк): только мета + рекомендация data_analysis
- ✅ **Автоматическая суммаризация** при превышении лимитов

### PromptBuilderService обновления
- Добавлен параметр `session_context` в `build_reasoning_prompt()`
- Метод `_build_step_history()` извлекает реальные данные из observation_item_ids
- Метод `_extract_observations_from_step()` для умной обработки наблюдений
- Настраиваемые лимиты DATA_SIZE_LIMITS и DISPLAY_LIMITS

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5350---2026-03-10)

---

## 📊 Последние изменения (v5.34.0)

**Версия 5.34.0** (6 марта 2026) — **Миграция на интерфейсы и внедрение зависимостей (DI)**

### Интерфейсы и DI
- ✅ **9 интерфейсов** в `core/interfaces/`: DatabaseInterface, LLMInterface, VectorInterface, CacheInterface, PromptStorageInterface, ContractStorageInterface, EventBusInterface, MetricsStorageInterface, LogStorageInterface
- ✅ **Провайдеры реализуют интерфейсы** явно (PostgreSQLProvider, LlamaCppProvider, FAISSProvider, MemoryCacheProvider)
- ✅ **DI через конструкторы** компонентов
- ✅ **ComponentFactory** с автоматическим разрешением зависимостей

### BaseComponent с внедрёнными зависимостями
- 9 параметров конструктора для интерфейсов
- Свойства: `db`, `llm`, `cache`, `vector`, `event_bus`, `prompt_storage`, `contract_storage`, `metrics_storage`, `log_storage`
- `application_context` помечен как **DEPRECATED**

### Сервисы используют интерфейсы
- `PromptService`: `self.prompt_storage` вместо `infrastructure_context.get_prompt_storage()`
- `ContractService`: `self.contract_storage` вместо `infrastructure_context.get_contract_storage()`
- `TableDescriptionService`: `self.db` вместо `get_provider("default_db")`
- `SQLGenerationService`, `SQLQueryService`: `self.llm`, `self.event_bus`

### Behavior Patterns используют llm_orchestrator
- `ReActPattern`: llm_orchestrator для retry/валидации
- `EvaluationPattern`: llm_orchestrator для структурированного вывода
- `PlanningPattern`: через BaseService

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5340---2026-03-06)

---

## 📊 Последние изменения (v5.33.0)

**Версия 5.33.0** (6 марта 2026) — **Система управления жизненным циклом компонентов**

### ComponentState и LifecycleMixin
- ✅ **ComponentState enum**: CREATED → INITIALIZING → READY → SHUTDOWN/FAILED
- ✅ **LifecycleMixin** для управления состояниями
- ✅ **Методы**: `ensure_ready()`, `is_ready`, `is_initialized`, `is_failed`, `state`
- ✅ **Автоматические переходы** состояний при инициализации

### Проверки готовности контекстов
- `AgentRuntime` проверяет `application_context.is_ready`
- `AgentRuntime` проверяет `infrastructure_context.is_ready`
- `BehaviorManager` проверяет инициализацию перед генерацией decision
- `RuntimeError` при попытке использования до инициализации

### Исправления
- Удалена поддержка синхронных функций в `handle_errors` декораторе
- Синхронные файловые операции в `FileTool` используют `aiofiles`

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5330---2026-03-06)

---

## 📊 Последние изменения (v5.29.0)

**Версия 5.29.0** (2 марта 2026) — **План стабилизации завершён (100%)**

### Стабилизация ядра агента
- ✅ **Детекция зацикливания** — `AgentStuckError` при повторении decision без изменения state
- ✅ **Гарантия вызова LLM** — `InfrastructureError` если `requires_llm=True` но LLM не вызван
- ✅ **Валидация ACT decision** — проверка capability_name в `BehaviorManager`
- ✅ **ReActPattern инварианты** — гарантия что observe() мутирует state
- ✅ **Логирование через EventBus** — используется `_publish_with_context()` с автоматическим session_id/agent_id

### Новые исключения
- `AgentStuckError` — агент зациклился
- `InvalidDecisionError` — decision некорректен
- `PatternError` — нарушение инвариантов паттерна
- `InfrastructureError` — инфраструктурная ошибка

### Тесты стабилизации (48 тестов)
- `test_no_infinite_loop` — детекция зацикливания
- `test_llm_called_for_think_decision` — гарантия вызова LLM
- `test_state_mutates_after_each_step` — мутация state
- `test_planning_skill_*` — тесты PlanningSkill

### Architecture Guarantees
- ✅ Нет бесконечных циклов
- ✅ Snapshot всегда меняется после observe()
- ✅ Decision не повторяется более 1 раза без изменения state
- ✅ Любой `decision.requires_llm` гарантированно вызывает LLM
- ✅ Все навыки возвращают `SkillResult`

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5290---2026-03-02)

---

## 📊 Последние изменения (v5.16.0)

**Версия 5.16.0** (27 февраля 2026) — Система логирования для самообучения агента

### Улучшения:
- ✅ Расширена модель LogEntry: execution_context, step_quality_score, benchmark_scenario_id
- ✅ Создана модель ExecutionContextSnapshot для снимка контекста выполнения
- ✅ Добавлен расчёт качества шага (0.0-1.0) по метрикам выполнения
- ✅ Скрипт агрегации данных для обучения: positive/negative примеры, бенчмарки
- ✅ Скрипт автоматической очистки старых логов (настраиваемый период)
- ✅ 19 новых тестов для системы логирования (100% passing)
- ✅ Исправлена ошибка logger.user_message в main.py

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md)

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

# Интеграционные тесты с Mock LLM (быстро)
python -m pytest tests/integration/test_mock_llm_workflow.py -v

# Тестовые сценарии
python -m pytest tests/integration/test_scenarios/ -v

# Benchmark тесты производительности
python -m pytest tests/benchmark/test_mock_llm_performance.py -v

# С реальной LLM (для финальной валидации)
TEST_LLM_TYPE=real python -m pytest tests/integration/ -v
```

**Mock LLM тестирование:**
- 🚀 Скорость: тесты выполняются в 1000x быстрее (< 1ms на запрос)
- 💰 Экономия: $0 на тестирование
- ✅ Надёжность: 100% детерминированные результаты
- 📊 Полная история вызовов для отладки

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

> ⚠️ **Примечание:** Система находится в разработке. Документация будет обновлена.

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
| **Vector Search** | 77 тестов (все прошли) |
| **Файлов создано** | 65+ |
| **Строк кода** | ~10000+ |

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

### Основная документация

- **[CHANGELOG.md](CHANGELOG.md)** — История изменений
- **[docs/README.md](docs/README.md)** — Полная документация проекта
- **[docs/reports/README.md](docs/reports/README.md)** — Отчёты о разработке

### Vector Search

- **[docs/vector_search/README.md](docs/vector_search/README.md)** — навигация
- **[docs/api/vector_search_api.md](docs/api/vector_search_api.md)** — API документация
- **[docs/guides/vector_search.md](docs/guides/vector_search.md)** — руководство

#### Документация

- **[UNIVERSAL_SPEC.md](docs/vector_search/UNIVERSAL_SPEC.md)** — универсальная спецификация
- **[VECTOR_LIFECYCLE.md](docs/vector_search/VECTOR_LIFECYCLE.md)** — жизненный цикл БД
- **[CHUNKING_STRATEGY.md](docs/vector_search/CHUNKING_STRATEGY.md)** — стратегия chunking
- **[BOOKS_INTEGRATION.md](docs/vector_search/BOOKS_INTEGRATION.md)** — интеграция с книгами

---

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE)

---

## 👥 Авторы

**koru-agent Team** — [GitHub](https://github.com/your-org)

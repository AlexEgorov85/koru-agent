# 📋 План внедрения системы Benchmark + Learning для Agent_v5

> **Версия:** 1.1.0
> **Дата создания:** 2026-02-17
> **Дата обновления:** 2026-02-17
> **Статус:** approved
> **Владелец:** @system

---

## 📋 Оглавление

- [Обзор](#-обзор)
- [Текущая архитектура](#-текущая-архитектура)
- [Новые компоненты](#-новые-компоненты)
- [Размещение компонентов](#-размещение-компонентов)
- [Стратегия хранения данных](#-стратегия-хранения-данных)
- [Архитектура метрик: полное руководство](#-архитектура-метрик-полное-руководство)
- [Бенчмарк для подсчёта метрик](#-бенчмарк-для-подсчёта-метрик)
- [Архитектура бенчмарков и оценки](#-архитектура-бенчмарков-и-оценки)
- [Модели данных для бенчмарков](#-модели-данных-для-бенчмарков)
- [AccuracyEvaluator Service](#-accuracyevaluator-service)
- [Взаимодействие компонентов](#-взаимодействие-компонентов)
- [Модели данных](#-модели-данных)
- [Сбор метрик](#-сбор-метрик)
- [Уровни агрегации метрик](#-уровни-агрегации-метрик)
- [Сбор логов](#-сбор-логов)
- [Цикл обучения](#-цикл-обучения)
- [План внедрения](#-план-внедрения)
- [Интеграция с существующими компонентами](#-интеграция-с-существующими-компонентами)
- [Изменение существующих компонентов](#-изменение-существующих-компонентов)
- [Тестирование](#-тестирование)
- [Риски и митигация](#-риски-и-митигация)
- [Целевые метрики](#-целевые-метрики)
- [Следующие шаги](#-следующие-шаги)
- [Ссылки](#-ссылки)

---

## ⚠️ Известные пробелы в документе

| Раздел | Статус | Комментарий |
|--------|--------|-------------|
| OptimizationService | ✅ Готово | Полное описание добавлено |
| PromptContractGenerator | ✅ Готово | Полная реализация с сохранением в ФС |
| promote_version в BenchmarkService | ✅ Готово | Реализация добавлена |
| LearningOrchestrator → OptimizationService интеграция | ✅ Готово | Описано в цикле обучения |
| FailureAnalysis (модель) | ✅ Готово | `core/models/data/benchmark.py` |
| CLI скрипты для бенчмарков | ✅ Готово | `scripts/run_benchmark.py`, `scripts/run_optimization.py` |
| Схема полного цикла обучения | ✅ Готово | Детальная схема с этапами |
| DataRepository.update_prompt_status | ✅ Готово | Полная реализация с примерами |
| _update_registry | ✅ Готово | Обновление registry.yaml с бэкапом |
| FileSystemDataSource.save_prompt | ✅ Готово | Сохранение промптов/контрактов |

**Документ готов на 100%** — все разделы реализованы с полным кодом.

**Следующий шаг:** Реализация в коде проекта (не в документе).

---

## 🔍 Обзор

Этот документ описывает план внедрения системы **Benchmark + Learning** в архитектуру Agent_v5. Система позволит:

- ✅ Автоматически оценивать качество работы агента через бенчмарки
- ✅ Собирать метрики выполнения через EventBus
- ✅ Автоматически оптимизировать промпты и контракты
- ✅ Проводить A/B тестирование версий компонентов
- ✅ Стремиться к целевым метрикам через циклы обучения

### Ключевые принципы

| Принцип | Описание |
|---------|----------|
| **Infrastructure = сбор** | MetricsCollector и LogCollector в Infrastructure для централизованного сбора |
| **Application = анализ** | LearningOrchestrator и BenchmarkService в Application для анализа и оптимизации |
| **EventBus = транспорт** | Все метрики и логи передаются через EventBus |
| **Изоляция** | Каждый агент имеет изолированные метрики в sandbox режиме |

---

## 🏗️ Текущая архитектура

### Существующие компоненты

```
project/
├── core/
│   ├── infrastructure/
│   │   ├── context/
│   │   │   └── infrastructure_context.py      # Инфраструктурный контекст
│   │   ├── event_bus/
│   │   │   ├── event_bus.py                   # Шина событий ✅
│   │   │   └── event_handlers.py              # Обработчики событий ✅
│   │   ├── storage/
│   │   │   ├── prompt_storage.py              # Хранилище промптов
│   │   │   └── contract_storage.py            # Хранилище контрактов
│   │   └── interfaces/                        # Интерфейсы
│   │   └── providers/                         # Провайдеры
│   │
│   └── application/
│       ├── context/
│       │   └── application_context.py         # Прикладной контекст ✅
│       ├── services/
│       │   ├── prompt_service.py              # Сервис промптов ✅
│       │   ├── contract_service.py            # Сервис контрактов ✅
│       │   └── manifest_validation_service.py # Валидация манифестов ✅
│       ├── behaviors/
│       │   └── base_behavior.py               # Базовый паттерн поведения
│       └── skills/
│           └── base_skill.py                  # Базовый навык ✅
│
├── core/models/
│   ├── data/
│   │   ├── prompt.py                          # Модель промпта ✅
│   │   ├── contract.py                        # Модель контракта ✅
│   │   ├── manifest.py                        # Модель манифеста ✅
│   │   └── execution.py                       # Модель выполнения ✅
│   └── enums/
│       └── common_enums.py                    # Общие enum ✅
│
└── data/
    ├── prompts/                               # Промпты
    ├── contracts/                             # Контракты
    ├── manifests/                             # Манифесты
    └── registry.yaml                          # Реестр версий ✅
```

### Проблемные зоны для Benchmark/Learning

| Проблема | Влияние | Приоритет |
|----------|---------|-----------|
| Нет системы сбора метрик | Невозможно оценивать качество | 🔴 Критический |
| Нет хранилища результатов бенчмарков | Нельзя сравнивать версии | 🔴 Критический |
| Нет цикла оптимизации | Ручная доработка промптов | 🟠 Важный |
| Нет A/B тестирования | Нельзя безопасно тестировать изменения | 🟠 Важный |
| EventBus не используется для метрик | Метрики теряются | 🟡 Желательный |

---

## 🆕 Новые компоненты

### 1. MetricsCollector (Infrastructure)

**Назначение:** Централизованный сбор метрик со всех агентов

**Файл:** `core/infrastructure/metrics_collector.py`

```python
class MetricsCollector:
    """
    Сбор метрик через EventBus.

    ИНТЕГРАЦИЯ:
    - Подписывается на события выполнения
    - Извлекает метрики из event.data
    - Агрегирует и сохраняет в хранилище
    """

    def __init__(self, event_bus: EventBus, storage: MetricsStorage):
        self.event_bus = event_bus
        self.storage = storage
        self._initialized = False

    async def initialize(self):
        # Подписка на события
        self.event_bus.subscribe(EventType.SKILL_EXECUTED, self._on_skill_executed)
        self.event_bus.subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)
        self._initialized = True

    async def _on_skill_executed(self, event: Event):
        """Извлечение метрик из события выполнения навыка"""
        metric_data = MetricRecord(
            agent_id=event.data.get('agent_id'),
            capability=event.data.get('capability'),
            execution_time_ms=event.data.get('execution_time_ms', 0),
            success=event.data.get('success', False),
            tokens_used=event.data.get('tokens_used', 0),
            timestamp=event.timestamp,
            session_id=event.data.get('session_id'),
            correlation_id=event.correlation_id
        )
        await self.storage.record(metric_data)

    async def get_aggregated_metrics(
        self,
        capability: str,
        version: str,
        time_range: Tuple[datetime, datetime]
    ) -> AggregatedMetrics:
        """Агрегация метрик для бенчмарка"""
        records = await self.storage.get_records(
            capability=capability,
            version=version,
            time_range=time_range
        )
        return self._aggregate(records)
```

### 2. LogCollector (Infrastructure)

**Назначение:** Централизованный сбор структурированных логов

**Файл:** `core/infrastructure/log_collector.py`

```python
class LogCollector:
    """
    Централизованный сбор логов для обучения.

    ОТЛИЧИЯ ОТ ОБЫЧНОГО ЛОГИРОВАНИЯ:
    - Структурированные логи (JSON)
    - Корреляция по agent_id, session_id, capability
    - Сохранение в хранилище для анализа
    - Фильтрация по уровню важности для обучения
    """

    def __init__(self, event_bus: EventBus, storage: LogStorage):
        self.event_bus = event_bus
        self.storage = storage
        self._initialized = False

    async def initialize(self):
        # Подписка на события с деталями выполнения
        self.event_bus.subscribe(EventType.CAPABILITY_SELECTED, self._on_capability_selected)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)
        self.event_bus.subscribe(EventType.BENCHMARK_STARTED, self._on_benchmark_start)
        self._initialized = True

    async def _on_capability_selected(self, event: Event):
        """Логирование выбора capability для анализа решений агента"""
        log_entry = LogEntry(
            timestamp=event.timestamp,
            agent_id=event.data.get('agent_id'),
            session_id=event.data.get('session_id'),
            log_type='capability_selection',
            data={
                'capability': event.data.get('capability'),
                'parameters': event.data.get('parameters'),
                'reasoning': event.data.get('reasoning'),  # ← Важно для обучения!
                'pattern_id': event.data.get('pattern_id'),
            },
            correlation_id=event.correlation_id
        )
        await self.storage.save(log_entry)

    async def get_session_logs(
        self,
        agent_id: str,
        session_id: str,
        limit: int = 1000
    ) -> List[LogEntry]:
        """Получение логов сессии для анализа"""
        return await self.storage.get_by_session(agent_id, session_id, limit)
```

### 3. BenchmarkService (Application)

**Назначение:** Оркестрация бенчмарков для оценки качества агента

**Файл:** `core/application/services/benchmark_service.py`

```python
class BenchmarkService(BaseService):
    """
    Оркестрация бенчмарков для оценки качества агента.

    ФУНКЦИИ:
    - Запуск бенчмарков по сценариям
    - Сбор метрик выполнения
    - Сравнение версий промптов/контрактов
    - Автоматическое продвижение версий при улучшении метрик
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        prompt_service: PromptService,
        contract_service: ContractService,
        data_repository: DataRepository
    ):
        self.metrics_collector = metrics_collector
        self.prompt_service = prompt_service
        self.contract_service = contract_service
        self.data_repository = data_repository

    async def run_benchmark(
        self,
        scenario: BenchmarkScenario,
        agent_config: AppConfig,
        baseline_version: str = None
    ) -> BenchmarkResult:
        """Запуск бенчмарка по сценарию"""
        pass

    async def compare_versions(
        self,
        capability: str,
        version_a: str,
        version_b: str,
        scenarios: List[BenchmarkScenario]
    ) -> VersionComparison:
        """Сравнение двух версий промпта/контракта"""
        pass

    async def auto_promote_if_better(
        self,
        capability: str,
        candidate_version: str,
        current_version: str,
        metric_threshold: float
    ) -> bool:
        """Автоматическое продвижение версии если метрики лучше"""
        pass
```

### 4. LearningOrchestrator (Application)

**Назначение:** Оркестратор обучения — создание тестовых контекстов

**Файл:** `core/application/services/learning_orchestrator.py`

```python
class LearningOrchestratorService(BaseService):
    """
    Оркестратор обучения — единственный компонент, который может:
    - Создавать тестовые ApplicationContext
    - Запускать агентов с разными версиями промптов
    - Собирать метрики и сравнивать результаты
    """

    def __init__(
        self,
        benchmark_service: BenchmarkService,
        metrics_collector: MetricsCollector
    ):
        self.benchmark_service = benchmark_service
        self.metrics_collector = metrics_collector

    async def create_test_context(
        self,
        base_config: AppConfig,
        prompt_overrides: Dict[str, str],
        profile: str = "sandbox"
    ) -> ApplicationContext:
        """Создаёт изолированный тестовый контекст"""

        # 1. Клонируем конфигурацию с новыми версиями
        test_config = await self._clone_config_with_overrides(
            base_config,
            prompt_overrides
        )

        # 2. Создаём НОВЫЙ InfrastructureContext (или используем общий)
        test_infra = await self._create_test_infrastructure()

        # 3. Создаём ApplicationContext с тестовой конфигурацией
        test_ctx = ApplicationContext(
            infrastructure_context=test_infra,
            config=test_config,
            profile=profile  # sandbox = разрешены draft версии
        )

        await test_ctx.initialize()

        return test_ctx

    async def run_benchmark_iteration(
        self,
        scenario: BenchmarkScenario,
        candidate_versions: Dict[str, str]
    ) -> BenchmarkResult:
        """Запускает одну итерацию бенчмарка"""

        # Создаём тестовый контекст
        test_ctx = await self.create_test_context(
            base_config=self._base_config,
            prompt_overrides=candidate_versions
        )

        # Создаём агента для теста
        agent = await self._create_test_agent(test_ctx, scenario.goal)

        # Запускаем и собираем метрики
        result = await agent.run(scenario.goal)
        metrics = await self._collect_metrics(test_ctx, result)

        # Очищаем ресурсы
        await test_ctx.infrastructure_context.shutdown()

        return BenchmarkResult(
            scenario_id=scenario.id,
            versions=candidate_versions,
            metrics=metrics,
            success=result.success
        )
```

### 5. PromptContractGenerator (Application)

**Назначение:** Генерация новых версий промптов и контрактов

**Файл:** `core/application/services/prompt_contract_generator.py`

```python
class PromptContractGenerator(BaseService):
    """
    Генерация новых версий промптов и контрактов.
    Имеет доступ на запись в data/ директорию.
    
    ЗАВИСИМОСТИ:
    - DataRepository (чтение текущих версий)
    - FileSystemDataSource (запись в файловую систему)
    - LLM Provider (генерация контента)
    """

    def __init__(
        self,
        llm_provider: Any,
        data_repository: DataRepository,
        data_dir: Path
    ):
        self.llm_provider = llm_provider
        self.data_repository = data_repository
        self.data_dir = data_dir
```

---

## 🤖 Выбор LLM для анализа и улучшения промптов/контрактов

### ❓ Какую LLM использовать?

**Ответ:** Зависит от **задачи** и **бюджета**. Рекомендуется **разделение по задачам**:

```
┌─────────────────────────────────────────────────────────────┐
│              СТРАТЕГИЯ ВЫБОРА LLM                           │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │  Тип задачи?    │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Генерация    │   │  Анализ       │   │  Оценка       │
│  промптов     │   │  ошибок       │   │  (accuracy)   │
│               │   │               │   │               │
│ → МОЩНАЯ LLM  │   │ → LLM средней │   │ → LLM средней │
│   (GPT-4,     │   │   мощности    │   │   мощности    │
│   Claude 3)   │   │   (GPT-3.5,   │   │   (GPT-3.5,   │
│               │   │    Claude)    │   │    Claude)    │
└───────────────┘   └───────────────┘   └───────────────┘
```

---

### 📊 Рекомендуемая конфигурация

#### Вариант 1: Разные LLM для разных задач (рекомендуется)

```python
# core/config/llm_config.py

class LLMConfig:
    """Конфигурация LLM для разных задач"""
    
    # 1. ГЕНЕРАЦИЯ ПРОМПТОВ (критичная задача)
    PROMPT_GENERATION = {
        'provider': 'openai',
        'model': 'gpt-4-turbo-preview',
        'temperature': 0.7,      # Баланс креативности/точности
        'max_tokens': 4000,
        'top_p': 0.9,
        'frequency_penalty': 0.3,
        'presence_penalty': 0.3
    }
    
    # 2. АНАЛИЗ ОШИБОК (средняя важность)
    FAILURE_ANALYSIS = {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo-16k',  # Дешевле, но достаточно
        'temperature': 0.5,      # Более детерминировано
        'max_tokens': 2000,
    }
    
    # 3. ОЦЕНКА ACCURACY (много вызовов)
    ACCURACY_EVALUATION = {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo',  # Самый дешёвый
        'temperature': 0.3,      # Минимум вариативности
        'max_tokens': 500,
    }
    
    # 4. ГЕНЕРАЦИЯ КОНТРАКТОВ (требует точности)
    CONTRACT_GENERATION = {
        'provider': 'openai',
        'model': 'gpt-4-turbo-preview',
        'temperature': 0.5,      # Меньше креативности
        'max_tokens': 3000,
    }
```

**Почему так:**

| Задача | LLM | Почему | Стоимость (1K токенов) |
|--------|-----|--------|------------------------|
| Генерация промптов | GPT-4 Turbo | Требует креативности и понимания контекста | $0.01 |
| Анализ ошибок | GPT-3.5 | Достаточно для классификации | $0.001 |
| Оценка accuracy | GPT-3.5 | Много вызовов, нужна скорость | $0.001 |
| Генерация контрактов | GPT-4 Turbo | Требует точности (JSON Schema) | $0.01 |

---

#### Вариант 2: Единая LLM для всех задач (проще)

```python
# core/config/llm_config.py

class LLMConfig:
    """Единая LLM для всех задач"""
    
    DEFAULT = {
        'provider': 'openai',
        'model': 'gpt-4-turbo-preview',  # Универсальный выбор
        'temperature': 0.7,
        'max_tokens': 4000,
    }
```

**Плюсы:**
- ✅ Проще в настройке
- ✅ Меньше зависимостей
- ✅ Консистентные результаты

**Минусы:**
- ❌ Дороже (все вызовы по $0.01/1K)
- ❌ Медленнее (GPT-4 медленнее GPT-3.5)
- ❌ Overkill для простых задач

---

#### Вариант 3: Локальная LLM (для экономии)

```python
# core/config/llm_config.py

class LLMConfig:
    """Локальная LLM для экономии"""
    
    # Генерация промптов (требует качества)
    PROMPT_GENERATION = {
        'provider': 'vllm',
        'model': 'meta-llama/Llama-3-70B-Instruct',
        'temperature': 0.7,
        'max_tokens': 4000,
        'gpu_memory_utilization': 0.9,
    }
    
    # Анализ ошибок (достаточно меньшей модели)
    FAILURE_ANALYSIS = {
        'provider': 'vllm',
        'model': 'meta-llama/Llama-3-8B-Instruct',
        'temperature': 0.5,
        'max_tokens': 2000,
    }
```

**Плюсы:**
- ✅ Дешевле (нет оплаты за токены)
- ✅ Контроль над данными
- ✅ Нет rate limits

**Минусы:**
- ❌ Требует GPU (70B → ~140GB VRAM)
- ❌ Сложнее в настройке
- ❌ Качество может быть ниже

---

### 📋 Сравнение LLM для задач

| Задача | GPT-4 Turbo | GPT-3.5 | Claude 3 | Llama-3-70B |
|--------|-------------|---------|----------|-------------|
| **Генерация промптов** | ✅ Отлично | ⚠️ Средне | ✅ Отлично | ⚠️ Средне |
| **Анализ ошибок** | ✅ Отлично | ✅ Хорошо | ✅ Отлично | ✅ Хорошо |
| **Оценка accuracy** | ✅ Отлично | ✅ Хорошо | ✅ Отлично | ⚠️ Нестабильно |
| **Генерация контрактов** | ✅ Отлично | ⚠️ Средне | ✅ Отлично | ⚠️ Средне |
| **Стоимость** | $$$$ | $ | $$$ | $ (GPU) |
| **Скорость** | Средняя | Быстрая | Средняя | Зависит от GPU |

---

### 💡 Рекомендации

#### Для продакшена:

```python
# Оптимальная конфигурация
LLM_CONFIG = {
    'prompt_generation': {
        'provider': 'openai',
        'model': 'gpt-4-turbo-preview',
        'temperature': 0.7,
    },
    'failure_analysis': {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo-16k',
        'temperature': 0.5,
    },
    'accuracy_evaluation': {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo',
        'temperature': 0.3,
    },
    'contract_generation': {
        'provider': 'openai',
        'model': 'gpt-4-turbo-preview',
        'temperature': 0.5,
    }
}
```

**Ожидаемая стоимость на цикл оптимизации:**
```
1 цикл = 10 итераций × (1 генерация + 1 анализ + 5 оценок)

Генерация промпта: 10 × 3000 токенов × $0.01 = $0.30
Анализ ошибок: 10 × 1000 токенов × $0.001 = $0.01
Оценка accuracy: 50 × 500 токенов × $0.001 = $0.025

Итого: ~$0.34 за цикл оптимизации
```

---

#### Для разработки/тестирования:

```python
# Бюджетная конфигурация
LLM_CONFIG = {
    'prompt_generation': {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo',  # Дешевле
        'temperature': 0.7,
    },
    'failure_analysis': {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo',
        'temperature': 0.5,
    },
    'accuracy_evaluation': {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo',
        'temperature': 0.3,
    },
    'contract_generation': {
        'provider': 'openai',
        'model': 'gpt-3.5-turbo',
        'temperature': 0.5,
    }
}
```

**Ожидаемая стоимость:**
```
Итого: ~$0.05 за цикл оптимизации (в 7 раз дешевле!)
```

---

### 🔧 Реализация переключения LLM

```python
# core/application/services/llm_router.py

class LLMRouter:
    """
    Маршрутизатор LLM вызовов.
    
    Выбирает LLM на основе задачи.
    """

    def __init__(self, config: Dict[str, Dict[str, Any]]):
        self.config = config
        self._providers = self._init_providers()

    def _init_providers(self) -> Dict[str, Any]:
        """Инициализация провайдеров"""
        providers = {}
        
        for task_name, task_config in self.config.items():
            provider_name = task_config['provider']
            
            if provider_name == 'openai':
                from openai import AsyncOpenAI
                providers[task_name] = AsyncOpenAI()
            elif provider_name == 'vllm':
                from vllm import AsyncLLMEngine
                providers[task_name] = AsyncLLMEngine(task_config)
            elif provider_name == 'anthropic':
                from anthropic import AsyncAnthropic
                providers[task_name] = AsyncAnthropic()
        
        return providers

    async def generate(
        self,
        task: str,  # 'prompt_generation', 'failure_analysis', etc.
        prompt: str,
        **kwargs
    ) -> str:
        """
        Генерация через соответствующую LLM.
        
        ARGS:
        - task: тип задачи
        - prompt: промпт для генерации
        - kwargs: дополнительные параметры
        
        RETURNS:
        - str: результат генерации
        """
        if task not in self.config:
            raise ValueError(f"Неизвестная задача: {task}")
        
        task_config = self.config[task]
        provider = self._providers[task]
        
        # Объединение конфигурации с overrides
        full_config = {**task_config, **kwargs}
        
        if task_config['provider'] == 'openai':
            response = await provider.chat.completions.create(
                model=full_config['model'],
                messages=[{'role': 'user', 'content': prompt}],
                temperature=full_config.get('temperature', 0.7),
                max_tokens=full_config.get('max_tokens', 4000),
            )
            return response.choices[0].message.content
        
        elif task_config['provider'] == 'anthropic':
            response = await provider.messages.create(
                model=full_config['model'],
                max_tokens=full_config.get('max_tokens', 4000),
                messages=[{'role': 'user', 'content': prompt}],
            )
            return response.content[0].text
        
        # ... другие провайдеры
```

---

### Пример использования

```python
# core/application/services/prompt_contract_generator.py

class PromptContractGenerator(BaseService):
    def __init__(
        self,
        llm_router: LLMRouter,  # ← Вместо llm_provider
        data_repository: DataRepository,
        data_dir: Path
    ):
        self.llm_router = llm_router
        self.data_repository = data_repository
        self.data_dir = data_dir

    async def generate_prompt_variant(...) -> str:
        # ... анализ неудач ...
        
        # 3. Генерируем новый промпт через LLM
        new_content = await self.llm_router.generate(
            task='prompt_generation',  # ← Указываем задачу
            prompt=self._build_generation_prompt(...)
        )
        
        return new_version

    async def _generate_input_schema(self, prompt: Prompt) -> Dict[str, Any]:
        """Генерация входной схемы через LLM"""
        response = await self.llm_router.generate(
            task='contract_generation',  # ← Другая задача
            prompt=f"Создай JSON Schema: {prompt.content[:500]}..."
        )
        return json.loads(response)
```

---

### 📊 Итоговая рекомендация

| Сценарий | Конфигурация | Стоимость/цикл | Качество |
|----------|--------------|----------------|----------|
| **Продакшен** | GPT-4 Turbo + GPT-3.5 | $0.34 | ⭐⭐⭐⭐⭐ |
| **Разработка** | GPT-3.5 (везде) | $0.05 | ⭐⭐⭐⭐ |
| **Эконом** | Llama-3-70B + 8B | $0.01 (GPU) | ⭐⭐⭐ |
| **Гибрид** | GPT-4 (генерация) + Llama (анализ) | $0.15 | ⭐⭐⭐⭐ |

**Рекомендация:**
- **Старт:** GPT-3.5 для всех задач (дешево, достаточно для тестов)
- **Продакшен:** GPT-4 Turbo для генерации + GPT-3.5 для анализа/оценки
- **Эконом:** Llama-3-70B для генерации + 8B для анализа

---

## 🔧 Работа с несколькими LLM в InfraContext

### ❓ Поддерживает ли InfraContext несколько LLM?

**Ответ:** ✅ **ДА!** InfraContext регистрирует **все включённые LLM провайдеры** из конфигурации.

---

### 📋 Конфигурация нескольких LLM

**registry.yaml:**

```yaml
llm_providers:
  primary_llm:           # ← Имя провайдера
    enabled: true
    provider_type: llama_cpp
    parameters:
      model_path: "models/llama-3-70b.gguf"
  
  backup_llm:
    enabled: true
    provider_type: mock
    parameters:
      model_name: "gpt-4"
  
  cheap_llm:
    enabled: true
    provider_type: mock
    parameters:
      model_name: "gpt-3.5-turbo"
```

**При инициализации:**
- Все `enabled: true` провайдеры регистрируются в `ResourceRegistry`
- Первый успешный провайдер становится **default** (`is_default=True`)
- Доступ к каждому провайдеру по **имени**

---

### 🔧 Как получить доступ к конкретной LLM

#### Способ 1: `call_llm(request, provider_name)` — через InfraContext (рекомендуется)

```python
from core.infrastructure.context.infrastructure_context import InfrastructureContext

# Инициализация
infra = await InfrastructureContext.create(config)

# Default LLM (без указания провайдера)
response = await infra.call_llm("Привет!")

# Конкретная LLM по имени
response = await infra.call_llm(
    "Создай план",
    provider_name='primary_llm'
)

# Конкретная LLM без fallback
response = await infra.call_llm(
    "Создай план",
    provider_name='primary_llm',
    fallback=False
)
```

**Параметры `call_llm`:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `request` | str | — | Запрос к LLM |
| `provider_name` | str | None | Имя провайдера (если None → default) |
| `fallback` | bool | True | Использовать backup при ошибке |

**Логика работы:**

```
1. provider_name указан?
   ├─ ДА → Попытка получить провайдер по имени
   │      ├─ Успех → Использовать этот провайдер
   │      └─ Неудача → Переход к шагу 2 (если fallback=True)
   └─ НЕТ → Переход к шагу 2

2. Есть default LLM?
   ├─ ДА → Использовать default
   └─ НЕТ → Переход к шагу 3

3. Есть первый доступный LLM?
   ├─ ДА → Использовать первый доступный
   └─ НЕТ → Ошибка "Нет доступных LLM провайдеров"

4. При ошибке генерации (если fallback=True):
   └─ Попытка использовать backup LLM
```

**Преимущества `call_llm`:**
- ✅ Автоматический fallback на backup
- ✅ Градация: provider → default → first available
- ✅ Логирование всех шагов
- ✅ Простой интерфейс

---

#### Способ 2: `get_resource(name)` — универсальный

```python
# Универсальный метод для любого ресурса
llm = infra.get_resource('primary_llm')
response = await llm.generate(prompt)
```

---

#### Способ 3: `call_llm(request)` — только default LLM

```python
# Вызов LLM по умолчанию (первый зарегистрированный)
response = await infra.call_llm(prompt)
```

**Важно:** Использует только default LLM, не подходит для выбора конкретной.

---

#### Способ 4: Через `resource_registry` — все провайдеры

```python
# Получить все LLM провайдеры
from core.models.enums.common_enums import ResourceType

llm_providers = infra.resource_registry.get_resources_by_type(
    ResourceType.LLM_PROVIDER
)

# Итерация по всем
for name, resource_info in llm_providers.items():
    llm = resource_info.instance
    print(f"{name}: is_default={resource_info.is_default}")

# Получить default LLM
default_llm = infra.resource_registry.get_default_resource(
    ResourceType.LLM_PROVIDER
)
```

---

### 💡 Пример: Выбор LLM для задачи

```python
# core/application/services/prompt_contract_generator.py

class PromptContractGenerator(BaseService):
    def __init__(
        self,
        infra_context: InfrastructureContext,
        data_repository: DataRepository,
        data_dir: Path
    ):
        self.infra = infra_context
        self.data_repository = data_repository
        self.data_dir = data_dir
        
        # ← Явное получение LLM для разных задач
        self.powerful_llm = infra.get_provider('primary_llm')   # Для генерации
        self.cheap_llm = infra.get_provider('cheap_llm')       # Для анализа
        self.backup_llm = infra.get_provider('backup_llm')     # Fallback

    async def generate_prompt_variant(self, ...) -> str:
        """Генерация промпта → используем мощную LLM"""
        try:
            new_content = await self.powerful_llm.generate(
                prompt=self._build_generation_prompt(...)
            )
        except Exception:
            # Fallback на backup при ошибке
            new_content = await self.backup_llm.generate(...)
        
        return new_content

    async def _analyze_failures(self, failure_analysis: FailureAnalysis) -> List[str]:
        """Анализ ошибок → используем дешёвую LLM"""
        response = await self.cheap_llm.generate(
            prompt=f"Проанализируй ошибки: {failure_analysis}"
        )
        return response.strip().split('\n')

    async def _generate_input_schema(self, prompt: Prompt) -> Dict[str, Any]:
        """Генерация контракта → используем мощную LLM"""
        response = await self.powerful_llm.generate(
            prompt=f"Создай JSON Schema: {prompt.content[:500]}..."
        )
        return json.loads(response)
```

---

### 🎯 Как указать задачу для конкретной LLM

```python
# Явное указание LLM по имени
llm_name = 'primary_llm'  # или 'cheap_llm', 'backup_llm'
llm = infra_context.get_provider(llm_name)

if llm is None:
    raise ValueError(f"LLM провайдер '{llm_name}' не найден")

# Генерация через выбранную LLM
response = await llm.generate(prompt)
```

---

### 📊 Методы InfraContext для работы с LLM

| Метод | Описание | Параметры | Возвращает | Пример |
|-------|----------|-----------|------------|--------|
| `call_llm(request, provider_name, fallback)` | **Универсальный вызов LLM** | request, provider_name=None, fallback=True | str | `call_llm("Привет!", provider_name='primary_llm')` |
| `get_provider(name)` | Получение провайдера по имени | name | BaseLLMProvider | `get_provider('primary_llm')` |
| `get_resource(name)` | Универсальное получение | name | Any | `get_resource('cheap_llm')` |
| `resource_registry.get_resources_by_type()` | Все провайдеры типа | resource_type | Dict[str, ResourceInfo] | `get_resources_by_type(LLM_PROVIDER)` |
| `resource_registry.get_default_resource()` | Default провайдер | resource_type | ResourceInfo | `get_default_resource(LLM_PROVIDER)` |

---

### 📋 Сценарии использования

#### Сценарий 1: Простой вызов (default LLM)

```python
# Используем LLM по умолчанию
response = await infra.call_llm("Создай план проекта")
```

#### Сценарий 2: Вызов конкретной LLM

```python
# Генерация промпта → мощная LLM
prompt = await infra.call_llm(
    "Улучши этот промпт: ...",
    provider_name='primary_llm'
)

# Анализ ошибок → дешёвая LLM
analysis = await infra.call_llm(
    "Проанализируй ошибки: ...",
    provider_name='cheap_llm'
)
```

#### Сценарий 3: Вызов с fallback

```python
# Попытка через primary, при ошибке → backup
try:
    response = await infra.call_llm(
        "Создай план",
        provider_name='primary_llm',
        fallback=True  # ← Автоматический fallback
    )
except RuntimeError as e:
    # Все LLM недоступны
    logger.error(f"Все LLM не доступны: {e}")
```

#### Сценарий 4: Вызов без fallback

```python
# Только конкретная LLM, без fallback
try:
    response = await infra.call_llm(
        "Создай план",
        provider_name='primary_llm',
        fallback=False  # ← Только primary_llm
    )
except Exception as e:
    # Обработка ошибки primary_llm
    logger.error(f"Primary LLM failed: {e}")
```

#### Сценарий 5: Прямой доступ к провайдеру

```python
# Для сложных сценариев (несколько вызовов, streaming, etc.)
llm = infra.get_provider('primary_llm')

# Несколько вызовов
response1 = await llm.generate("Запрос 1")
response2 = await llm.generate("Запрос 2")

# Streaming
async for chunk in llm.generate_stream("Большой запрос"):
    print(chunk, end='')
```

---

### 🔄 Fallback стратегия

```python
async def generate_with_fallback(self, prompt: str) -> str:
    """
    Генерация с fallback на backup LLM.
    
    СТРАТЕГИЯ:
    1. Попытка через primary_llm
    2. При ошибке → backup_llm
    3. При ошибке → исключение
    """
    # Попытка 1: Primary
    try:
        return await self.powerful_llm.generate(prompt)
    except Exception as e:
        self.logger.warning(f"Primary LLM failed: {e}")
    
    # Попытка 2: Backup
    try:
        return await self.backup_llm.generate(prompt)
    except Exception as e:
        self.logger.error(f"Backup LLM failed: {e}")
    
    raise RuntimeError("Все LLM провайдеры недоступны")
```

---

### 📋 Чеклист: правильно ли настроены LLM

```
□ 1. В registry.yaml указано ≥ 2 LLM провайдеров
□ 2. У каждого провайдера уникальное имя
□ 3. Первый провайдер enabled: true (будет default)
□ 4. В коде используется get_provider('имя') для выбора
□ 5. Реализован fallback на backup при ошибке
□ 6. Для разных задач используются разные LLM
```

---

### 💡 Рекомендации

1. **Минимум 2 LLM:** primary + backup
2. **Именуйте явно:** `primary_llm`, `cheap_llm`, `backup_llm`
3. **Используйте fallback:** всегда обрабатывайте ошибки LLM
4. **Разделяйте задачи:** генерация → powerful, анализ → cheap
5. **Проверяйте доступность:** `if llm is None: raise ValueError(...)`

    async def generate_prompt_variant(
        self,
        capability: str,
        base_version: str,
        optimization_goal: str,
        failure_analysis: FailureAnalysis
    ) -> str:
        """Генерирует новую версию промпта"""

        # 1. Загружаем текущий промпт через DataRepository
        current_prompt = self.data_repository.get_prompt(capability, base_version)

        # 2. Анализируем неудачи
        failure_patterns = await self._analyze_failures(failure_analysis)

        # 3. Генерируем новый промпт через LLM
        new_content = await self.llm_provider.generate(
            prompt=self._build_generation_prompt(
                current_content=current_prompt.content,
                failure_patterns=failure_patterns,
                optimization_goal=optimization_goal
            )
        )

        # 4. Создаём новую версию (draft)
        new_version = self._calculate_next_version(base_version, 'minor')

        new_prompt = Prompt(
            capability=capability,
            version=new_version,
            status=PromptStatus.DRAFT,  # ← Важно: только DRAFT
            component_type=current_prompt.component_type,
            content=new_content,
            variables=current_prompt.variables,
            metadata={
                **current_prompt.metadata,
                'generated_from': base_version,
                'optimization_goal': optimization_goal,
                'generated_at': datetime.now().isoformat()
            }
        )

        # 5. Сохраняем в файловую систему
        await self._save_prompt(new_prompt)

        # 6. Генерируем соответствующий контракт (если нужно)
        await self._generate_matching_contract(new_prompt)

        return new_version

    async def _save_prompt(self, prompt: Prompt) -> Path:
        """
        Сохранение промпта в файловую систему.
        
        ФОРМАТ:
        data/prompts/{component_type}/{capability_path}/{name}_{version}.yaml
        
        ПРИМЕР:
        data/prompts/skills/planning/create_plan_v1.1.0.yaml
        """
        # 1. Определяем путь
        capability_path = prompt.capability.replace('.', '/')
        
        if prompt.component_type == ComponentType.SKILL:
            base_subdir = 'skills'
        elif prompt.component_type == ComponentType.SERVICE:
            base_subdir = 'services'
        elif prompt.component_type == ComponentType.TOOL:
            base_subdir = 'tools'
        else:
            base_subdir = 'prompts'
        
        # 2. Создаём директорию
        prompt_dir = self.data_dir / base_subdir / capability_path
        prompt_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Определяем имя файла
        # Формат: {last_part_of_capability}_{version}.yaml
        capability_parts = prompt.capability.split('.')
        file_name = f"{capability_parts[-1]}_{prompt.version}.yaml"
        prompt_file = prompt_dir / file_name
        
        # 4. Сериализуем в YAML
        yaml_data = {
            'capability': prompt.capability,
            'version': prompt.version,
            'status': prompt.status.value,
            'component_type': prompt.component_type.value,
            'content': prompt.content,
            'variables': [v.model_dump() for v in prompt.variables],
            'metadata': prompt.metadata
        }
        
        # 5. Записываем файл
        import yaml
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return prompt_file

    async def _generate_matching_contract(self, prompt: Prompt) -> Optional[Path]:
        """
        Генерация контракта для промпта.
        
        СОЗДАЁТ:
        - Входной контракт (input schema)
        - Выходной контракт (output schema)
        """
        # Генерация схем через LLM
        input_schema = await self._generate_input_schema(prompt)
        output_schema = await self._generate_output_schema(prompt)
        
        # Сохранение контрактов
        input_contract = Contract(
            capability=prompt.capability,
            version=prompt.version,
            status=PromptStatus.DRAFT,
            component_type=prompt.component_type,
            direction=ContractDirection.INPUT,
            schema_data=input_schema,
            description=f"Input contract for {prompt.capability}"
        )
        
        output_contract = Contract(
            capability=prompt.capability,
            version=prompt.version,
            status=PromptStatus.DRAFT,
            component_type=prompt.component_type,
            direction=ContractDirection.OUTPUT,
            schema_data=output_schema,
            description=f"Output contract for {prompt.capability}"
        )
        
        # Сохранение
        await self._save_contract(input_contract)
        await self._save_contract(output_contract)
        
        return prompt_file

    async def _save_contract(self, contract: Contract) -> Path:
        """Сохранение контракта в файловую систему"""
        capability_path = contract.capability.replace('.', '/')
        
        if contract.component_type == ComponentType.SKILL:
            base_subdir = 'skills'
        else:
            base_subdir = 'contracts'
        
        contract_dir = self.data_dir / base_subdir / capability_path
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        contract_parts = contract.capability.split('.')
        direction_suffix = contract.direction.value  # 'input' или 'output'
        file_name = f"{contract_parts[-1]}_{contract.version}_{direction_suffix}.yaml"
        contract_file = contract_dir / file_name
        
        yaml_data = {
            'capability': contract.capability,
            'version': contract.version,
            'status': contract.status.value,
            'component_type': contract.component_type.value,
            'direction': contract.direction.value,
            'schema_data': contract.schema_data,
            'description': contract.description
        }
        
        import yaml
        with open(contract_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return contract_file

    def _calculate_next_version(self, base_version: str, bump_type: str) -> str:
        """
        Расчёт следующей версии.
        
        ПРИМЕРЫ:
        - v1.0.0 + minor → v1.1.0
        - v1.0.0 + major → v2.0.0
        - v1.0.0 + patch → v1.0.1
        """
        import re
        match = re.match(r'v(\d+)\.(\d+)\.(\d+)', base_version)
        if not match:
            return 'v1.0.0'
        
        major, minor, patch = map(int, match.groups())
        
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        else:  # patch
            patch += 1
        
        return f'v{major}.{minor}.{patch}'

    async def _analyze_failures(self, failure_analysis: FailureAnalysis) -> List[str]:
        """Извлечение паттернов неудач для генерации улучшений"""
        patterns = []
        
        for error_pattern in failure_analysis.error_patterns:
            patterns.append(f"- Тип ошибки: {error_pattern['type']}")
            patterns.append(f"  Количество: {error_pattern['count']}")
            if error_pattern.get('examples'):
                patterns.append(f"  Примеры: {error_pattern['examples'][:2]}")

        return patterns

    def _build_generation_prompt(
        self,
        current_content: str,
        failure_patterns: List[str],
        optimization_goal: str
    ) -> str:
        """Создание промпта для генерации улучшенной версии"""
        return f"""
Улучши промпт для агента.

Текущий промпт:
{current_content}

Выявленные проблемы:
{chr(10).join(failure_patterns)}

Цель оптимизации:
{optimization_goal}

Сгенерируй улучшенную версию промпта:
1. Сохрани структуру и переменные
2. Устраняй выявленные проблемы
3. Добавь конкретные инструкции для улучшения качества
4. Оптимизируй для {optimization_goal}

Новый промпт:
"""

    async def _generate_input_schema(self, prompt: Prompt) -> Dict[str, Any]:
        """Генерация входной схемы через LLM"""
        response = await self.llm_provider.generate(f"""
Создай JSON Schema для входных данных промпта:

Промпт:
{prompt.content[:500]}...

Переменные:
{prompt.variables}

Верни JSON Schema:
""")
        return json.loads(response)

    async def _generate_output_schema(self, prompt: Prompt) -> Dict[str, Any]:
        """Генерация выходной схемы через LLM"""
        response = await self.llm_provider.generate(f"""
Создай JSON Schema для выходных данных промпта:

Промпт:
{prompt.content[:500]}...

Ожидаемый результат:
{prompt.metadata.get('expected_output', 'Не указано')}

Верни JSON Schema:
""")
        return json.loads(response)
```

---

## 📝 Как именно улучшается промпт

### Процесс улучшения (step-by-step)

```
┌─────────────────────────────────────────────────────────────┐
│              ЦИКЛ УЛУЧШЕНИЯ ПРОМПТА                         │
└─────────────────────────────────────────────────────────────┘

1. АНАЛИЗ ТЕКУЩЕГО ПРОМПТА
   └→ Загрузка Prompt(capability, version)
   └→ Извлечение: content, variables, metadata

2. ВЫЯВЛЕНИЕ ПРОБЛЕМ (Failure Analysis)
   └→ Сбор error logs за 7 дней
   └→ Группировка по типам ошибок
   └→ Подсчёт частоты ошибок
   └→ Извлечение примеров

3. ФОРМИРОВАНИЕ PROMPT ДЛЯ LLM
   └→ Шаблон: _build_generation_prompt()
   └→ Включение:
      * Текущий content промпта
      * Список проблем (failure_patterns)
      * Цель оптимизации (optimization_goal)

4. LLM ГЕНЕРАЦИЯ
   └→ Вызов: llm_provider.generate(prompt)
   └→ Температура: 0.7 (баланс креативности/точности)
   └→ Max tokens: 4000

5. ВАЛИДАЦИЯ РЕЗУЛЬТАТА
   └→ Проверка структуры (переменные сохранены)
   └→ Проверка длины (не короче оригинала на 50%)
   └→ Проверка Jinja2 шаблона

6. СОХРАНЕНИЕ НОВОЙ ВЕРСИИ
   └→ Расчёт версии: v1.0.0 → v1.1.0 (minor bump)
   └→ Статус: DRAFT
   └→ Сохранение в data/prompts/...
```

---

### Детальный пример улучшения промпта

#### ДО (текущий промпт):

```yaml
# data/prompts/skills/planning/create_plan_v1.0.0.yaml
capability: planning.create_plan
version: v1.0.0
status: active
content: |
  Ты — агент планирования. Создай план для задачи.
  
  Задача: {{task}}
  
  Создай план с шагами.
  
variables:
  - name: task
    description: Описание задачи
    required: true
```

#### Проблемы (из Failure Analysis):

```python
failure_patterns = [
    {
        'type': 'ContractValidationError',
        'count': 10,
        'examples': [
            'missing field: description in step',
            'missing field: estimate in step'
        ]
    },
    {
        'type': 'IncompletePlanError',
        'count': 5,
        'examples': [
            'plan has only 2 steps, expected at least 5',
            'steps lack detailed descriptions'
        ]
    }
]
```

#### PROMPT для LLM (генерация улучшения):

```
Улучши промпт для агента.

Текущий промпт:
Ты — агент планирования. Создай план для задачи.

Задача: {{task}}

Создай план с шагами.

Выявленные проблемы:
- Тип ошибки: ContractValidationError (10 случаев)
  Примеры: ['missing field: description in step', 'missing field: estimate in step']
- Тип ошибки: IncompletePlanError (5 случаев)
  Примеры: ['plan has only 2 steps, expected at least 5']

Цель оптимизации:
Улучшить точность и снизить ошибки валидации

Сгенерируй улучшенную версию промпта:
1. Сохрани структуру и переменные
2. Устраняй выявленные проблемы
3. Добавь конкретные инструкции для улучшения качества
4. Оптимизируй для "Улучшить точность и снизить ошибки валидации"

Новый промпт:
```

#### ПОСЛЕ (улучшенный промпт):

```yaml
# data/prompts/skills/planning/create_plan_v1.1.0.yaml
capability: planning.create_plan
version: v1.1.0
status: draft
content: |
  Ты — опытный агент планирования проектов. Твоя задача — создать детальный, 
  выполнимый план для заданной задачи.
  
  Задача: {{task}}
  
  ИНСТРУКЦИИ:
  1. Создай план consisting of МИНИМУМ 5 шагов
  2. Каждый шаг ДОЛЖЕН включать:
     - name: Краткое название шага (2-5 слов)
     - description: Подробное описание (минимум 2 предложения)
     - estimate: Оценка времени в часах (число)
     - dependencies: Список зависимостей (может быть пустым)
  3. Убедись, что шаги логически связаны
  4. Избегай дублирования между шагами
  
  ФОРМАТ ОТВЕТА:
  {
    "steps": [
      {
        "name": "...",
        "description": "...",
        "estimate": 0,
        "dependencies": []
      }
    ]
  }
  
  ВАЖНО:
  - Минимум 5 шагов
  - Каждый шаг с description и estimate
  - Описание должно быть конкретным и actionable
  
  Начни планирование:
variables:
  - name: task
    description: Описание задачи
    required: true
metadata:
  generated_from: v1.0.0
  optimization_goal: Улучшить точность и снизить ошибки валидации
  generated_at: '2026-02-17T10:30:00'
```

---

### Что изменилось в улучшенной версии:

| Аспект | v1.0.0 | v1.1.0 | Почему |
|--------|--------|--------|--------|
| **Роль** | "Ты — агент планирования" | "Ты — опытный агент планирования проектов" | Более конкретная роль |
| **Минимум шагов** | Не указано | "МИНИМУМ 5 шагов" | Исправляет IncompletePlanError |
| **Структура шага** | Не указана | name, description, estimate, dependencies | Исправляет ContractValidationError |
| **Описание** | Не указано | "Подробное описание (минимум 2 предложения)" | Улучшает качество |
| **Формат ответа** | Не указан | JSON с примером | Упрощает валидацию |
| **Важно** | Нет | Блок с ключевыми требованиями | Акцентирует внимание |

---

### Техники улучшения промптов

#### 1. Добавление конкретных инструкций

```yaml
# БЫЛО:
Создай план с шагами.

# СТАЛО:
1. Создай план consisting of МИНИМУМ 5 шагов
2. Каждый шаг ДОЛЖЕН включать:
   - name: Краткое название шага (2-5 слов)
   - description: Подробное описание (минимум 2 предложения)
   - estimate: Оценка времени в часах (число)
```

#### 2. Добавление формата ответа

```yaml
# БЫЛО:
(нет формата)

# СТАЛО:
ФОРМАТ ОТВЕТА:
{
  "steps": [
    {
      "name": "...",
      "description": "...",
      "estimate": 0,
      "dependencies": []
    }
  ]
}
```

#### 3. Добавление ограничений

```yaml
# БЫЛО:
(нет ограничений)

# СТАЛО:
ВАЖНО:
- Минимум 5 шагов
- Каждый шаг с description и estimate
- Описание должно быть конкретным и actionable
```

#### 4. Улучшение роли

```yaml
# БЫЛО:
Ты — агент планирования.

# СТАЛО:
Ты — опытный агент планирования проектов. Твоя задача — создать детальный, 
выполнимый план для заданной задачи.
```

---

### Автоматическая валидация улучшенного промпта

```python
async def _validate_improved_prompt(
    original_prompt: Prompt,
    new_prompt: Prompt
) -> Tuple[bool, List[str]]:
    """
    Валидация улучшенного промпта.
    
    RETURNS:
    - bool: True если валидация пройдена
    - List[str]: список ошибок
    """
    errors = []
    
    # 1. Проверка: переменные сохранены
    original_vars = {v.name for v in original_prompt.variables}
    new_vars = {v.name for v in new_prompt.variables}
    
    if original_vars != new_vars:
        missing = original_vars - new_vars
        extra = new_vars - original_vars
        if missing:
            errors.append(f"Удалены переменные: {missing}")
        if extra:
            errors.append(f"Добавлены переменные: {extra}")
    
    # 2. Проверка: длина не уменьшилась на 50%+
    if len(new_prompt.content) < len(original_prompt.content) * 0.5:
        errors.append("Промпт стал слишком коротким (>50% сокращение)")
    
    # 3. Проверка: Jinja2 шаблон валиден
    try:
        from jinja2 import Environment
        env = Environment()
        env.parse(new_prompt.content)
    except Exception as e:
        errors.append(f"Ошибка Jinja2 шаблона: {e}")
    
    # 4. Проверка: есть конкретные инструкции
    instruction_keywords = ['должен', 'минимум', 'максимум', 'обязательно', 'важно']
    has_instructions = any(
        keyword in new_prompt.content.lower()
        for keyword in instruction_keywords
    )
    if not has_instructions:
        errors.append("Нет конкретных инструкций в промпте")
    
    return len(errors) == 0, errors
```

---

## 📝 Как именно улучшается контракт

### Процесс улучшения контрактов

```
┌─────────────────────────────────────────────────────────────┐
│              ЦИКЛ УЛУЧШЕНИЯ КОНТРАКТА                       │
└─────���───────────────────────────────────────────────────────┘

1. АНАЛИЗ ТЕКУЩЕГО КОНТРАКТА
   └→ Загрузка Contract(capability, version, direction)
   └→ Извлечение: schema_data, description

2. ВЫЯВЛЕНИЕ ПРОБЛЕМ
   └→ ContractValidationError: какие поля часто missing
   └→ TypeValidationError: какие поля часто wrong type
   └→ Извлечение паттернов из error logs

3. LLM ГЕНЕРАЦИЯ УЛУЧШЕННОЙ СХЕМЫ
   └→ Prompt: "Улучши JSON Schema с учётом ошибок"
   └→ Вход: текущая schema + failure patterns
   └→ Выход: улучшенная JSON Schema

4. ДОБАВЛЕНИЕ ОГРАНИЧЕНИЙ
   └→ required: добавление обязательных полей
   └→ minLength/maxLength: для строк
   └→ minimum/maximum: для чисел
   └→ pattern: regex для форматирования

5. ВАЛИДАЦИЯ СХЕМЫ
   └→ Проверка JSON Schema Draft 7
   └→ Проверка: схема не слишком строгая
   └→ Проверка: схема не слишком слабая

6. СОХРАНЕНИЕ НОВОЙ ВЕРСИИ
   └→ Версия: v1.0.0 → v1.1.0
   └→ Статус: DRAFT
   └→ Сохранение в data/contracts/...
```

---

### Детальный пример улучшения контракта

#### ДО (текущий входной контракт):

```yaml
# data/contracts/skills/planning/create_plan_v1.0.0_input.yaml
capability: planning.create_plan
version: v1.0.0
status: active
direction: input
schema_data:
  type: object
  properties:
    task:
      type: string
  required:
    - task
description: "Входной контракт для планирования"
```

#### Проблемы (из Failure Analysis):

```python
# Из error logs:
error_patterns = [
    {
        'type': 'ContractValidationError',
        'field': 'task',
        'issue': 'empty string',
        'count': 5
    },
    {
        'type': 'MissingContextError',
        'issue': 'no deadline provided',
        'count': 8
    },
    {
        'type': 'IncompletePlanError',
        'issue': 'plan quality too low',
        'count': 10
    }
]
```

#### PROMPT для LLM (генерация улучшения):

```
Улучши JSON Schema для входных данных промпта.

Текущая схема:
{
  "type": "object",
  "properties": {
    "task": {"type": "string"}
  },
  "required": ["task"]
}

Выявленные проблемы:
- Поле 'task' часто пустое (5 случаев)
- Отсутствует deadline (8 случаев)
- Низкое качество плана из-за недостатка контекста (10 случаев)

Создай улучшенную JSON Schema:
1. Добавь minLength для task
2. Добавь обязательное поле deadline
3. Добавь опциональные поля для контекста
4. Добавь описания для всех полей

Новая схема:
```

#### ПОСЛЕ (улучшенный входной контракт):

```yaml
# data/contracts/skills/planning/create_plan_v1.1.0_input.yaml
capability: planning.create_plan
version: v1.1.0
status: draft
direction: input
schema_data:
  type: object
  properties:
    task:
      type: string
      description: "Подробное описание задачи, которую нужно спланировать"
      minLength: 20
      maxLength: 2000
      examples:
        - "Разработать мобильное приложение для доставки еды с интеграцией платежных систем"
    
    deadline:
      type: string
      format: date-time
      description: "Дедлайн выполнения задачи (ISO 8601 формат)"
      examples:
        - "2026-03-01T00:00:00Z"
    
    priority:
      type: string
      enum: [low, medium, high, critical]
      description: "Приоритет задачи"
      default: "medium"
    
    constraints:
      type: array
      items:
        type: string
      description: "Список ограничений (бюджет, ресурсы, зависимости)"
      default: []
    
    context:
      type: object
      properties:
        budget:
          type: number
          description: "Бюджет проекта"
        team_size:
          type: integer
          description: "Размер команды"
        stakeholders:
          type: array
          items:
            type: string
          description: "Заинтересованные стороны"
      description: "Дополнительный контекст проекта"
  
  required:
    - task
    - deadline
  
  additionalProperties: false
description: "Входной контракт для планирования (улучшенная версия с валидацией)"
```

---

### Что изменилось в улучшенной версии:

| Аспект | v1.0.0 | v1.1.0 | Почему |
|--------|--------|--------|--------|
| **task validation** | `type: string` | `minLength: 20, maxLength: 2000` | Исправляет empty string |
| **deadline** | Отсутствует | `required, format: date-time` | Исправляет MissingContextError |
| **priority** | Отсутствует | `enum: [low, medium, high, critical]` | Добавляет контекст |
| **constraints** | Отсутствует | `array of strings` | Добавляет ограничения |
| **context** | Отсутствует | `object with budget, team_size` | Улучшает качество плана |
| **descriptions** | Отсутствуют | Есть для всех полей | Улучшает понимание |
| **examples** | Отсутствуют | Есть для task и deadline | Помогает агенту |
| **additionalProperties** | Разрешены | `false` | Строгая валидация |

---

### Техники улучшения контрактов

#### 1. Добавление валидации строк

```json
// БЫЛО:
{"task": {"type": "string"}}

// СТАЛО:
{
  "task": {
    "type": "string",
    "minLength": 20,
    "maxLength": 2000,
    "description": "Подробное описание задачи"
  }
}
```

#### 2. Добавление обязательных полей

```json
// БЫЛО:
"required": ["task"]

// СТАЛО:
"required": ["task", "deadline"]
```

#### 3. Добавление enum для строгости

```json
// БЫЛО:
{"priority": {"type": "string"}}

// СТАЛО:
{
  "priority": {
    "type": "string",
    "enum": ["low", "medium", "high", "critical"]
  }
}
```

#### 4. Добавление вложенных объектов

```json
// БЫЛО:
(нет контекста)

// СТАЛО:
{
  "context": {
    "type": "object",
    "properties": {
      "budget": {"type": "number"},
      "team_size": {"type": "integer"},
      "stakeholders": {"type": "array", "items": {"type": "string"}}
    }
  }
}
```

#### 5. Добавление examples

```json
// БЫЛО:
(нет примеров)

// СТАЛО:
{
  "task": {
    "type": "string",
    "examples": [
      "Разработать мобильное приложение для доставки еды"
    ]
  }
}
```

---

### Валидация улучшенного контракта

```python
async def _validate_improved_contract(
    original_contract: Contract,
    new_contract: Contract
) -> Tuple[bool, List[str]]:
    """
    Валидация улучшенного контракта.
    
    RETURNS:
    - bool: True если валидация пройдена
    - List[str]: список ошибок
    """
    errors = []
    
    # 1. Проверка: JSON Schema валидна
    try:
        from jsonschema import validators
        validator_cls = validators.validator_for(new_contract.schema_data)
        validator_cls.check_schema(new_contract.schema_data)
    except Exception as e:
        errors.append(f"Невалидная JSON Schema: {e}")
        return False, errors
    
    # 2. Проверка: required поля не удалены
    original_required = set(original_contract.schema_data.get('required', []))
    new_required = set(new_contract.schema_data.get('required', []))
    
    removed_required = original_required - new_required
    if removed_required:
        errors.append(f"Удалены required поля: {removed_required}")
    
    # 3. Проверка: схема не слишком строгая
    # (проверяем что есть хотя бы одно optional поле)
    all_properties = set(new_contract.schema_data.get('properties', {}).keys())
    if new_required == all_properties:
        errors.append("Схема слишком строгая (нет optional полей)")
    
    # 4. Проверка: есть описания полей
    properties = new_contract.schema_data.get('properties', {})
    fields_without_desc = [
        name for name, schema in properties.items()
        if 'description' not in schema
    ]
    if fields_without_desc:
        errors.append(f"Нет описаний у полей: {fields_without_desc}")
    
    return len(errors) == 0, errors
```

---

### Связь улучшения промпта и контракта

```
┌─────────────────────────────────────────────────────────────┐
│         СВЯЗЬ УЛУЧШЕНИЯ ПРОМПТА И КОНТРАКТА                 │
└─────────────────────────────────────────────────────────────┘

Промпт v1.0.0          Контракт v1.0.0
     │                       │
     │  Выявлены проблемы:   │
     │  - missing fields     │
     │  - empty strings      │
     │  - no deadline        │
     │                       │
     ▼                       ▼
┌─────────────────────────────────────────┐
│      LLM Генерация улучшений            │
│                                         │
│  Промпт:  Добавить инструкции           │
│  Контракт: Добавить валидацию           │
└─────────────────────────────────────────┘
     │                       │
     ▼                       ▼
Промпт v1.1.0          Контракт v1.1.0
- Минимум 5 шагов      - task: minLength 20
- Format ответа        - deadline: required
- Важные инструкции    - priority: enum
                       - context: object

     │                       │
     └───────────┬───────────┘
                 │
                 ▼
      A/B Тестирование обеих версий
      (промпт + контракт вместе!)
```

---

### Пример использования (полный цикл)

```python
# 1. Генерация улучшенного промпта
new_prompt_version = await generator.generate_prompt_variant(
    capability='planning.create_plan',
    base_version='v1.0.0',
    optimization_goal='Улучшить точность и снизить ошибки',
    failure_analysis=failure_analysis
)

# 2. Генерация улучшенного контракта (автоматически)
# _generate_matching_contract() вызывается внутри generate_prompt_variant()

# 3. Валидация
prompt_valid, prompt_errors = await _validate_improved_prompt(
    original_prompt, new_prompt
)
contract_valid, contract_errors = await _validate_improved_contract(
    original_contract, new_contract
)

# 4. Если всё OK → A/B тест
if prompt_valid and contract_valid:
    comparison = await benchmark_service.compare_versions(
        version_a='v1.0.0',
        version_b='v1.1.0-draft',
        scenarios=scenarios
    )
    
    # 5. Продвижение если лучше
    if comparison.improvement > 0.05:
        await benchmark_service.promote_version(
            capability='planning.create_plan',
            from_version='v1.0.0',
            to_version='v1.1.0'
        )
```

---

### Пример использования PromptContractGenerator

```python
# 1. Инициализация
generator = PromptContractGenerator(
    llm_provider=llm_provider,
    data_repository=data_repository,
    data_dir=Path('data')
)

# 2. Анализ неудач
failure_analysis = FailureAnalysis(
    capability='planning.create_plan',
    version='v1.0.0',
    failure_count=15,
    total_executions=100,
    error_patterns=[
        {'type': 'ContractValidationError', 'count': 10, 'examples': ['missing field']},
        {'type': 'TimeoutError', 'count': 5, 'examples': ['exceeded 30s']}
    ],
    common_failure_scenarios=['Complex tasks with multiple dependencies'],
    suggested_fixes=['Add validation for required fields']
)

# 3. Генерация новой версии
new_version = await generator.generate_prompt_variant(
    capability='planning.create_plan',
    base_version='v1.0.0',
    optimization_goal='Улучшить точность и снизить количество ошибок валидации',
    failure_analysis=failure_analysis
)

print(f"Создана новая версия: {new_version}")
# → v1.1.0-draft

# 4. Проверка сохранённого файла
prompt_file = Path('data/prompts/skills/planning/create_plan_v1.1.0.yaml')
assert prompt_file.exists()
```

---

## 📍 Размещение компонентов

### Правильное размещение

```
project/
├── core/
│   ├── infrastructure/
│   │   ├── metrics_collector.py           ← НОВОЕ: Сбор метрик
│   │   ├── metrics_storage.py             ← НОВОЕ: Хранилище метрик
│   │   ├── log_collector.py               ← НОВОЕ: Сбор логов
│   │   └── log_storage.py                 ← НОВОЕ: Хранилище логов
│   │
│   └── application/
│       ├── services/
│       │   ├── learning_orchestrator.py   ← НОВОЕ: Оркестратор обучения
│       │   ├── benchmark_service.py       ← НОВОЕ: Бенчмарк сервис
│       │   ├── optimization_service.py    ← НОВОЕ: Оптимизация
│       │   └── prompt_contract_generator.py ← НОВОЕ: Генерация промптов
│       └── behaviors/
│           └── learning_pattern.py        ← НОВОЕ: Паттерн обучения
│
└── data/
    ├── benchmarks/                        ← НОВОЕ: Сценарии бенчмарков
    │   ├── scenarios/
    │   └── datasets/
    └── metrics/                           ← НОВОЕ: История метрик
```

### Почему так?

| Компонент | Слой | Почему |
|-----------|------|--------|
| **MetricsCollector** | Infrastructure | Централизованный сбор со всех агентов |
| **LogCollector** | Infrastructure | Централизованное хранение логов |
| **LearningOrchestrator** | Application | Оркестрация поведения агента |
| **BenchmarkService** | Application | Тестирование application-компонентов |
| **OptimizationService** | Application | Генерация новых промптов/контрактов |

**Главное правило:**
```
Infrastructure = сбор и хранение (централизованно)
Application = анализ и оптимизация (пер-агент)
```

---

## 💾 Стратегия хранения данных

### Принципы

| Принцип | Описание |
|---------|----------|
| **Интерфейсы primero** | Сначала определяем интерфейсы, потом реализации |
| **Файлы по умолчанию** | FileSystem — реализация по умолчанию (не требует БД) |
| **Смена провайдера** | Замена реализации без изменения бизнес-логики |
| **Единый стиль** | Следование конвенциям `IPromptStorage`/`IContractStorage` |

### Архитектура хранения

```
┌─────────────────────────────────────────────────────────────┐
│                    Бизнес-логика                            │
│  MetricsCollector → IMetricsStorage ← LogCollector          │
│                         │                                   │
│                         ▼                                   │
│              ┌──────────────────────┐                       │
│              │   Интерфейсы (ABC)   │                       │
│              │  - IMetricsStorage   │                       │
│              │  - ILogStorage       │                       │
│              └──────────┬───────────┘                       │
│                         │                                   │
│         ┌───────────────┼───────────────┐                   │
│         ▼               ▼               ▼                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │ FileSystem │ │   SQLite   │ │ PostgreSQL │              │
│  │ (default)  │ │  (local)   │ │  (prod)    │              │
│  └────────────┘ └────────────┘ └────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

### Интерфейсы (новые файлы)

**Файл:** `core/infrastructure/interfaces/metrics_log_interfaces.py`

```python
"""
Интерфейсы для хранилищ метрик и логов.

ПРИНЦИПЫ:
- Абстрактные базовые классы (ABC) для строгой контракции
- Асинхронные методы для неблокирующего доступа
- Типизированные модели данных (MetricRecord, LogEntry)
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime
from core.models.data.metrics import MetricRecord, AggregatedMetrics
from core.models.data.benchmark import LogEntry


class IMetricsStorage(ABC):
    """
    Интерфейс для хранилища метрик.
    
    РЕАЛИЗАЦИИ:
    - FileSystemMetricsStorage (по умолчанию)
    - SQLiteMetricsStorage (локально)
    - PostgreSQLMetricsStorage (продакшен)
    """

    @abstractmethod
    async def record(self, metric: MetricRecord) -> None:
        """
        Запись одной метрики.

        ARGS:
        - metric: объект метрики для записи

        RAISES:
        - IOError: если не удалось записать
        """
        pass

    @abstractmethod
    async def get_records(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000
    ) -> List[MetricRecord]:
        """
        Получение записей метрик с фильтрацией.

        ARGS:
        - capability: имя capability для фильтрации
        - version: версия для фильтрации (опционально)
        - time_range: диапазон времени (start, end)
        - limit: максимум записей

        RETURNS:
        - List[MetricRecord]: список записей метрик
        """
        pass

    @abstractmethod
    async def aggregate(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> AggregatedMetrics:
        """
        Агрегация метрик по фильтру.

        ARGS:
        - capability: имя capability
        - version: версия (опционально)
        - time_range: диапазон времени

        RETURNS:
        - AggregatedMetrics: агрегированные метрики
        """
        pass

    @abstractmethod
    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых записей (TTL).

        ARGS:
        - older_than: удалять записи старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        pass


class ILogStorage(ABC):
    """
    Интерфейс для хранилища логов.
    
    РЕАЛИЗАЦИИ:
    - FileSystemLogStorage (по умолчанию)
    - SQLiteLogStorage (локально)
    - PostgreSQLLogStorage (продакшен)
    """

    @abstractmethod
    async def save(self, entry: LogEntry) -> None:
        """
        Сохранение одной записи лога.

        ARGS:
        - entry: объект записи лога

        RAISES:
        - IOError: если не удалось сохранить
        """
        pass

    @abstractmethod
    async def get_by_session(
        self,
        agent_id: str,
        session_id: str,
        limit: int = 1000
    ) -> List[LogEntry]:
        """
        Получение логов по сессии.

        ARGS:
        - agent_id: ID агента
        - session_id: ID сессии
        - limit: максимум записей

        RETURNS:
        - List[LogEntry]: список записей логов
        """
        pass

    @abstractmethod
    async def get_by_capability(
        self,
        capability: str,
        log_type: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000
    ) -> List[LogEntry]:
        """
        Получение логов по capability.

        ARGS:
        - capability: имя capability
        - log_type: тип лога (опционально)
        - time_range: диапазон времени
        - limit: максимум записей

        RETURNS:
        - List[LogEntry]: список записей логов
        """
        pass

    @abstractmethod
    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых записей (TTL).

        ARGS:
        - older_than: удалять записи старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        pass
```

---

### Реализация: FileSystem (по умолчанию)

**Файл:** `core/infrastructure/metrics_storage.py`

```python
"""
Хранилище метрик на базе файловой системы.

ФОРМАТ ХРАНЕНИЯ:
- JSON Lines (.jsonl) — одна запись = одна строка
- Партиционирование по датам: data/metrics/YYYY-MM-DD.jsonl
- Автоматическая ротация файлов

ПРЕИМУЩЕСТВА:
- Не требует БД
- Легко читать внешними инструментами
- Простое резервное копирование
"""
from pathlib import Path
import json
import aiofiles
from datetime import datetime
from typing import List, Optional, Tuple
from core.models.data.metrics import MetricRecord, AggregatedMetrics
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage


class FileSystemMetricsStorage(IMetricsStorage):
    """FileSystem реализация IMetricsStorage"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "metrics"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_daily_file(self, date: datetime) -> Path:
        """Получение пути к файлу за дату"""
        return self.base_dir / f"{date.strftime('%Y-%m-%d')}.jsonl"

    async def record(self, metric: MetricRecord) -> None:
        """Запись метрики в daily файл"""
        file_path = self._get_daily_file(metric.timestamp)
        
        line = json.dumps({
            'agent_id': metric.agent_id,
            'capability': metric.capability,
            'version': metric.version,
            'execution_time_ms': metric.execution_time_ms,
            'success': metric.success,
            'tokens_used': metric.tokens_used,
            'timestamp': metric.timestamp.isoformat(),
            'session_id': metric.session_id,
            'correlation_id': metric.correlation_id,
            'metadata': metric.metadata
        }, ensure_ascii=False)

        async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
            await f.write(line + '\n')

    async def get_records(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000
    ) -> List[MetricRecord]:
        """Чтение метрик с фильтрацией"""
        records = []
        
        # Определяем файлы для чтения
        if time_range:
            start, end = time_range
            current = start.date()
            end_date = end.date()
        else:
            # По умолчанию — последние 7 дней
            end = datetime.now()
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            current = start.date()
            end_date = end.date()

        while current <= end_date and len(records) < limit:
            file_path = self.base_dir / f"{current}.jsonl"
            if file_path.exists():
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    async for line in f:
                        if len(records) >= limit:
                            break
                        data = json.loads(line.strip())
                        
                        # Фильтрация по capability
                        if data['capability'] != capability:
                            continue
                        
                        # Фильтрация по version
                        if version and data.get('version') != version:
                            continue
                        
                        # Фильтрация по времени
                        ts = datetime.fromisoformat(data['timestamp'])
                        if time_range and (ts < start or ts > end):
                            continue

                        records.append(MetricRecord(**data))
            
            current = current.replace(day=current.day + 1)

        return records

    async def aggregate(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> AggregatedMetrics:
        """Агрегация метрик"""
        records = await self.get_records(
            capability=capability,
            version=version,
            time_range=time_range,
            limit=10000  # Большой лимит для агрегации
        )

        if not records:
            return AggregatedMetrics(
                capability=capability,
                version=version or 'unknown',
                time_range=time_range or (datetime.now(), datetime.now())
            )

        # Вычисляем агрегации
        total = len(records)
        success_count = sum(1 for r in records if r.success)
        total_time = sum(r.execution_time_ms for r in records)
        total_tokens = sum(r.tokens_used for r in records)
        
        # Сортируем для перцентилей
        times = sorted(r.execution_time_ms for r in records)
        p95_idx = int(len(times) * 0.95)
        p99_idx = int(len(times) * 0.99)

        return AggregatedMetrics(
            capability=capability,
            version=version or 'unknown',
            time_range=time_range or (datetime.now(), datetime.now()),
            accuracy=success_count / total if total > 0 else 0.0,
            success_rate=success_count / total if total > 0 else 0.0,
            latency_ms=total_time / total if total > 0 else 0.0,
            latency_p95_ms=times[p95_idx] if p95_idx < len(times) else times[-1],
            latency_p99_ms=times[p99_idx] if p99_idx < len(times) else times[-1],
            tokens_used=total_tokens,
            total_executions=total,
            error_rate=1.0 - (success_count / total) if total > 0 else 0.0
        )

    async def clear_old(self, older_than: datetime) -> int:
        """Удаление старых файлов"""
        deleted = 0
        for file_path in self.base_dir.glob("*.jsonl"):
            # Извлекаем дату из имени файла
            try:
                file_date = datetime.strptime(file_path.stem, '%Y-%m-%d')
                if file_date < older_than:
                    file_path.unlink()
                    deleted += 1
            except ValueError:
                continue  # Пропускаем файлы с неверным форматом
        return deleted
```

---

### Реализация: Log Storage

**Файл:** `core/infrastructure/log_storage.py`

```python
"""
Хранилище логов на базе файловой системы.

ФОРМАТ ХРАНЕНИЯ:
- JSON Lines (.jsonl) — одна запись = одна строка
- Партиционирование по типам и датам: data/logs/{type}/YYYY-MM-DD.jsonl
- Индексация по session_id для быстрого поиска
"""
from pathlib import Path
import json
import aiofiles
from datetime import datetime
from typing import List, Optional, Tuple
from core.models.data.benchmark import LogEntry
from core.infrastructure.interfaces.metrics_log_interfaces import ILogStorage


class FileSystemLogStorage(ILogStorage):
    """FileSystem реализация ILogStorage"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "logs"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._session_index: dict[str, List[Path]] = {}  # Индекс для быстрого поиска

    def _get_daily_file(self, log_type: str, date: datetime) -> Path:
        """Получение пути к файлу лога"""
        type_dir = self.base_dir / log_type
        type_dir.mkdir(parents=True, exist_ok=True)
        return type_dir / f"{date.strftime('%Y-%m-%d')}.jsonl"

    async def save(self, entry: LogEntry) -> None:
        """Сохранение записи лога"""
        file_path = self._get_daily_file(entry.log_type, entry.timestamp)
        
        line = json.dumps({
            'timestamp': entry.timestamp.isoformat(),
            'agent_id': entry.agent_id,
            'session_id': entry.session_id,
            'log_type': entry.log_type,
            'data': entry.data,
            'correlation_id': entry.correlation_id
        }, ensure_ascii=False)

        async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
            await f.write(line + '\n')

        # Обновляем индекс
        if entry.session_id:
            key = f"{entry.agent_id}:{entry.session_id}"
            if key not in self._session_index:
                self._session_index[key] = []
            self._session_index[key].append(file_path)

    async def get_by_session(
        self,
        agent_id: str,
        session_id: str,
        limit: int = 1000
    ) -> List[LogEntry]:
        """Получение логов сессии"""
        entries = []
        key = f"{agent_id}:{session_id}"
        
        # Используем индекс если есть
        if key in self._session_index:
            files_to_read = set(self._session_index[key])
        else:
            # Fallback: читаем все файлы за последние 7 дней
            files_to_read = set()
            for i in range(7):
                date = datetime.now().replace(day=datetime.now().day - i)
                for log_type in ['capability_selection', 'error', 'benchmark']:
                    files_to_read.add(self._get_daily_file(log_type, date))

        for file_path in files_to_read:
            if not file_path.exists():
                continue
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                async for line in f:
                    if len(entries) >= limit:
                        break
                    data = json.loads(line.strip())
                    if data.get('session_id') == session_id and data.get('agent_id') == agent_id:
                        entries.append(LogEntry(**data))

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    async def get_by_capability(
        self,
        capability: str,
        log_type: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 1000
    ) -> List[LogEntry]:
        """Получение логов по capability"""
        entries = []
        types_to_read = [log_type] if log_type else ['capability_selection', 'error']

        # Определяем диапазон дат
        if time_range:
            start, end = time_range
            current = start.date()
            end_date = end.date()
        else:
            end = datetime.now()
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            current = start.date()
            end_date = end.date()

        while current <= end_date and len(entries) < limit:
            for lt in types_to_read:
                file_path = self._get_daily_file(lt, current)
                if file_path.exists():
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        async for line in f:
                            if len(entries) >= limit:
                                break
                            data = json.loads(line.strip())
                            
                            # Фильтрация по capability
                            if data.get('data', {}).get('capability') == capability:
                                entries.append(LogEntry(**data))
            
            current = current.replace(day=current.day + 1)

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    async def clear_old(self, older_than: datetime) -> int:
        """Удаление старых файлов"""
        deleted = 0
        for type_dir in self.base_dir.iterdir():
            if not type_dir.is_dir():
                continue
            for file_path in type_dir.glob("*.jsonl"):
                try:
                    file_date = datetime.strptime(file_path.stem, '%Y-%m-%d')
                    if file_date < older_than:
                        file_path.unlink()
                        deleted += 1
                except ValueError:
                    continue
        return deleted
```

---

### Модель LogEntry

**Файл:** `core/models/data/benchmark.py` (дополнить)

```python
@dataclass
class LogEntry:
    """
    Запись лога для обучения.
    """
    timestamp: datetime
    agent_id: str
    session_id: str
    log_type: str  # 'capability_selection', 'error', 'benchmark'
    data: Dict[str, Any]
    correlation_id: str = ""
```

---

### Регистрация в InfrastructureContext

**Файл:** `core/infrastructure/context/infrastructure_context.py` (расширить)

```python
class InfrastructureContext:
    def __init__(self, config: AppConfig):
        self.config = config
        self.data_dir = Path(config.data_dir)
        
        # Хранилища (интерфейсы)
        self.metrics_storage: IMetricsStorage = FileSystemMetricsStorage(self.data_dir)
        self.log_storage: ILogStorage = FileSystemLogStorage(self.data_dir)
        
        # Коллекторы
        self.metrics_collector = MetricsCollector(self.event_bus, self.metrics_storage)
        self.log_collector = LogCollector(self.event_bus, self.log_storage)

    async def initialize(self):
        await self.metrics_collector.initialize()
        await self.log_collector.initialize()
```

---

### Смена провайдера (пример)

**Для перехода на SQLite — изменить только 2 файла:**

```python
# core/infrastructure/context/infrastructure_context.py

# БЫЛО:
from core.infrastructure.metrics_storage import FileSystemMetricsStorage
from core.infrastructure.log_storage import FileSystemLogStorage

# СТАЛО:
from core.infrastructure.sqlite_metrics_storage import SQLiteMetricsStorage
from core.infrastructure.sqlite_log_storage import SQLiteLogStorage

# В __init__:
self.metrics_storage = SQLiteMetricsStorage("sqlite:///data/metrics.db")
self.log_storage = SQLiteLogStorage("sqlite:///data/logs.db")
```

**Бизнес-логика (MetricsCollector, LogCollector, BenchmarkService) не меняется!**

---

### Политика хранения (TTL)

| Тип данных | Горячие | Архив | Удаление |
|------------|---------|-------|----------|
| Метрики | 7 дней | 30 дней | 90 дней |
| Логи | 3 дня | 14 дней | 30 дней |
| Бенчмарки | 30 дней | 90 дней | 1 год |

**Автоматическая очистка:**
```python
# scripts/cleanup_old_data.py
async def cleanup():
    cutoff_metrics = datetime.now() - timedelta(days=90)
    cutoff_logs = datetime.now() - timedelta(days=30)
    
    await metrics_storage.clear_old(cutoff_metrics)
    await log_storage.clear_old(cutoff_logs)
```

---

## 📊 Архитектура метрик: полное руководство

### 🎯 Что такое метрика и зачем она нужна

**Метрика** — это измеримая характеристика выполнения capability.

**Зачем нужны метрики:**
```
┌─────────────────────────────────────────────────────────────┐
│                    ЦЕЛИ СБОРА МЕТРИК                        │
└─────────────────────────────────────────────────────────────┘

1. МОНИТОРИНГ
   └→ "Система работает нормально?"
   └→ "Нет ли деградации производительности?"

2. СРАВНЕНИЕ ВЕРСИЙ
   └→ "v1.1.0 лучше чем v1.0.0?"
   └→ "Стоит ли продвигать draft версию в active?"

3. ОПТИМИЗАЦИЯ
   └→ "Какая capability самая медленная?"
   └→ "Где больше всего ошибок?"

4. ПЛАНИРОВАНИЕ РЕСУРСОВ
   └→ "Сколько токенов тратим в день?"
   └→ "Нужно ли масштабироваться?"
```

---

### 📏 Базовые метрики шага (что собирается)

**При выполнении КАЖДОЙ capability** записывается `MetricRecord`:

```python
MetricRecord(
    # Контекст
    agent_id='agent-123',
    capability='planning.create_plan',
    version='v1.0.0',
    session_id='session-456',
    step_number=1,
    
    # Измерения
    execution_time_ms=150.5,    # ← СКОЛЬКО времени заняло
    success=True,                # ← УСПЕШНО или нет
    tokens_used=250,             # ← РЕСУРСЫ (токены)
    
    timestamp=datetime.now()
)
```

---

### 📊 Агрегированные метрики (что считается)

Из сырых записей (`MetricRecord`) вычисляются **агрегированные метрики**:

#### 1. Success Rate (Процент успешных выполнений)

**Что измеряет:** Надёжность capability

**Формула:**
```python
success_rate = successful_executions / total_executions
```

**Пример:**
```
planning.create_plan@v1.0.0 за неделю:
- Всего выполнений: 100
- Успешных: 93
- Ошибок: 7

success_rate = 93 / 100 = 0.93 (93%)
```

**Что такое хорошо/плохо:**
| Значение | Оценка | Действие |
|----------|--------|----------|
| ≥ 0.95 | ✅ Отлично | Поддерживать |
| 0.90 - 0.95 | ⚠️ Нормально | Наблюдать |
| 0.80 - 0.90 | 🟠 Внимание | Анализировать ошибки |
| < 0.80 | 🔴 Критично | Срочная оптимизация |

**На что влияет:**
- Решение о продвижении версии (promote/reject)
- Приоритет оптимизации (capability с низким success_rate — первые в очереди)

---

#### 2. Latency (Время выполнения)

**Что измеряет:** Скорость выполнения capability

**Три метрики:**

| Метрика | Формула | Зачем |
|---------|---------|-------|
| `latency_ms` (среднее) | `sum(execution_time) / count` | Общая оценка |
| `latency_p95_ms` (95-й перцентиль) | Значение, ниже которого 95% измерений | SLA, худшие случаи |
| `latency_p99_ms` (99-й перцентиль) | Значение, ниже которого 99% измерений | Критичные задержки |

**Пример расчёта:**
```
10 выполнений planning.create_plan@v1.0.0:
[100, 120, 115, 130, 125, 140, 135, 150, 200, 500] мс

latency_ms = (100+120+115+130+125+140+135+150+200+500) / 10 = 171.5 мс
latency_p95_ms = 200 мс (9-е значение из 10)
latency_p99_ms = 500 мс (10-е значение из 10)
```

**Что такое хорошо/плохо:**
| Capability | < 100мс | 100-500мс | 500-1000мс | > 1000мс |
|------------|---------|-----------|------------|----------|
| planning | ✅ | ⚠️ | 🟠 | 🔴 |
| sql_generation | ✅ | ⚠️ | 🟠 | 🔴 |
| text_summarize | ⚠️ | ✅ | ⚠️ | 🟠 |

**На что влияет:**
- Выбор capability (если есть альтернативы)
- Оптимизация промптов (сокращение токенов → быстрее)
- Бюджетирование времени сессии

---

#### 3. Accuracy (Точность)

**Что измеряет:** Насколько результат соответствует ожидаемому

**Как считается (для бенчмарков):**
```python
accuracy = matching_criteria / total_criteria
```

**Пример:**
```
Бенчмарк: "Создать план из 5 шагов"
Ожидаемый результат: 5 шагов, каждый с описанием

Фактический результат: 4 шага, 3 с описанием

Критерии оценки:
- Количество шагов: 4/5 = 0.8
- Полнота описания: 3/5 = 0.6

accuracy = (0.8 + 0.6) / 2 = 0.7 (70%)
```

**Что такое хорошо/плохо:**
| Значение | Оценка | Действие |
|----------|--------|----------|
| ≥ 0.95 | ✅ Отлично | Эталонная версия |
| 0.85 - 0.95 | ⚠️ Хорошо | Приемлемо для prod |
| 0.70 - 0.85 | 🟠 Требует улучшения | Только sandbox |
| < 0.70 | 🔴 Недопустимо | Отклонить версию |

**На что влияет:**
- **Главный критерий** для A/B тестирования версий
- Решение о продвижении версии
- Выявление регрессий

---

#### 4. Token Usage (Использование токенов)

**Что измеряет:** Потребление ресурсов LLM

**Формула:**
```python
total_tokens = sum(tokens_used for each execution)
avg_tokens = total_tokens / total_executions
```

**Пример:**
```
sql_generation.generate@v1.2.0 за день:
- 500 выполнений
- 125,000 токенов всего
- 250 токенов в среднем на выполнение

Стоимость (при $0.002/1K токенов):
125,000 / 1000 * 0.002 = $0.25/день
```

**Что такое хорошо/плохо:**
| Метрика | Оценка | Действие |
|---------|--------|----------|
| Растёт avg_tokens | 🟠 | Оптимизировать промпт |
| Растёт total_tokens | 🟠 | Пересмотреть бюджет |
| Выше аналогов на 50%+ | 🔴 | Критично, требует рефакторинга |

**На что влияет:**
- Бюджетирование
- Выбор между альтернативными capability
- Оптимизация промптов (меньше токенов = дешевле + быстрее)

---

#### 5. Error Rate (Процент ошибок)

**Что измеряет:** Частоту ошибок

**Формула:**
```python
error_rate = 1.0 - success_rate
# или
error_rate = failed_executions / total_executions
```

**Пример:**
```
planning.create_plan@v1.0.0:
- 100 выполнений
- 7 ошибок
- error_rate = 7 / 100 = 0.07 (7%)
```

**Типы ошибок (из логов):**
| Тип | Пример | Причина |
|-----|--------|---------|
| ContractValidationError | "missing field 'query'" | Ошибка агента (передал не то) |
| LLMProviderError | "timeout" | Внешняя система |
| PromptError | "template variable missing" | Ошибка в промпте |
| BusinessLogicError | "no tables found" | Ошибка в логике |

**Что такое хорошо/плохо:**
| Значение | Оценка | Действие |
|----------|--------|----------|
| < 0.05 | ✅ Отлично | Норма |
| 0.05 - 0.10 | ⚠️ Внимание | Анализировать паттерны |
| 0.10 - 0.20 | 🟠 Проблема | Срочный анализ |
| > 0.20 | 🔴 Критично | Блокировка версии |

**На что влияет:**
- Приоритет исправлений
- Выявление системных проблем
- Решение об откате версии

---

### 📋 Сводная таблица метрик

| Метрика | Формула | Хорошо | Плохо | Влияние |
|---------|---------|--------|-------|---------|
| **success_rate** | `success / total` | ≥ 0.95 | < 0.80 | Надёжность |
| **accuracy** | `matching / criteria` | ≥ 0.95 | < 0.70 | Качество |
| **latency_ms** | `sum(time) / count` | < 100мс | > 1000мс | Скорость |
| **latency_p95** | 95-й перцентиль | < 500мс | > 2000мс | SLA |
| **tokens_used** | `sum(tokens)` | Минимум | Рост > 50% | Стоимость |
| **error_rate** | `errors / total` | < 0.05 | > 0.20 | Стабильность |

---

## 🔬 Бенчмарк для подсчёта метрик

### Нужен ли бенчмарк?

**Ответ: ДА, но не для всех метрик**

| Метрика | Считается без бенчмарка? | Нужен бенчмарк? |
|---------|-------------------------|-----------------|
| `success_rate` | ✅ Да (из success флага) | ❌ Нет |
| `latency_ms` | ✅ Да (из execution_time) | ❌ Нет |
| `tokens_used` | ✅ Да (из tokens_used) | ❌ Нет |
| `error_rate` | ✅ Да (из success=false) | ❌ Нет |
| `accuracy` | ❌ **Нет** | ✅ **ДА** |

---

### Зачем нужен бенчмарк?

**Бенчмарк** — это тестовый сценарий с **известным ожидаемым результатом**.

**Проблема без бенчмарка:**
```
Агент выполнил задачу: "Создать план проекта"
→ success=True (ошибок не было)
→ latency=150мс (быстро)

НО: План оказался неполным (3 шага вместо 5)!
→ Без бенчмарка мы не узнаем об этом
→ success=True вводит в заблуждение
```

**Решение с бенчмарком:**
```python
BenchmarkScenario(
    id='planning_test_001',
    goal='Создать план из 5 шагов',
    input_data={'task': 'разработка ПО'},
    expected_output={
        'min_steps': 5,
        'each_step_has': ['description', 'estimate']
    },
    success_criteria={
        'steps_count': 5,
        'all_have_description': True,
        'all_have_estimate': True
    }
)

# После выполнения агента:
actual_output = agent.run('разработка ПО')

# Оценка accuracy:
accuracy = calculate_accuracy(
    actual=actual_output,
    expected=expected_output,
    criteria=success_criteria
)
# → accuracy = 0.6 (только 3 шага, без оценок)
```

---

### Как бенчмарк считает accuracy

**Важно:** Не существует универсального алгоритма. Стратегия зависит от **типа задачи**.

---

#### Стратегия 1: Правило-ориентированная (для структурированных задач)

**Для:** planning, sql_generation, data_extraction

**Алгоритм:**

```python
def calculate_accuracy(actual, expected, criteria) -> float:
    """
    Вычисляет точность через проверку правил.
    Возвращает число от 0.0 до 1.0
    """
    scores = []
    
    # Критерий 1: Количество элементов
    if 'min_count' in criteria:
        step_score = min(1.0, len(actual.items) / criteria['min_count'])
        scores.append(step_score)
    
    # Критерий 2: Наличие обязательных полей
    if 'required_fields' in criteria:
        field_scores = []
        for field in criteria['required_fields']:
            has_field = sum(1 for item in actual.items if hasattr(item, field))
            field_scores.append(has_field / len(actual.items) if actual.items else 0)
        scores.append(sum(field_scores) / len(field_scores))
    
    # Критерий 3: Соответствие формату
    if 'format_validator' in criteria:
        valid_count = sum(1 for item in actual.items 
                         if criteria['format_validator'](item))
        scores.append(valid_count / len(actual.items) if actual.items else 0)
    
    # Средняя точность
    return sum(scores) / len(scores) if scores else 0.0
```

**Пример расчёта:**
```
Задача: "Создать план из 5 шагов"

criteria = {
    'min_count': 5,
    'required_fields': ['description', 'estimate'],
    'format_validator': lambda step: len(step.description) > 10
}

Ожидаемо: 5 шагов, все с описанием >10 символов и оценкой
Фактично: 3 шага, 2 с описанием >10, 1 с оценкой

Критерий 1 (количество): min(1.0, 3/5) = 0.6
Критерий 2 (поля): (2/3 + 1/3) / 2 = 0.5
Критерий 3 (формат): 2/3 = 0.67

accuracy = (0.6 + 0.5 + 0.67) / 3 = 0.59 (59%)
```

---

#### Стратегия 2: LLM-ориентированная (для текстовых задач)

**Для:** summarization, classification, text_generation, reasoning

**Алгоритм:**

```python
async def calculate_accuracy_with_llm(
    actual: str,
    expected: str,
    criteria: Dict,
    llm_provider: Any
) -> float:
    """
    Оценка точности через LLM-сравнение.
    Используется когда результат — текст, а не структура.
    """
    prompt = f"""
Сравни два ответа на задачу:

Задача: {criteria['task_description']}

Ожидаемый ответ (эталон):
{expected}

Фактический ответ (агент):
{actual}

Критерии оценки (rubric):
{criteria['rubric']}

Оцени фактический ответ по шкале от 0.0 до 1.0:
- 1.0: Полностью соответствует эталону
- 0.5: Частично соответствует
- 0.0: Не соответствует

Верни ТОЛЬКО число от 0.0 до 1.0:
"""
    
    response = await llm_provider.generate(prompt)
    
    # Извлекаем число из ответа
    accuracy = float(response.strip())
    
    # Валидация диапазона
    return max(0.0, min(1.0, accuracy))
```

**Пример расчёта:**
```python
criteria = {
    'task_description': 'Саммаризировать статью про ИИ',
    'rubric': '''
    - 1.0: Все ключевые моменты отражены (нейросети, обучение, применение)
    - 0.5: Половина ключевых моментов
    - 0.0: Ни одного ключевого момента или ошибки
    '''
}

accuracy = await calculate_accuracy_with_llm(
    actual="ИИ использует нейросети для обучения...",
    expected="Искусственный интеллект применяет глубокие нейросети...",
    criteria=criteria,
    llm_provider=provider
)
# → LLM вернёт 0.75 (75% соответствие)
```

**Преимущества:**
- ✅ Работает для любых текстов
- ✅ Учитывает семантику, а не только синтаксис
- ✅ Не требует жёсткой структуры

**Недостатки:**
- ❌ Требует LLM-вызов (стоимость + время)
- ❌ Может быть неконсистентным (один ответ → разная оценка)

---

#### Стратегия 3: Гибридная (комбинированная)

**Для:** сложных задач с несколькими аспектами

**Алгоритм:**

```python
async def calculate_hybrid_accuracy(
    actual: Any,
    expected: Any,
    criteria: Dict,
    llm_provider: Any
) -> float:
    """
    Комбинирует правило-ориентированную и LLM-оценку.
    """
    scores = []
    weights = []
    
    # 1. Структурированные критерии (автоматически)
    if 'structured_criteria' in criteria:
        for crit in criteria['structured_criteria']:
            score = evaluate_structured(actual, expected, crit)
            scores.append(score)
            weights.append(crit.get('weight', 1.0))
    
    # 2. Текстовые критерии (через LLM)
    if 'text_criteria' in criteria:
        for crit in criteria['text_criteria']:
            score = await calculate_accuracy_with_llm(
                actual.text, expected.text, crit, llm_provider
            )
            scores.append(score)
            weights.append(crit.get('weight', 1.0))
    
    # 3. Взвешен����ое среднее
    if scores:
        total_weight = sum(weights)
        return sum(s * w for s, w in zip(scores, weights)) / total_weight
    return 0.0
```

**Пример расчёта:**
```python
criteria = {
    'structured_criteria': [
        {'type': 'min_count', 'value': 5, 'weight': 2.0},
        {'type': 'required_fields', 'fields': ['description'], 'weight': 1.0},
    ],
    'text_criteria': [
        {
            'task_description': 'Описание шагов плана',
            'rubric': 'Ясность и полнота описания',
            'weight': 1.5
        }
    ]
}

# Структурированные: 0.6 (кол-во), 0.5 (поля)
# LLM: 0.8 (качество текста)

# Взвешенное среднее:
# (0.6*2.0 + 0.5*1.0 + 0.8*1.5) / (2.0 + 1.0 + 1.5)
# = (1.2 + 0.5 + 1.2) / 4.5 = 0.64 (64%)
```

---

### Выбор стратегии

| Тип задачи | Стратегия | Почему |
|------------|-----------|--------|
| **planning.create_plan** | Правило-ориентированная | Структурированный результат (шаги) |
| **sql_generation.generate** | Правило-ориентированная | SQL можно валидировать синтаксически |
| **text.summarize** | LLM-ориентированная | Текст, семантика важна |
| **classification.categorize** | Правило-ориентированная | Точное совпадение категорий |
| **reasoning.analyze** | Гибридная | Структура + качество аргументации |

---

### Примеры для разных capability

#### planning.create_plan

```python
criteria = {
    'structured_criteria': [
        {'type': 'min_count', 'value': 5, 'weight': 2.0},
        {'type': 'required_fields', 'fields': ['description', 'estimate'], 'weight': 1.0},
        {'type': 'format_validator', 'validator': lambda s: s.estimate > 0, 'weight': 1.0},
    ]
}
```

#### sql_generation.generate

```python
criteria = {
    'structured_criteria': [
        {'type': 'sql_valid', 'validator': validate_sql_syntax, 'weight': 3.0},
        {'type': 'has_required_tables', 'tables': ['users', 'orders'], 'weight': 2.0},
        {'type': 'has_required_columns', 'columns': ['id', 'created_at'], 'weight': 1.0},
    ]
}
```

#### text.summarize

```python
criteria = {
    'text_criteria': [
        {
            'task_description': 'Саммаризировать статью',
            'rubric': 'Все ключевые моменты отражены кратко',
            'weight': 2.0
        }
    ]
}
```

---

### Пример расчёта:

```
Ожидаемо: 5 шагов, все с описанием и оценкой
Фактично: 3 шага, 2 с описанием, 1 с оценкой

Критерий 1 (шаги): min(1.0, 3/5) = 0.6
Критерий 2 (описание): 2/3 = 0.67
Критерий 3 (оценка): 1/3 = 0.33

accuracy = (0.6 + 0.67 + 0.33) / 3 = 0.53 (53%)
```

---

### Когда использовать бенчмарк

| Сценарий | Нужен бенчмарк? | Почему |
|----------|-----------------|--------|
| Мониторинг prod | ❌ Нет | Достаточно success/latency |
| A/B тестирование версий | ✅ **ДА** | Нужно объективное сравнение |
| Обучение/оптимизация | ✅ **ДА** | Нужно измерять улучшения |
| Отладка ошибок | ❌ Нет | Достаточно логов |
| Приёмка новой capability | ✅ **ДА** | Нужно подтвердить качество |

---

### Полный цикл с бенчмарком

```
┌─────────────────────────────────────────────────────────────┐
│              ЦИКЛ ИЗМЕРЕНИЯ С БЕНЧМАРКОМ                    │
└─────────────────────────────────────────────────────────────┘

1. Запуск бенчмарка
   └→ BenchmarkService.run_benchmark(scenario, version='v1.0.0')

2. Выполнение агентом
   └→ Agent.run(goal)
   └→ Сбор метрик шага (latency, tokens, success)

3. Оценка результата
   └→ compare(actual, expected)
   └→ accuracy = 0.73

4. Сохранение результата
   └→ BenchmarkResult(
         scenario_id='test_001',
         version='v1.0.0',
         accuracy=0.73,
         latency_ms=150,
         tokens_used=250
       )

5. Сравнение версий (A/B тест)
   └→ v1.0.0: accuracy=0.73
   └→ v1.1.0-draft: accuracy=0.89
   └→ improvement = 0.16 (16% улучшение!)

6. Решение
   └→ improvement > 0.05 → PROMOTE v1.1.0-draft to active
```

---

## 📊 Архитектура метрик (полная схема)

```
┌─────────────────────────────────────────────────────────────┐
│                    ПОТОК ДАННЫХ МЕТРИК                      │
└─────────────────────────────────────────────────────────────┘

1. СБОР (на каждый шаг)
   BaseSkill.execute()
   └→ publish(SKILL_EXECUTED, {execution_time_ms, success, tokens})
   └→ MetricsCollector._on_skill_executed()
   └→ storage.record(MetricRecord)

2. АГРЕГАЦИЯ (по запросу)
   MetricsCollector.get_aggregated_metrics(capability, version, time_range)
   └→ storage.get_records()
   └→ calculate:
      - success_rate = sum(success) / count
      - latency_ms = avg(execution_time_ms)
      - latency_p95 = percentile(95, execution_time_ms)
      - tokens_used = sum(tokens_used)
   └→ AggregatedMetrics

3. БЕНЧМАРК (для accuracy)
   BenchmarkService.run_benchmark(scenario, version)
   └→ Agent.run(goal)
   └→ compare(actual, expected)
   └→ accuracy = calculate_accuracy(...)
   └→ BenchmarkResult

4. СРАВНЕНИЕ (A/B тест)
   BenchmarkService.compare_versions(version_a, version_b)
   └→ run_benchmark для каждой версии
   └→ improvement = metrics_b.accuracy - metrics_a.accuracy
   └→ VersionComparison

5. РЕШЕНИЕ (promote/reject)
   if improvement > threshold (0.05):
       promote_version(version_b)
   else:
       reject_version(version_b)
```

---

## 💡 Практические примеры

### Пример 1: Мониторинг prod

```python
# Ежедневный отчёт
metrics = await metrics_collector.get_aggregated_metrics(
    capability='planning.create_plan',
    version='v1.0.0',
    time_range=(yesterday, today)
)

print(f"""
planning.create_plan@v1.0.0 за вчера:
- Выполнений: {metrics.total_executions}
- Успешность: {metrics.success_rate:.1%} {'✅' if metrics.success_rate >= 0.95 else '🔴'}
- Среднее время: {metrics.latency_ms:.0f}мс {'✅' if metrics.latency_ms < 500 else '🔴'}
- Токенов: {metrics.tokens_used} (${metrics.cost:.2f})
""")
```

### Пример 2: A/B тестирование

```python
# Сравнение версий
comparison = await benchmark_service.compare_versions(
    capability='sql_generation.generate',
    version_a='v1.0.0',
    version_b='v1.1.0-draft',
    scenarios=[
        BenchmarkScenario(...),  # 10 тестовых сценариев
        BenchmarkScenario(...),
    ]
)

print(f"""
Сравнение sql_generation.generate:
- v1.0.0: accuracy={comparison.metrics_a.accuracy:.1%}
- v1.1.0-draft: accuracy={comparison.metrics_b.accuracy:.1%}
- Улучшение: {comparison.improvement:.1%}
- Рекомендация: {comparison.recommendation}
""")
# → Рекомендация: "promote" если improvement > 5%
```

### Пример 3: Автоматическая оптимизация

```python
# Запуск цикла оптимизации
result = await optimization_service.start_optimization_cycle(
    capability='planning.create_plan',
    mode=OptimizationMode.TARGET,
    target_metric=TargetMetric(
        name='accuracy',
        target_value=0.95,
        current_value=0.87  # Текущая точность
    ),
    max_iterations=20
)

print(f"""
Оптимизация завершена:
- Было: accuracy=0.87
- Стало: accuracy={result.final_metrics.accuracy:.2f}
- Лучшая версия: {result.best_version}
- Итераций: {result.iterations}
""")
```

---

## 🏗️ Архитектура бенчмарков и оценки

### 🔴 Проблема текущего документа

Сейчас в документе используются **словари** для бенчмарков:

```python
# ❌ ПЛОХО: словари вместо классов
criteria = {
    'min_count': 5,
    'required_fields': ['description', 'estimate'],
}
```

**Почему это неправильно:**
- ❌ Нет валидации структуры
- ❌ Нет типизации
- ❌ Сложно переиспользовать
- ❌ Не соответствует архитектуре проекта (Prompt, Contract — классы)

---

### ✅ Решение: Классы данных (как Prompt, Contract)

**Вся архитектура на классах:**

```
┌─────────────────────────────────────────────────────────────┐
│                    МОДЕЛИ ДАННЫХ                            │
└─────────────────────────────────────────────────────────────┘

core/models/data/benchmark.py
├── BenchmarkScenario          # Сценарий бенчмарка
├── BenchmarkResult            # Результат запуска
├── EvaluationCriteria         # Критерии оценки
├── AccuracyEvaluation         # Результат оценки
└── VersionComparison          # Сравнение версий

core/application/services/accuracy_evaluator.py
├── AccuracyEvaluatorService   # Сервис оценки
└── evaluators/
    ├── ExactMatchEvaluator    # Точное совпадение
    ├── CoverageEvaluator      # Покрытие списка
    ├── SemanticEvaluator      # LLM-оценка
    └── HybridEvaluator        # Комбинированная
```

---

## 📊 Модели данных для бенчмарков

### BenchmarkScenario

**Файл:** `core/models/data/benchmark.py`

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class EvaluationType(str, Enum):
    """Типы оценки точности"""
    EXACT_MATCH = "exact_match"      # Точное совпадение
    MIN_VALUE = "min_value"          # Минимум >= значения
    COVERAGE = "coverage"            # Покрытие списка
    SEMANTIC = "semantic"            # LLM-оценка
    HYBRID = "hybrid"                # Комбинированная


@dataclass
class EvaluationCriterion:
    """
    Отдельный критерий оценки.
    
    ПРИМЕРЫ:
    - min_count: 5 (минимум 5 элементов)
    - required_fields: ['description', 'estimate']
    - sql_valid: True (валидный SQL)
    """
    name: str                      # Имя критерия
    eval_type: EvaluationType      # Тип оценки
    expected_value: Any            # Ожидаемое значение
    weight: float = 1.0            # Вес критерия
    tolerance: float = 0.0         # Допустимое отклонение
    description: str = ""          # Описание для понимания


@dataclass
class BenchmarkScenario:
    """
    Сценарий бенчмарка — тестовая задача с эталоном.
    
    ИСПОЛЬЗОВАНИЕ:
    scenario = BenchmarkScenario(
        id='planning_test_001',
        goal='Создать план из 5 шагов',
        expected_output=ExpectedOutput(...),
        evaluation_criteria=[...],
        allowed_capabilities=['planning.create_plan']
    )
    """
    id: str
    name: str
    description: str
    goal: str                               # Задача для агента
    
    # Эталонный ответ
    expected_output: 'ExpectedOutput'
    
    # Критерии оценки
    evaluation_criteria: List[EvaluationCriterion]
    
    # Ограничения
    allowed_capabilities: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    max_iterations: int = 10
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.now)
    version: str = "v1.0.0"
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Валидация при создании"""
        if not self.goal:
            raise ValueError("goal обязателен")
        if not self.evaluation_criteria:
            raise ValueError("evaluation_criteria обязателен")
```

---

### ExpectedOutput

**Файл:** `core/models/data/benchmark.py`

```python
@dataclass
class ExpectedOutput:
    """
    Ожидаемый результат выполнения бенчмарка.
    
    ДЛЯ СТРУКТУРИРОВАННЫХ ЗАДАЧ:
    ExpectedOutput(
        structured_data={
            'steps_count': 5,
            'has_descriptions': True,
            'tables': ['users', 'orders']
        }
    )
    
    ДЛЯ ТЕКСТОВЫХ ЗАДАЧ:
    ExpectedOutput(
        text='Эталонный текст саммаризации...',
        key_concepts=['концепт1', 'концепт2']
    )
    """
    # Для структурированных задач
    structured_data: Optional[Dict[str, Any]] = None
    
    # Для текстовых задач
    text: Optional[str] = None
    key_concepts: List[str] = field(default_factory=list)
    
    # Для задач со списком ответов
    items: List[str] = field(default_factory=list)
    
    # Метаданные
    description: str = ""
    
    def __post_init__(self):
        """Валидация"""
        has_data = any([
            self.structured_data,
            self.text,
            self.items
        ])
        if not has_data:
            raise ValueError("ExpectedOutput должен содержать данные")
```

---

### BenchmarkResult

**Файл:** `core/models/data/benchmark.py`

```python
@dataclass
class BenchmarkResult:
    """
    Результат запуска бенчмарка.
    
    И��ПОЛЬЗОВАНИЕ:
    result = await benchmark_service.run_benchmark(scenario, version)
    """
    scenario_id: str
    scenario_name: str
    version: str
    
    # Фактический результат
    actual_output: 'ActualOutput'
    
    # Оценка точности
    accuracy: float                    # 0.0 - 1.0
    accuracy_details: 'AccuracyEvaluation'
    
    # Метрики выполнения
    execution_time_ms: float
    tokens_used: int
    total_steps: int
    
    # Статус
    success: bool                      # Все шаги успешны
    goal_achieved: bool                # Цель достигнута (accuracy >= threshold)
    error_message: Optional[str] = None
    
    # Контекст
    agent_id: str
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_better_than(self, other: 'BenchmarkResult', threshold: float = 0.05) -> bool:
        """Проверяет, лучше ли этот результат чем другой"""
        return self.accuracy >= other.accuracy + threshold
```

---

### AccuracyEvaluation

**Файл:** `core/models/data/benchmark.py`

```python
@dataclass
class CriterionScore:
    """Оценка по одному критерию"""
    criterion_name: str
    score: float                       # 0.0 - 1.0
    max_score: float = 1.0
    details: str = ""                  # Пояснение оценки


@dataclass
class AccuracyEvaluation:
    """
    Детальная оценка точности.
    
    ПРИМЕР:
    AccuracyEvaluation(
        overall_accuracy=0.73,
        criterion_scores=[
            CriterionScore('min_count', 0.6, details='3 из 5 шагов'),
            CriterionScore('required_fields', 0.8, details='2 из 3 полей'),
            CriterionScore('format_valid', 1.0, details='формат корректен'),
        ],
        evaluation_type=EvaluationType.HYBRID
    )
    """
    overall_accuracy: float
    criterion_scores: List[CriterionScore]
    evaluation_type: EvaluationType
    
    # Для LLM-оценки
    llm_feedback: Optional[str] = None
    
    def get_weighted_accuracy(self) -> float:
        """Взвешенная точность (с учётом весов критериев)"""
        if not self.criterion_scores:
            return self.overall_accuracy
        
        total_weight = sum(s.max_score for s in self.criterion_scores)
        weighted_sum = sum(s.score * s.max_score for s in self.criterion_scores)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
```

---

### ActualOutput

**Файл:** `core/models/data/benchmark.py`

```python
@dataclass
class ActualOutput:
    """
    Фактический результат выполнения агента.
    
    СОЗДАЁТСЯ:
    - При выполнении Agent.run(goal)
    - Извлекается из ExecutionContextSnapshot
    """
    # Структурированные данные
    structured_data: Optional[Dict[str, Any]] = None
    
    # Текст
    text: Optional[str] = None
    
    # Список элементов
    items: List[str] = field(default_factory=list)
    
    # Метаданные выполнения
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    steps_count: int = 0
    
    # Ошибки
    errors: List[str] = field(default_factory=list)
    
    @classmethod
    def from_execution_context(cls, context: 'ExecutionContextSnapshot') -> 'ActualOutput':
        """Создание из контекста выполнения"""
        return cls(
            structured_data=context.output_result,
            execution_time_ms=context.execution_time_ms,
            tokens_used=context.tokens_used,
            steps_count=context.step_number,
        )
```

---

## 🏗️ AccuracyEvaluator Service

### Интерфейс сервиса

**Файл:** `core/application/services/accuracy_evaluator.py`

```python
from abc import ABC, abstractmethod
from typing import Protocol


class IEvaluationStrategy(Protocol):
    """Интерфейс стратегии оценки"""
    
    async def evaluate(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criteria: List[EvaluationCriterion]
    ) -> AccuracyEvaluation:
        """Оценка точности"""
        pass


class AccuracyEvaluatorService:
    """
    Сервис оценки точности ответов агента.
    
    АРХИТЕКТУРА:
    - Фасад для стратегий оценки
    - Dependency Injection для LLM provider
    - Расширяемость через новые стратегии
    
    ИСПОЛЬЗОВАНИЕ:
    evaluator = AccuracyEvaluatorService(llm_provider)
    evaluation = await evaluator.evaluate(actual, expected, criteria)
    """

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider
        self._strategies = self._init_strategies()

    def _init_strategies(self) -> Dict[EvaluationType, IEvaluationStrategy]:
        """Регистрация стратегий"""
        return {
            EvaluationType.EXACT_MATCH: ExactMatchEvaluator(),
            EvaluationType.MIN_VALUE: MinValueEvaluator(),
            EvaluationType.COVERAGE: CoverageEvaluator(),
            EvaluationType.SEMANTIC: SemanticEvaluator(self.llm_provider),
            EvaluationType.HYBRID: HybridEvaluator(self.llm_provider),
        }

    async def evaluate(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criteria: List[EvaluationCriterion]
    ) -> AccuracyEvaluation:
        """
        Универсальная оценка точности.
        
        ARGS:
        - actual: фактический ответ (класс ActualOutput)
        - expected: ожидаемый ответ (класс ExpectedOutput)
        - criteria: критерии оценки (список EvaluationCriterion)
        
        RETURNS:
        - AccuracyEvaluation: детальная оценка
        
        RAISES:
        - ValueError: если критерии пустые
        """
        if not criteria:
            raise ValueError("criteria не может быть пустым")
        
        # Определяем тип оценки из критериев
        eval_type = self._determine_eval_type(criteria)
        strategy = self._strategies.get(eval_type)
        
        if not strategy:
            raise ValueError(f"Неизвестный тип оценки: {eval_type}")
        
        return await strategy.evaluate(actual, expected, criteria)

    def _determine_eval_type(self, criteria: List[EvaluationCriterion]) -> EvaluationType:
        """Определение типа оценки по критериям"""
        types = set(c.eval_type for c in criteria)
        
        if len(types) == 1:
            return types.pop()
        elif len(types) > 1:
            return EvaluationType.HYBRID
        else:
            return EvaluationType.COVERAGE  # По умолчанию
```

---

### Стратегии оценки

**Файл:** `core/application/evaluators/coverage_evaluator.py`

```python
class CoverageEvaluator:
    """
    Оценка покрытия списка.
    
    ДЛЯ: открытых вопросов (список правильных ответов)
    ПРИМЕР: "Какие книги написал Пушкин?"
    """

    async def evaluate(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criteria: List[EvaluationCriterion]
    ) -> AccuracyEvaluation:
        scores = []
        
        for criterion in criteria:
            if criterion.name == 'min_count':
                score = self._eval_min_count(actual, expected, criterion)
            elif criterion.name == 'required_items':
                score = self._eval_required_items(actual, expected, criterion)
            else:
                continue
            
            scores.append(score)
        
        overall = sum(s.score for s in scores) / len(scores) if scores else 0.0
        
        return AccuracyEvaluation(
            overall_accuracy=overall,
            criterion_scores=scores,
            evaluation_type=EvaluationType.COVERAGE
        )

    def _eval_min_count(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criterion: EvaluationCriterion
    ) -> CriterionScore:
        """Оценка по критерию минимального количества"""
        actual_count = len(actual.items) if actual.items else 0
        expected_count = criterion.expected_value
        
        score = min(1.0, actual_count / expected_count)
        
        return CriterionScore(
            criterion_name='min_count',
            score=score,
            max_score=criterion.weight,
            details=f'{actual_count} из {expected_count}'
        )

    def _eval_required_items(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criterion: EvaluationCriterion
    ) -> CriterionScore:
        """Оценка по критерию обязательных элементов"""
        required_items = criterion.expected_value
        actual_items = actual.items if actual.items else []
        
        # Подсчёт правильных (с учётом синонимов)
        correct_count = sum(
            1 for item in actual_items
            if self._is_correct_item(item, required_items)
        )
        
        score = correct_count / len(required_items) if required_items else 0.0
        
        return CriterionScore(
            criterion_name='required_items',
            score=score,
            max_score=criterion.weight,
            details=f'{correct_count} из {len(required_items)} обязательных'
        )

    def _is_correct_item(self, item: str, required: List[str]) -> bool:
        """Проверка элемента на правильность (с fuzzy match)"""
        if item in required:
            return True
        
        # Fuzzy match для синонимов
        for req in required:
            if fuzzy_match(item, req, threshold=0.8):
                return True
        
        return False
```

---

**Файл:** `core/application/evaluators/semantic_evaluator.py`

```python
class SemanticEvaluator:
    """
    LLM-оценка семантического сходства.
    
    ДЛЯ: текстовых задач (summarize, reasoning)
    ПРИМЕР: "Объясни теорию относительности"
    """

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    async def evaluate(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criteria: List[EvaluationCriterion]
    ) -> AccuracyEvaluation:
        scores = []
        llm_feedback = ""
        
        for criterion in criteria:
            if criterion.eval_type == EvaluationType.SEMANTIC:
                score, feedback = await self._eval_semantic(
                    actual, expected, criterion
                )
                scores.append(score)
                llm_feedback = feedback
        
        overall = sum(s.score for s in scores) / len(scores) if scores else 0.0
        
        return AccuracyEvaluation(
            overall_accuracy=overall,
            criterion_scores=scores,
            evaluation_type=EvaluationType.SEMANTIC,
            llm_feedback=llm_feedback
        )

    async def _eval_semantic(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criterion: EvaluationCriterion
    ) -> Tuple[CriterionScore, str]:
        """LLM-оценка семантики"""
        prompt = self._build_semantic_prompt(actual, expected, criterion)
        
        response = await self.llm_provider.generate(prompt)
        
        # Парсинг ответа LLM
        accuracy, feedback = self._parse_llm_response(response)
        
        return CriterionScore(
            criterion_name=criterion.name,
            score=accuracy,
            max_score=criterion.weight,
            details=feedback
        ), feedback

    def _build_semantic_prompt(
        self,
        actual: ActualOutput,
        expected: ExpectedOutput,
        criterion: EvaluationCriterion
    ) -> str:
        """Создание промпта для LLM-оценки"""
        return f"""
Сравни два ответа на задачу:

Задача: {criterion.description}

Эталонный ответ:
{expected.text or expected.key_concepts}

Фактический ответ агента:
{actual.text}

Критерии оценки:
{criterion.expected_value}

Оцени фактический ответ по шкале от 0.0 до 1.0:
- 1.0: Полностью соответствует эталону
- 0.5: Частично соответствует
- 0.0: Не соответствует

Верни ответ в формате JSON:
{{
    "accuracy": 0.75,
    "feedback": "Краткое пояснение оценки"
}}
"""

    def _parse_llm_response(self, response: str) -> Tuple[float, str]:
        """Парсинг JSON ответа от LLM"""
        try:
            data = json.loads(response.strip())
            accuracy = float(data.get('accuracy', 0.0))
            feedback = data.get('feedback', '')
            return max(0.0, min(1.0, accuracy)), feedback
        except (json.JSONDecodeError, ValueError):
            # Fallback: извлечь число из текста
            import re
            match = re.search(r'\d+\.?\d*', response)
            accuracy = float(match.group()) if match else 0.0
            return max(0.0, min(1.0, accuracy)), response
```

---

## 🔄 Взаимодействие компонентов

### Полный цикл бенчмарка

```
┌─────────────────────────────────────────────────────────────┐
│              ПОТОК ВЫЗОВОВ (на классах)                     │
└─────────────────────────────────────────────────────────────┘

1. Создание бенчмарка
   └→ scenario = BenchmarkScenario(
         id='test_001',
         goal='Создать план',
         expected_output=ExpectedOutput(structured_data={...}),
         evaluation_criteria=[
             EvaluationCriterion('min_count', COVERAGE, 5),
             EvaluationCriterion('required_fields', COVERAGE, ['desc']),
         ]
       )

2. Запуск бенчмарка
   └→ result = await benchmark_service.run_benchmark(scenario, 'v1.0.0')
      │
      ├→ actual_output = await self.agent.run(scenario.goal)
      │   └→ ActualOutput.from_execution_context(context)
      │
      └→ evaluation = await self.evaluator.evaluate(
             actual=actual_output,
             expected=scenario.expected_output,
             criteria=scenario.evaluation_criteria
         )
         │
         ├→ strategy = self._strategies[COVERAGE]
         └→ await strategy.evaluate(actual, expected, criteria)
            └→ CoverageEvaluator._eval_min_count(...)
            └→ CoverageEvaluator._eval_required_items(...)

3. Результат
   └→ return BenchmarkResult(
         scenario_id=scenario.id,
         actual_output=actual_output,
         accuracy=evaluation.overall_accuracy,
         accuracy_details=evaluation,
         execution_time_ms=...,
         success=True
       )
```

---

### Пример использования

```python
# 1. Создание бенчмарка
scenario = BenchmarkScenario(
    id='planning_test_001',
    name='План из 5 шагов',
    description='Тестирование planning.create_plan',
    goal='Создать план разработки ПО из 5 шагов',
    
    expected_output=ExpectedOutput(
        structured_data={
            'steps_count': 5,
            'required_fields': ['description', 'estimate']
        },
        description='План с 5 шагами, каждый с описанием и оценкой'
    ),
    
    evaluation_criteria=[
        EvaluationCriterion(
            name='min_steps',
            eval_type=EvaluationType.MIN_VALUE,
            expected_value=5,
            weight=2.0,
            description='Минимум 5 шагов'
        ),
        EvaluationCriterion(
            name='required_fields',
            eval_type=EvaluationType.COVERAGE,
            expected_value=['description', 'estimate'],
            weight=1.5,
            description='Каждый шаг имеет описание и оценку'
        ),
    ],
    
    allowed_capabilities=['planning.create_plan'],
    timeout_seconds=300
)

# 2. Запуск бенчмарка
result = await benchmark_service.run_benchmark(
    scenario=scenario,
    version='v1.0.0'
)

# 3. Анализ результата
print(f"Точность: {result.accuracy:.1%}")
print(f"Цель достигнута: {result.goal_achieved}")

for score in result.accuracy_details.criterion_scores:
    print(f"  {score.criterion_name}: {score.score:.1%} ({score.details})")

# 4. Сравнение версий
comparison = await benchmark_service.compare_versions(
    version_a='v1.0.0',
    version_b='v1.1.0-draft',
    scenarios=[scenario]
)

if comparison.improvement > 0.05:
    await benchmark_service.promote_version('v1.1.0-draft')
```

---

### Интеграция с BenchmarkService

**Файл:** `core/application/services/benchmark_service.py`

```python
class BenchmarkService(BaseService):
    """
    Оркестрация бенчмарков.
    
    ЗАВИСИМОСТИ:
    - AccuracyEvaluatorService (оценка точности)
    - MetricsCollector (сбор метрик)
    - DataRepository (доступ к версиям)
    """

    def __init__(
        self,
        evaluator: AccuracyEvaluatorService,
        metrics_collector: MetricsCollector,
        data_repository: DataRepository,
        llm_provider: Any
    ):
        self.evaluator = evaluator
        self.metrics_collector = metrics_collector
        self.data_repository = data_repository
        self.llm_provider = llm_provider

    async def run_benchmark(
        self,
        scenario: BenchmarkScenario,
        version: str
    ) -> BenchmarkResult:
        """Запуск одного бенчмарка"""
        start_time = time.time()
        
        try:
            # 1. Создание тестового контекста
            context = await self._create_test_context(scenario, version)
            
            # 2. Запуск агента
            agent = self._create_test_agent(context)
            actual_output = await agent.run(scenario.goal)
            
            # 3. Оценка точности
            evaluation = await self.evaluator.evaluate(
                actual=actual_output,
                expected=scenario.expected_output,
                criteria=scenario.evaluation_criteria
            )
            
            # 4. Сбор метрик
            execution_time = (time.time() - start_time) * 1000
            tokens_used = await self._get_tokens_used(context.session_id)
            
            # 5. Результат
            return BenchmarkResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                version=version,
                actual_output=actual_output,
                accuracy=evaluation.overall_accuracy,
                accuracy_details=evaluation,
                execution_time_ms=execution_time,
                tokens_used=tokens_used,
                total_steps=context.current_step,
                success=evaluation.overall_accuracy >= 0.7,  # Threshold
                goal_achieved=evaluation.overall_accuracy >= 0.9,
                agent_id=context.agent_id,
                session_id=context.session_id
            )
            
        except Exception as e:
            return BenchmarkResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                version=version,
                actual_output=ActualOutput(errors=[str(e)]),
                accuracy=0.0,
                accuracy_details=AccuracyEvaluation(
                    overall_accuracy=0.0,
                    criterion_scores=[],
                    evaluation_type=EvaluationType.EXACT_MATCH
                ),
                execution_time_ms=(time.time() - start_time) * 1000,
                tokens_used=0,
                total_steps=0,
                success=False,
                goal_achieved=False,
                error_message=str(e),
                agent_id="",
                session_id=""
            )

    async def compare_versions(
        self,
        version_a: str,
        version_b: str,
        scenarios: List[BenchmarkScenario]
    ) -> VersionComparison:
        """
        Сравнение двух версий с проверкой статистической значимости.
        
        ЭТАПЫ:
        1. Множественные прогоны (min 5 итераций на сценарий)
        2. Расчёт средних метрик
        3. Проверка статистической значимости (t-test)
        4. Проверка устойчивости (consistency check)
        5. Принятие решения
        
        ARGS:
        - version_a: текущая версия (baseline)
        - version_b: новая версия (candidate)
        - scenarios: список сценариев для тестирования
        
        RETURNS:
        - VersionComparison: результат сравнения
        """
        all_results_a = []
        all_results_b = []
        
        # 1. Множественные прогоны (min 5 итераций на сценарий)
        num_iterations = max(5, len(scenarios) * 3)  # Минимум 5 или 3x от числа сценариев
        
        for iteration in range(num_iterations):
            for scenario in scenarios:
                result_a = await self.run_benchmark(scenario, version_a)
                result_b = await self.run_benchmark(scenario, version_b)
                
                all_results_a.append(result_a)
                all_results_b.append(result_b)
        
        # 2. Расчёт статистик
        stats_a = self._calculate_statistics(all_results_a)
        stats_b = self._calculate_statistics(all_results_b)
        
        # 3. Проверка статистической значимости (t-test)
        t_stat, p_value = self._t_test(
            [r.accuracy for r in all_results_a],
            [r.accuracy for r in all_results_b]
        )
        
        statistically_significant = p_value < 0.05  # 95% confidence
        
        # 4. Проверка устойчивости (consistency check)
        consistency_check = self._check_consistency(all_results_a, all_results_b)
        
        # 5. Расчёт улучшения
        improvement = stats_b['mean_accuracy'] - stats_a['mean_accuracy']
        
        # 6. Принятие решения
        recommendation = self._get_recommendation(
            improvement=improvement,
            statistically_significant=statistically_significant,
            consistency=consistency_check
        )
        
        return VersionComparison(
            version_a=version_a,
            version_b=version_b,
            scenarios_run=len(scenarios),
            total_iterations=num_iterations,
            improvement=improvement,
            best_version=version_b if improvement > 0 else version_a,
            metrics_a=stats_a,
            metrics_b=stats_b,
            statistical_significance={
                't_statistic': t_stat,
                'p_value': p_value,
                'significant': statistically_significant,
                'confidence_level': 0.95
            },
            consistency_check=consistency_check,
            recommendation=recommendation
        )

    def _calculate_statistics(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """
        Расчёт статистик по результатам.
        
        RETURNS:
        - mean_accuracy: средняя точность
        - std_accuracy: стандартное отклонение
        - min_accuracy: минимальная точность
        - max_accuracy: максимальная точность
        - median_accuracy: медианная точность
        - mean_latency: среднее время
        """
        import statistics
        
        accuracies = [r.accuracy for r in results]
        latencies = [r.execution_time_ms for r in results]
        
        return {
            'mean_accuracy': statistics.mean(accuracies),
            'std_accuracy': statistics.stdev(accuracies) if len(accuracies) > 1 else 0,
            'min_accuracy': min(accuracies),
            'max_accuracy': max(accuracies),
            'median_accuracy': statistics.median(accuracies),
            'mean_latency': statistics.mean(latencies),
            'total_runs': len(results)
        }

    def _t_test(self, sample_a: List[float], sample_b: List[float]) -> Tuple[float, float]:
        """
        Двухвыборочный t-тест Стьюдента.
        
        ПРОВЕРЯЕТ:
        - Принадлежат ли две выборки одному распределению
        - Null hypothesis: выборки из одного распределения
        
        RETURNS:
        - t_statistic: t-статистика
        - p_value: вероятность null hypothesis
        
        ИНТЕРПРЕТАЦИЯ:
        - p_value < 0.05: статистически значимо (отвергаем null hypothesis)
        - p_value >= 0.05: не значимо (не можем отвергнуть null hypothesis)
        """
        import statistics
        
        n_a = len(sample_a)
        n_b = len(sample_b)
        
        if n_a < 2 or n_b < 2:
            return 0.0, 1.0  # Недостаточно данных
        
        mean_a = statistics.mean(sample_a)
        mean_b = statistics.mean(sample_b)
        
        var_a = statistics.variance(sample_a)
        var_b = statistics.variance(sample_b)
        
        # Стандартная ошибка разности средних
        se = ((var_a / n_a) + (var_b / n_b)) ** 0.5
        
        if se == 0:
            return 0.0, 1.0
        
        # t-статистика
        t_stat = (mean_a - mean_b) / se
        
        # Степени свободы (приближение Уэлча)
        df = ((var_a / n_a + var_b / n_b) ** 2) / (
            (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        )
        
        # Приближённое вычисление p-value (через нормальное распределение)
        # Для точного вычисления использовать scipy.stats.t.sf
        from math import erf, sqrt
        p_value = 1 - (0.5 * (1 + erf(abs(t_stat) / sqrt(2))))
        
        return t_stat, p_value * 2  # Двусторонний тест

    def _check_consistency(
        self,
        results_a: List[BenchmarkResult],
        results_b: List[BenchmarkResult]
    ) -> Dict[str, Any]:
        """
        Проверка устойчивости результатов.
        
        КРИТЕРИИ:
        1. Коэффициент вариации (CV) < 0.1 (10%)
        2. Все прогоны показывают одинаковое направление
        3. Нет выбросов (>3σ от среднего)
        
        RETURNS:
        - consistent: True если результаты устойчивы
        - cv_a: коэффициент вариации версии A
        - cv_b: коэффициент вариации версии B
        - direction_consistent: все прогоны в одном направлении
        - outliers: количество выбросов
        """
        import statistics
        
        accuracies_a = [r.accuracy for r in results_a]
        accuracies_b = [r.accuracy for r in results_b]
        
        mean_a = statistics.mean(accuracies_a)
        mean_b = statistics.mean(accuracies_b)
        
        std_a = statistics.stdev(accuracies_a) if len(accuracies_a) > 1 else 0
        std_b = statistics.stdev(accuracies_b) if len(accuracies_b) > 1 else 0
        
        # Коэффициент вариации (CV)
        cv_a = std_a / mean_a if mean_a > 0 else 0
        cv_b = std_b / mean_b if mean_b > 0 else 0
        
        # Проверка направления (все ли прогоны b > a или все a > b)
        directions = [b.accuracy - a.accuracy for a, b in zip(results_a, results_b)]
        all_positive = all(d > 0 for d in directions)
        all_negative = all(d < 0 for d in directions)
        direction_consistent = all_positive or all_negative
        
        # Проверка выбросов (>3σ от среднего)
        outliers_a = sum(1 for x in accuracies_a if abs(x - mean_a) > 3 * std_a) if std_a > 0 else 0
        outliers_b = sum(1 for x in accuracies_b if abs(x - mean_b) > 3 * std_b) if std_b > 0 else 0
        
        consistent = (
            cv_a < 0.1 and  # CV < 10%
            cv_b < 0.1 and
            direction_consistent and
            outliers_a == 0 and
            outliers_b == 0
        )
        
        return {
            'consistent': consistent,
            'cv_a': cv_a,
            'cv_b': cv_b,
            'direction_consistent': direction_consistent,
            'outliers_a': outliers_a,
            'outliers_b': outliers_b,
            'total_outliers': outliers_a + outliers_b
        }

    def _get_recommendation(
        self,
        improvement: float,
        statistically_significant: bool,
        consistency: Dict[str, Any]
    ) -> str:
        """
        Принятие решения о продвижении версии.
        
        КРИТЕРИИ ДЛЯ PROMOTE:
        1. Улучшение > 5% (improvement > 0.05)
        2. Статистически значимо (p_value < 0.05)
        3. Результаты устойчивы (consistent = True)
        
        КРИТЕРИИ ДЛЯ REJECT:
        1. Ухудшение > 5% (improvement < -0.05)
        2. ИЛИ статистически значимое ухудшение
        
        ИНАЧЕ: needs_more_testing
        
        ARGS:
        - improvement: разница в точности (version_b - version_a)
        - statistically_significant: результат t-теста
        - consistency: результат проверки устойчивости
        
        RETURNS:
        - "promote", "reject", или "needs_more_testing"
        """
        # Проверка на ухудшение
        if improvement < -0.05:
            return "reject"
        
        if improvement < 0 and statistically_significant:
            return "reject"
        
        # Проверка на улучшение
        if improvement > 0.05:
            if statistically_significant and consistency['consistent']:
                return "promote"
            elif not consistency['consistent']:
                return "needs_more_testing"  # Нестабильные результаты
            else:
                return "needs_more_testing"  # Недостаточно значимо
        
        # Небольшое улучшение/ухудшение (< 5%)
        if -0.05 <= improvement <= 0.05:
            if statistically_significant and improvement > 0:
                return "promote"  # Статистически значимое улучшение даже < 5%
            else:
                return "needs_more_testing"
        
        return "needs_more_testing"


---

## 🧪 A/B тестирование: как принимать решение о продвижении в prod

### ❓ Вопросы и ответы

#### Вопрос 1: Как понять, стоит ли изменение добавлять в промышленную эксплуатацию?

**Ответ:** Решение принимается по **трём критериям**:

```
┌─────────────────────────────────────────────────────────────┐
│           КРИТЕРИИ ДЛЯ ПРОДВИЖЕНИЯ В PROD                   │
└─────────────────────────────────────────────────────────────┘

1. УЛУЧШЕНИЕ > 5%
   └→ improvement = accuracy_b - accuracy_a > 0.05
   └→ Почему 5%? Меньшие улучшения могут быть случайными

2. СТАТИСТИЧЕСКАЯ ЗНАЧИМОСТЬ (p-value < 0.05)
   └→ t-тест Стьюдента показывает, что разница не случайна
   └→ 95% confidence level
   └→ Null hypothesis отвергается

3. УСТОЙЧИВОСТЬ РЕЗУЛЬТАТОВ (consistency check)
   └→ Коэффициент вариации (CV) < 10%
   └→ Все прогоны в одном направлении
   └→ Нет выбросов (>3σ)

ТОЛЬКО ЕСЛИ ВСЕ 3 КРИТЕРИЯ ВЫПОЛНЕНЫ → PROMOTE TO PROD
```

---

#### Вопрос 2: Сколько раз проводится тестирование?

**Ответ:** **Минимум 5 итераций**, но зависит от количества сценариев:

```python
# Формула расчёта количества итераций
num_iterations = max(5, len(scenarios) * 3)  # Минимум 5 или 3x от числа сценариев

# Примеры:
# 1 сценарий  → 5 итераций (минимум)
# 3 сценария  → 9 итераций (3 * 3)
# 10 сценариев → 30 итераций (10 * 3)
```

**Почему так:**
- **Минимум 5** — для базовой статистики
- **3x от числа сценариев** — чтобы каждый сценарий был представлен многократно

**Общее количество прогонов:**
```
total_runs = num_iterations * len(scenarios) * 2  # ×2 для version_a и version_b

Пример (3 сценария, 9 итераций):
total_runs = 9 * 3 * 2 = 54 прогона
```

---

#### Вопрос 3: Как система понимает, что результат устойчивый?

**Ответ:** Проверка **consistency** включает 3 теста:

```python
consistent = (
    cv_a < 0.1 and              # 1. CV версии A < 10%
    cv_b < 0.1 and              # 2. CV версии B < 10%
    direction_consistent and    # 3. Все прогоны в одном направлении
    outliers_a == 0 and         # 4. Нет выбросов в A
    outliers_b == 0             # 5. Нет выбросов в B
)
```

**1. Коэффициент вариации (CV):**
```python
CV = std_dev / mean

# Пример:
version_a: mean=0.80, std=0.05 → CV = 0.05/0.80 = 0.0625 (6.25%) ✅
version_b: mean=0.88, std=0.12 → CV = 0.12/0.88 = 0.136 (13.6%) ❌

# version_b нестабильна (CV > 10%)
```

**2. Направление (direction_consistent):**
```python
# Проверяем, что ВСЕ прогоны показывают b > a (или все a > b)
directions = [b.accuracy - a.accuracy for each run]

# Пример 1 (устойчиво):
directions = [+0.08, +0.06, +0.09, +0.07, +0.08]
→ all_positive = True ✅

# Пример 2 (неустойчиво):
directions = [+0.08, -0.02, +0.09, +0.07, -0.01]
→ all_positive = False ❌
```

**3. Выбросы (outliers):**
```python
# Выброс = значение > 3σ от среднего
outlier = abs(x - mean) > 3 * std

# Пример:
version_a: mean=0.80, std=0.05
runs: [0.78, 0.82, 0.79, 0.81, 0.50]  # ← 0.50 это выброс!
outliers = 1 ❌
```

---

### 📊 Матрица решений

```
┌─────────────────────────────────────────────────────────────┐
│                    A/B TEST DECISION MATRIX                 │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │  compare_versions() │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 1. improvement  │
                    │    > 5%?        │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ NO                          │ YES
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ improvement <   │           │ 2. p-value <    │
    │ -5%?            │           │    0.05?        │
    └────────┬────────┘           └────────┬────────┘
             │                             │
    ┌────────┴────────┐           ┌────────┴────────┐
    │ NO              │ YES       │ NO              │ YES
    ▼                 ▼           ▼                 ▼
┌─────────┐   ┌───────────┐ ┌─────────┐   ┌─────────────────┐
│ needs_  │   │  REJECT   │ │ needs_  │ │ 3. consistent?  │
│ more_   │   │  (ухудше- │ │ more_   │ │ (CV<10%, no     │
│ testing │   │  ние)     │ │ testing │ │  outliers)       │
└─────────┘   └───────────┘ └─────────┘   └────────┬────────┘
                                                   │
                                     ┌─────────────┴─────────────┐
                                     │ NO                        │ YES
                                     ▼                           ▼
                               ┌─────────────┐         ┌─────────────────┐
                               │ needs_more_ │         │    PROMOTE ✅   │
                               │ testing     │         │ (улучшение      │
                               │ (нестабиль- │         │  значимо и      │
                               │  но)        │         │  устойчиво)     │
                               └─────────────┘         └─────────────────┘
```

---

### 📈 Примеры результатов и решений

#### Пример 1: Уверенное улучшение ✅

```python
comparison = await benchmark_service.compare_versions(
    version_a='v1.0.0',
    version_b='v1.1.0-draft',
    scenarios=scenarios
)

# Результаты:
comparison.improvement = 0.12  # 12% улучшение
comparison.statistical_significance = {
    'p_value': 0.003,          # p < 0.05 ✅
    'significant': True
}
comparison.consistency_check = {
    'consistent': True,
    'cv_a': 0.05,              # 5% < 10% ✅
    'cv_b': 0.06,              # 6% < 10% ✅
    'direction_consistent': True,
    'total_outliers': 0
}

comparison.recommendation = "promote"
# ✅ РЕШЕНИЕ: Продвинуть в prod
```

**Почему promote:**
- ✅ Улучшение 12% > 5%
- ✅ p-value 0.003 < 0.05 (статистически значимо)
- ✅ CV 5-6% < 10% (устойчиво)
- ✅ Нет выбросов

---

#### Пример 2: Статистически не значимо ❌

```python
comparison.improvement = 0.08  # 8% улучшение
comparison.statistical_significance = {
    'p_value': 0.15,           # p > 0.05 ❌
    'significant': False
}
comparison.consistency_check = {
    'consistent': True,
    'cv_a': 0.12,              # Высокая вариация
    'cv_b': 0.14
}

comparison.recommendation = "needs_more_testing"
# ❌ РЕШЕНИЕ: Нужно больше тестов
```

**Почему needs_more_testing:**
- ❌ p-value 0.15 > 0.05 (не значимо)
- ❌ CV 12-14% > 10% (высокая вариация)
- Возможно улучшение есть, но нужно больше данных

---

#### Пример 3: Нестабильные результаты ❌

```python
comparison.improvement = 0.10  # 10% улучшение
comparison.statistical_significance = {
    'p_value': 0.02,           # p < 0.05 ✅
    'significant': True
}
comparison.consistency_check = {
    'consistent': False,       # ❌ Нестабильно
    'cv_a': 0.08,
    'cv_b': 0.15,              # ❌ CV > 10%
    'direction_consistent': False,  # ❌ Разные направления
    'total_outliers': 3        # ❌ 3 выброса
}

comparison.recommendation = "needs_more_testing"
# ❌ РЕШЕНИЕ: Результаты нестабильны
```

**Почему needs_more_testing:**
- ✅ Улучшение 10% > 5%
- ✅ p-value 0.02 < 0.05 (значимо)
- ❌ CV 15% > 10% (нестабильно)
- ❌ direction_consistent = False (разные направления)
- ❌ 3 выброса

---

#### Пример 4: Ухудшение ❌

```python
comparison.improvement = -0.08  # -8% (ухудшение!)
comparison.statistical_significance = {
    'p_value': 0.01,           # p < 0.05 ✅
    'significant': True
}

comparison.recommendation = "reject"
# ❌ РЕШЕНИЕ: Отклонить версию
```

**Почему reject:**
- ❌ Ухудшение 8% > 5%
- ✅ Статистически значимо (но это плохо!)
- Новая версия ХУЖЕ текущей

---

### 📊 Интерпретация p-value

| p-value | Значение | Решение |
|---------|----------|---------|
| < 0.01 | Очень значимо | ✅ Доверяем результату |
| 0.01 - 0.05 | Значимо | ✅ Доверяем результату |
| 0.05 - 0.10 | Почти значимо | ⚠️ Нужно больше тестов |
| > 0.10 | Не значимо | ❌ Результат случайный |

**Что такое p-value:**
```
p-value = вероятность получить такие же результаты случайно,
          если на самом деле разницы нет (null hypothesis верна)

p-value = 0.03 означает:
"3% вероятность что разница случайна"
→ 97% уверенность что разница реальная
→ Отвергаем null hypothesis
```

---

### 📊 Интерпретация коэффициента вариации (CV)

| CV | Оценка | Решение |
|----|--------|---------|
| < 5% | Отличная стабильность | ✅ |
| 5% - 10% | Хорошая стабильность | ✅ |
| 10% - 15% | Средняя стабильность | ⚠️ |
| > 15% | Низкая стабильность | ❌ |

**Формула:**
```python
CV = std_dev / mean

# Пример:
mean_accuracy = 0.85
std_dev = 0.04
CV = 0.04 / 0.85 = 0.047 (4.7%) ✅
```

---

### 📋 Чеклист для принятия решения

```
┌─────────────────────────────────────────────────────────────┐
│              ЧЕКЛИСТ: ГОТОВО ЛИ К PROMOTE?                  │
└─────────────────────────────────────────────────────────────┘

□ 1. improvement > 0.05 (улучшение > 5%)
□ 2. p_value < 0.05 (статистически значимо)
□ 3. CV версии A < 0.10 (стабильно)
□ 4. CV версии B < 0.10 (стабильно)
□ 5. direction_consistent = True (все прогоны в одном направлении)
□ 6. total_outliers = 0 (нет выбросов)
□ 7. total_iterations >= 5 (минимум 5 прогонов)
□ 8. total_runs >= 15 (минимум 15 total runs)

ЕСЛИ ВСЕ ✅ → PROMOTE TO PROD
ЕСЛИ ХОТЯ БЫ ОДИН ❌ → NEEDS_MORE_TESTING
```

---

### 💡 Рекомендации

#### Когда нужно больше тестов:

1. **p-value > 0.05** → Увеличить количество итераций
2. **CV > 10%** → Проверить сценарии на стабильность
3. **Есть выбросы** → Исследовать причины выбросов
4. **direction_consistent = False** → Разбить на подгруппы сценариев

#### Как уменьшить вариацию:

1. **Увеличить количество сценариев** (минимум 5-10)
2. **Увеличить количество итераций** (минимум 10-20)
3. **Исключить нестабильные сценарии** (с высокой вариацией)
4. **Нормализовать данные** (если есть систематические различия)

#### Когда можно снизить требования:

1. **Критичные исправления** → Можно promote при p < 0.10
2. **Некритичные улучшения** → Требуется p < 0.01 и CV < 5%
3. **Экспериментальные функции** → Можно promote при improvement > 10% даже с CV < 15%

---

    async def promote_version(
        self,
        capability: str,
        from_version: str,
        to_version: str
    ) -> bool:
        """
        Продвижение версии промпта в active статус.

        ТРЕБУЕТ:
        - FileSystemDataSource для записи в ФС
        - Обновления registry.yaml

        ARGS:
        - capability: имя capability
        - from_version: текущая active версия
        - to_version: новая версия для продвижения

        RETURNS:
        - bool: True если успешно
        """
        # 1. Получаем промпт новой версии
        new_prompt = self.data_repository.get_prompt(capability, to_version)

        # 2. Получаем промпт текущей версии
        old_prompt = self.data_repository.get_prompt(capability, from_version)

        # 3. Обновляем статусы (через FileSystemDataSource)
        # ПРИМЕЧАНИЕ: Требуется реализация в FileSystemDataSource
        await self.data_repository.update_prompt_status(
            capability=capability,
            version=from_version,
            new_status=PromptStatus.INACTIVE
        )
        await self.data_repository.update_prompt_status(
            capability=capability,
            version=to_version,
            new_status=PromptStatus.ACTIVE
        )
        
        # 4. Обновляем registry.yaml
        await self._update_registry(capability, to_version)
        
        # 5. Публикуем событие
        await self.event_bus.publish(
            EventType.VERSION_PROMOTED,
            data={
                'capability': capability,
                'from_version': from_version,
                'to_version': to_version,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        return True

    async def _update_registry(self, capability: str, version: str):
        """
        Обновление registry.yaml с новой активной версией.
        
        ФОРМАТ registry.yaml:
        ```yaml
        profile: prod
        prompt_versions:
          planning.create_plan: v1.1.0
          sql_generation.generate: v2.0.0
        input_contract_versions:
          planning.create_plan.input: v1.0.0
        output_contract_versions:
          planning.create_plan.output: v1.0.0
        ```
        
        ARGS:
        - capability: имя capability (например, 'planning.create_plan')
        - version: новая активная версия (например, 'v1.1.0')
        """
        import yaml
        
        registry_path = self.data_dir.parent / 'registry.yaml'
        
        # 1. Загрузка текущего registry.yaml
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry_data = yaml.safe_load(f)
        
        # 2. Обновление prompt_versions
        if 'prompt_versions' not in registry_data:
            registry_data['prompt_versions'] = {}
        
        old_version = registry_data['prompt_versions'].get(capability)
        registry_data['prompt_versions'][capability] = version
        
        # 3. Сохранение с бэкапом
        if old_version:
            backup_path = registry_path.with_suffix('.yaml.bak')
            import shutil
            shutil.copy2(registry_path, backup_path)
        
        with open(registry_path, 'w', encoding='utf-8') as f:
            yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        # 4. Логирование
        self.logger.info(
            f"Registry обновлён: {capability} {old_version} → {version}"
        )
```

---

### DataRepository: update_prompt_status

**Файл:** `core/application/data_repository.py` (расширить)

```python
class DataRepository:
    """
    Централизованный р��������������������позиторий с единой точкой валидации структуры данных.
    """

    def __init__(self, data_source: ResourceDataSource, profile: str = "prod"):
        self.data_source = data_source
        self.profile = profile
        self._initialized = False
        self.logger = logging.getLogger(__name__)

        # ТИПИЗИРОВАННЫЕ индексы
        self._prompts_index: Dict[Tuple[str, str], Prompt] = {}
        self._contracts_index: Dict[Tuple[str, str, str], Contract] = {}
        self._manifest_cache: Dict[str, Manifest] = {}

        # Кэши
        self._prompt_content_cache: Dict[Tuple[str, str], str] = {}
        self._contract_schema_cache: Dict[Tuple[str, str, str], Type[BaseModel]] = {}

        self._validation_errors: List[str] = []
        self._validation_warnings: List[str] = []

    # === СУЩЕСТВУЮЩИЕ МЕТОДЫ ===
    # initialize(), load_manifests(), get_prompt(), get_contract(), etc.

    # === НОВЫЕ МЕТОДЫ ДЛЯ PROMOTE/REJECT ===

    async def update_prompt_status(
        self,
        capability: str,
        version: str,
        new_status: PromptStatus
    ) -> bool:
        """
        Обновление статуса промпта в файловой системе.
        
        ИСПОЛЬЗОВАНИЕ:
        - При продвижении версии (DRAFT → ACTIVE)
        - При откате версии (ACTIVE → INACTIVE)
        
        ARGS:
        - capability: имя capability (например, 'planning.create_plan')
        - version: версия промпта (например, 'v1.1.0')
        - new_status: новый статус (ACTIVE, INACTIVE, DRAFT, etc.)
        
        RETURNS:
        - bool: True если успешно
        
        RAISES:
        - FileNotFoundError: если промпт не найден
        - IOError: если не удалось записать файл
        """
        # 1. Получаем текущий промпт
        current_prompt = self.get_prompt(capability, version)
        
        # 2. Создаём новый промпт с обновлённым статусом
        updated_prompt = Prompt(
            capability=current_prompt.capability,
            version=current_prompt.version,
            status=new_status,  # ← Обновляем статус
            component_type=current_prompt.component_type,
            content=current_prompt.content,
            variables=current_prompt.variables,
            metadata={
                **current_prompt.metadata,
                'status_changed_at': datetime.now().isoformat(),
                'previous_status': current_prompt.status.value
            }
        )
        
        # 3. Сохраняем через DataSource
        await self.data_source.save_prompt(capability, version, updated_prompt)
        
        # 4. Обновляем кэш
        self._prompts_index[(capability, version)] = updated_prompt
        
        self.logger.info(
            f"Статус промпта обновлён: {capability}@{version} "
            f"{current_prompt.status.value} → {new_status.value}"
        )
        
        return True

    async def update_contract_status(
        self,
        capability: str,
        version: str,
        direction: str,
        new_status: PromptStatus
    ) -> bool:
        """
        Обновление статуса контракта в файловой системе.
        
        ARGS:
        - capability: имя capability
        - version: версия контракта
        - direction: направление ('input' или 'output')
        - new_status: новый статус
        
        RETURNS:
        - bool: True если успешно
        """
        # 1. Получаем теку��ий контракт
        current_contract = self.get_contract(capability, version, direction)
        
        # 2. Создаём новый контракт с обновлённым статусом
        updated_contract = Contract(
            capability=current_contract.capability,
            version=current_contract.version,
            status=new_status,  # ← Обновляем статус
            component_type=current_contract.component_type,
            direction=current_contract.direction,
            schema_data=current_contract.schema_data,
            description=current_contract.description
        )
        
        # 3. Сохраняем через DataSource
        await self.data_source.save_contract(capability, version, direction, updated_contract)
        
        # 4. Обновляем кэш
        self._contracts_index[(capability, version, direction)] = updated_contract
        
        self.logger.info(
            f"Статус контракта обновлён: {capability}@{version} ({direction}) "
            f"{current_contract.status.value} → {new_status.value}"
        )
        
        return True

    async def get_prompt_versions(self, capability: str) -> List[Prompt]:
        """
        Получить все версии промпта для capability.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - List[Prompt]: список версий, отсортированный по версии
        """
        versions = []
        for (cap, ver), prompt in self._prompts_index.items():
            if cap == capability:
                versions.append(prompt)
        
        # Сортировка по семантической версии
        return sorted(versions, key=lambda p: self._parse_version(p.version))

    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """
        Парсинг семантической версии.
        
        ПРИМЕР:
        v1.2.3 → (1, 2, 3)
        """
        import re
        match = re.match(r'v(\d+)\.(\d+)\.(\d+)', version)
        if match:
            return tuple(map(int, match.groups()))
        return (0, 0, 0)

    async def get_active_version(self, capability: str) -> Optional[str]:
        """
        Получить текущую активную версию capability.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - str: версия или None если нет активной
        """
        versions = await self.get_prompt_versions(capability)
        active_versions = [v for v in versions if v.status == PromptStatus.ACTIVE]
        
        if active_versions:
            return active_versions[0].version
        return None

    async def get_draft_versions(self, capability: str) -> List[str]:
        """
        Получить все draft версии capability.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - List[str]: список draft версий
        """
        versions = await self.get_prompt_versions(capability)
        draft_versions = [v.version for v in versions if v.status == PromptStatus.DRAFT]
        return draft_versions
```

---

### FileSystemDataSource: save_prompt

**Файл:** `core/infrastructure/storage/file_system_data_source.py` (расширить)

```python
class FileSystemDataSource(ResourceDataSource):
    """
    Источник данных на базе файловой системы.
    Поддерживает чтение и запись промптов/контрактов.
    """

    def __init__(self, data_dir: Path, registry_config: Dict[str, Any]):
        self.data_dir = data_dir
        self.registry_config = registry_config
        self.logger = logging.getLogger(__name__)

    def initialize(self):
        """Инициализация источника данных"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"FileSystemDataSource инициализирован: {self.data_dir}")

    async def load_prompt(self, capability: str, version: str) -> Prompt:
        """Загрузка промпта (существующая реализация)"""
        # ... существующий код ...
        pass

    async def save_prompt(
        self,
        capability: str,
        version: str,
        prompt: Prompt
    ) -> Path:
        """
        Сохранение промпта в файловую систему.
        
        ФОРМАТ ПУТИ:
        data/prompts/{component_type}/{capability_path}/{name}_{version}.yaml
        
        ПРИМЕР:
        data/prompts/skills/planning/create_plan_v1.1.0.yaml
        
        ARGS:
        - capability: имя capability
        - version: версия
        - prompt: объект Prompt для сохранения
        
        RETURNS:
        - Path: путь к сохранённому файлу
        
        RAISES:
        - IOError: если не удалось сохранить
        """
        import yaml
        
        # 1. Определяем путь
        capability_path = capability.replace('.', '/')
        
        if prompt.component_type == ComponentType.SKILL:
            base_subdir = 'skills'
        elif prompt.component_type == ComponentType.SERVICE:
            base_subdir = 'services'
        elif prompt.component_type == ComponentType.TOOL:
            base_subdir = 'tools'
        else:
            base_subdir = 'prompts'
        
        prompt_dir = self.data_dir / base_subdir / capability_path
        prompt_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Имя файла
        capability_parts = capability.split('.')
        file_name = f"{capability_parts[-1]}_{version}.yaml"
        prompt_file = prompt_dir / file_name
        
        # 3. Сериализация в YAML
        yaml_data = {
            'capability': prompt.capability,
            'version': prompt.version,
            'status': prompt.status.value,
            'component_type': prompt.component_type.value,
            'content': prompt.content,
            'variables': [v.model_dump() for v in prompt.variables],
            'metadata': prompt.metadata
        }
        
        # 4. Запись файла
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        self.logger.info(f"Промпт сохранён: {prompt_file}")
        return prompt_file

    async def save_contract(
        self,
        capability: str,
        version: str,
        direction: str,
        contract: Contract
    ) -> Path:
        """
        Сохранение контракта в файловую систему.
        
        ФОРМАТ ПУТИ:
        data/contracts/{component_type}/{capability_path}/{name}_{version}_{direction}.yaml
        
        ПРИМЕР:
        data/contracts/skills/planning/create_plan_v1.0.0_input.yaml
        
        ARGS:
        - capability: имя capability
        - version: версия
        - direction: 'input' или 'output'
        - contract: объект Contract для сохранения
        
        RETURNS:
        - Path: путь к сохранённому файлу
        """
        import yaml
        
        capability_path = capability.replace('.', '/')
        
        if contract.component_type == ComponentType.SKILL:
            base_subdir = 'skills'
        else:
            base_subdir = 'contracts'
        
        contract_dir = self.data_dir / base_subdir / capability_path
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        contract_parts = capability.split('.')
        file_name = f"{contract_parts[-1]}_{version}_{direction}.yaml"
        contract_file = contract_dir / file_name
        
        yaml_data = {
            'capability': contract.capability,
            'version': contract.version,
            'status': contract.status.value,
            'component_type': contract.component_type.value,
            'direction': contract.direction.value,
            'schema_data': contract.schema_data,
            'description': contract.description
        }
        
        with open(contract_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        self.logger.info(f"Контракт сохранён: {contract_file}")
        return contract_file

    async def list_prompts(self) -> List[Prompt]:
        """Сканирование всех промптов (существующая реализация)"""
        # ... существующий код ...
        pass

    async def list_contracts(self) -> List[Contract]:
        """Сканирование всех контрактов (существующая реализация)"""
        # ... существующий код ...
        pass
```

---

### Пример использования update_prompt_status

```python
# 1. Инициализация
data_source = FileSystemDataSource(Path('data'), registry_config)
data_source.initialize()

data_repository = DataRepository(data_source, profile='prod')
await data_repository.initialize(app_config)

# 2. Продвижение версии (DRAFT → ACTIVE)
await data_repository.update_prompt_status(
    capability='planning.create_plan',
    version='v1.1.0',
    new_status=PromptStatus.ACTIVE
)

# 3. Откат предыдущей версии (ACTIVE → INACTIVE)
await data_repository.update_prompt_status(
    capability='planning.create_plan',
    version='v1.0.0',
    new_status=PromptStatus.INACTIVE
)

# 4. Проверка
active_version = await data_repository.get_active_version('planning.create_plan')
print(f"Active версия: {active_version}")  # → v1.1.0

draft_versions = await data_repository.get_draft_versions('planning.create_plan')
print(f"Draft версии: {draft_versions}")  # → []
```

---

### Пример использования _update_registry

```python
# В BenchmarkService.promote_version()
await self._update_registry('planning.create_plan', 'v1.1.0')

# registry.yaml ДО:
"""
profile: prod
prompt_versions:
  planning.create_plan: v1.0.0
  sql_generation.generate: v2.0.0
"""

# registry.yaml ПОСЛЕ:
"""
profile: prod
prompt_versions:
  planning.create_plan: v1.1.0  # ← Обновлено
  sql_generation.generate: v2.0.0
"""
```

---

### Полный цикл promote_version

```python
# 1. Запуск бенчмарка
comparison = await benchmark_service.compare_versions(
    version_a='v1.0.0',
    version_b='v1.1.0-draft',
    scenarios=scenarios
)

# comparison.improvement = 0.12 (12% улучшение!)

# 2. Решение о продвижении
if comparison.improvement > 0.05:
    # 3. Обновление статусов промптов
    await data_repository.update_prompt_status(
        capability='planning.create_plan',
        version='v1.0.0',
        new_status=PromptStatus.INACTIVE  # ← Старая версия
    )
    await data_repository.update_prompt_status(
        capability='planning.create_plan',
        version='v1.1.0-draft',
        new_status=PromptStatus.ACTIVE  # ← Новая версия
    )
    
    # 4. Обновление registry.yaml
    await benchmark_service._update_registry(
        capability='planning.create_plan',
        version='v1.1.0'  # Без -draft
    )
    
    # 5. Публикация события
    await event_bus.publish(
        EventType.VERSION_PROMOTED,
        data={
            'capability': 'planning.create_plan',
            'from_version': 'v1.0.0',
            'to_version': 'v1.1.0'
        }
    )
    
    print("✅ Версия продвинута: v1.0.0 → v1.1.0")
```

---

## 🏗️ OptimizationService

### Назначение

**Файл:** `core/application/services/optimization_service.py`

```python
class OptimizationService(BaseService):
    """
    Сервис оптимизации промптов и контрактов.
    
    ОТВЕЧАЕТ ЗА:
    - Запуск циклов оптимизации (Manual/Automatic/Target)
    - Анализ неудач (FailureAnalysis)
    - Генерацию новых версий (через PromptContractGenerator)
    - Координацию с BenchmarkService для A/B тестирования
    
    ЗАВИСИМОСТИ:
    - BenchmarkService (сравнение версий)
    - PromptContractGenerator (генерация вариантов)
    - MetricsCollector (получение метрик)
    - DataRepository (доступ к версиям)
    """

    def __init__(
        self,
        benchmark_service: BenchmarkService,
        prompt_generator: PromptContractGenerator,
        metrics_collector: MetricsCollector,
        data_repository: DataRepository,
        llm_provider: Any
    ):
        self.benchmark_service = benchmark_service
        self.prompt_generator = prompt_generator
        self.metrics_collector = metrics_collector
        self.data_repository = data_repository
        self.llm_provider = llm_provider

    async def start_optimization_cycle(
        self,
        capability: str,
        mode: OptimizationMode,
        target_metric: Optional[TargetMetric] = None,
        max_iterations: int = 20,
        scenarios: Optional[List[BenchmarkScenario]] = None
    ) -> OptimizationResult:
        """
        Запуск цикла оптимизации.
        
        РЕЖИМЫ:
        - Manual: ручная оптимизация по запросу
        - Automatic: при ухудшении метрик
        - Target: стремление к целевой метрике
        
        ARGS:
        - capability: имя capability для оптимизации
        - mode: режим оптимизации
        - target_metric: целевая метрика (для Target режима)
        - max_iterations: максимум итераций
        - scenarios: сценарии для бенчмарка
        
        RETURNS:
        - OptimizationResult: результат оптимизации
        """
        # 1. Получаем текущую версию
        current_version = await self._get_active_version(capability)
        
        # 2. Получаем базовые метрики
        current_metrics = await self.metrics_collector.get_aggregated_metrics(
            capability=capability,
            version=current_version,
            time_range=(datetime.now() - timedelta(days=7), datetime.now())
        )
        
        # 3. Проверяем необходимость оптимизации
        if mode == OptimizationMode.AUTOMATIC:
            if not await self._needs_optimization(capability, current_metrics):
                return OptimizationResult(
                    status='not_needed',
                    reason='Метрики в норме'
                )
        
        # 4. Запускаем цикл итераций
        best_version = current_version
        best_metrics = current_metrics
        
        for iteration in range(max_iterations):
            # 4.1. Анализ неудач
            failure_analysis = await self._analyze_failures(
                capability=capability,
                version=current_version
            )
            
            # 4.2. Генерация новой версии
            new_version = await self.prompt_generator.generate_prompt_variant(
                capability=capability,
                base_version=current_version,
                optimization_goal=self._get_optimization_goal(mode, target_metric),
                failure_analysis=failure_analysis
            )
            
            # 4.3. A/B тестирование
            comparison = await self.benchmark_service.compare_versions(
                version_a=current_version,
                version_b=new_version,
                scenarios=scenarios or await self._get_default_scenarios(capability)
            )
            
            # 4.4. Сохраняем лучшую версию
            if comparison.improvement > 0:
                best_version = new_version
                best_metrics = comparison.metrics_b
            
            # 4.5. Проверяем достижение цели
            if mode == OptimizationMode.TARGET and target_metric:
                if self._target_achieved(best_metrics, target_metric):
                    break
        
        # 5. Продвигаем лучшую версию
        if best_version != current_version:
            await self.benchmark_service.promote_version(
                capability=capability,
                from_version=current_version,
                to_version=best_version
            )
        
        return OptimizationResult(
            status='completed',
            best_version=best_version,
            final_metrics=best_metrics,
            iterations=iteration + 1
        )

    async def _analyze_failures(
        self,
        capability: str,
        version: str
    ) -> FailureAnalysis:
        """Анализ неудач для генерации улучшений"""
        # Получаем логи ошибок
        error_logs = await self.metrics_collector.log_collector.get_by_capability(
            capability=capability,
            log_type='error',
            time_range=(datetime.now() - timedelta(days=7), datetime.now())
        )
        
        # Получаем метрики
        metrics = await self.metrics_collector.get_aggregated_metrics(
            capability=capability,
            version=version,
            time_range=(datetime.now() - timedelta(days=7), datetime.now())
        )
        
        # Анализируем паттерны ошибок
        error_patterns = self._extract_error_patterns(error_logs)
        
        # Определяем сценарии провалов
        failure_scenarios = self._identify_failure_scenarios(error_logs)
        
        # Генерируем предложения исправлений
        suggested_fixes = await self._generate_fix_suggestions(
            error_patterns,
            failure_scenarios
        )
        
        return FailureAnalysis(
            capability=capability,
            version=version,
            failure_count=metrics.total_executions - int(metrics.success_rate * metrics.total_executions),
            total_executions=metrics.total_executions,
            error_patterns=error_patterns,
            common_failure_scenarios=failure_scenarios,
            suggested_fixes=suggested_fixes
        )

    def _extract_error_patterns(self, error_logs: List[LogEntry]) -> List[Dict[str, Any]]:
        """Извлечение паттернов ошибок из логов"""
        patterns = {}
        
        for log in error_logs:
            error_type = log.data.get('error_type', 'Unknown')
            if error_type not in patterns:
                patterns[error_type] = {
                    'type': error_type,
                    'count': 0,
                    'examples': []
                }
            patterns[error_type]['count'] += 1
            if len(patterns[error_type]['examples']) < 3:
                patterns[error_type]['examples'].append(log.data.get('error_message', ''))
        
        return list(patterns.values())

    def _identify_failure_scenarios(self, error_logs: List[LogEntry]) -> List[str]:
        """Определение сценариев, где происходят ошибки"""
        scenarios = set()
        
        for log in error_logs:
            # Извлекаем контекст выполнения
            context = log.data.get('context_snapshot', {})
            step_number = context.get('step_number', 'unknown')
            input_params = context.get('input_parameters', {})
            
            # Формируем описание сценария
            scenario_desc = f"Step {step_number}: {input_params}"
            scenarios.add(scenario_desc)
        
        return list(scenarios)

    async def _generate_fix_suggestions(
        self,
        error_patterns: List[Dict[str, Any]],
        failure_scenarios: List[str]
    ) -> List[str]:
        """Генерация предложений исправлений через LLM"""
        prompt = f"""
Проанализируй ошибки и предложи исправления для промпта:

Ошибки:
{json.dumps(error_patterns, indent=2)}

Сценарии провалов:
{json.dumps(failure_scenarios, indent=2)}

Предложи конкретные исправления для промпта:
1. ...
2. ...
3. ...
"""
        
        response = await self.llm_provider.generate(prompt)
        return response.strip().split('\n')

    def _get_optimization_goal(
        self,
        mode: OptimizationMode,
        target_metric: Optional[TargetMetric]
    ) -> str:
        """Определение цели оптимизации"""
        if mode == OptimizationMode.TARGET and target_metric:
            return f"Достичь {target_metric.name} >= {target_metric.target_value}"
        elif mode == OptimizationMode.AUTOMATIC:
            return "Устранить ошибки и улучшить метрики"
        else:
            return "Улучшить качество ответов"

    def _target_achieved(
        self,
        metrics: AggregatedMetrics,
        target: TargetMetric
    ) -> bool:
        """Проверка достижения целевой метрики"""
        current_value = getattr(metrics, target.name, 0.0)
        return current_value >= target.target_value - target.tolerance

    async def _get_active_version(self, capability: str) -> str:
        """Получение текущей active версии"""
        versions = await self.data_repository.get_prompt_versions(capability)
        active_versions = [v for v in versions if v.status == PromptStatus.ACTIVE]
        return active_versions[0].version if active_versions else 'v1.0.0'

    async def _get_default_scenarios(
        self,
        capability: str
    ) -> List[BenchmarkScenario]:
        """Получение сценариев по умолчанию для capability"""
        # Загрузка из data/benchmarks/scenarios/{capability}/
        pass

    async def _needs_optimization(
        self,
        capability: str,
        metrics: AggregatedMetrics
    ) -> bool:
        """
        Проверка необходимости оптимизации.
        
        КРИТЕРИИ (все должны быть True):
        1. Метрики ниже порога (success_rate < 0.9 или accuracy < 0.85)
        2. Есть данные для анализа (минимум 10 выполнений)
        3. Нет активной оптимизации
        4. Capability разрешена для оптимизации
        
        ARGS:
        - capability: имя capability
        - metrics: текущие метрики
        
        RETURNS:
        - bool: True если оптимизация нужна
        """
        # 1. Проверка минимального количества данных
        if metrics.total_executions < 10:
            self.logger.warning(
                f"Недостаточно данных для {capability}: "
                f"{metrics.total_executions} < 10"
            )
            return False
        
        # 2. Проверка метрик
        needs_improvement = (
            metrics.success_rate < 0.9 or 
            metrics.accuracy < 0.85
        )
        
        if not needs_improvement:
            self.logger.info(
                f"Метрики {capability} в норме: "
                f"success_rate={metrics.success_rate:.1%}, "
                f"accuracy={metrics.accuracy:.1%}"
            )
            return False
        
        # 3. Проверка, что capability разрешена для оптимизации
        if not await self._is_capability_optimizable(capability):
            return False
        
        # 4. Проверка, что нет активной оптимизации
        if await self._is_optimization_in_progress(capability):
            self.logger.warning(
                f"Оптимизация {capability} уже выполняется"
            )
            return False
        
        self.logger.info(
            f"Оптимизация {capability} необходима: "
            f"success_rate={metrics.success_rate:.1%}, "
            f"accuracy={metrics.accuracy:.1%}"
        )
        return True

    async def _is_capability_optimizable(self, capability: str) -> bool:
        """
        Проверка, разрешена ли оптимизация для capability.
        
        НЕЛЬЗЯ ОПТИМИЗИРОВАТЬ:
        - Критические компоненты (помечены в manifest.yaml)
        - Стабильные версии (active > 30 дней без проблем)
        - Заблокированные capability (в blacklist)
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - bool: True если можно оптимизировать
        """
        # 1. Проверка blacklist
        blacklist = [
            'core.system',  # Системные компоненты
            'security.*',   # Компоненты безопасности
        ]
        
        for pattern in blacklist:
            if pattern.endswith('*'):
                if capability.startswith(pattern[:-1]):
                    self.logger.warning(
                        f"Capability {capability} в blacklist (паттерн {pattern})"
                    )
                    return False
            elif capability == pattern:
                self.logger.warning(
                    f"Capability {capability} в blacklist"
                )
                return False
        
        # 2. Проверка манифеста
        manifest = self.data_repository.get_manifest(
            component_type='skill',
            component_id=capability.split('.')[0]
        )
        
        if manifest and manifest.quality_metrics:
            if not manifest.quality_metrics.auto_optimize:
                self.logger.warning(
                    f"Оптимизация запрещена в манифесте {capability}"
                )
                return False
        
        # 3. Проверка "стабильности" версии
        active_version = await self.get_active_version(capability)
        if active_version:
            active_prompt = self.data_repository.get_prompt(
                capability, active_version
            )
            
            # Если версия active больше 30 дней и метрики хорошие
            days_active = (datetime.now() - active_prompt.created_at).days
            if days_active > 30:
                metrics = await self.metrics_collector.get_aggregated_metrics(
                    capability=capability,
                    version=active_version,
                    time_range=(datetime.now() - timedelta(days=7), datetime.now())
                )
                
                if metrics.success_rate >= 0.95 and metrics.accuracy >= 0.90:
                    self.logger.info(
                        f"Capability {capability} стабильна ({days_active} дней), "
                        f"оптимизация не требуется"
                    )
                    return False
        
        return True

    async def _is_optimization_in_progress(self, capability: str) -> bool:
        """
        Проверка, выполняется ли уже оптимизация для capability.
        
        ИСПОЛЬЗУЕТ:
        - Файл блокировки: data/locks/optimization_{capability}.lock
        - Возраст lock < 1 часа
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - bool: True если оптимизация выполняется
        """
        lock_file = Path('data/locks') / f'optimization_{capability.replace(".", "_")}.lock'
        
        if not lock_file.exists():
            return False
        
        # Проверка возраста lock
        lock_age = datetime.now() - datetime.fromtimestamp(lock_file.stat().st_mtime)
        
        if lock_age.total_seconds() < 3600:  # 1 час
            return True
        
        # Старый lock - удаляем
        lock_file.unlink()
        return False

    async def _acquire_optimization_lock(self, capability: str) -> bool:
        """
        Установка блокировки оптимизации.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - bool: True если блокировка установлена
        """
        lock_file = Path('data/locks') / f'optimization_{capability.replace(".", "_")}.lock'
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            lock_file.write_text(f'{datetime.now().isoformat()}\n')
            return True
        except IOError:
            return False

    async def _release_optimization_lock(self, capability: str):
        """Освобождение блокировки оптимизации"""
        lock_file = Path('data/locks') / f'optimization_{capability.replace(".", "_")}.lock'
        if lock_file.exists():
            lock_file.unlink()
```

---

## 📊 Как сервис понимает что можно улучшать

### Матрица решений

```
┌─────────────────────────────────────────────────────────────┐
│           МОЖНО ЛИ ОПТИМИЗИРОВАТЬ CAPABILITY?               │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │  start_optimi-  │
                    │  zation_cycle() │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 1. Достаточно   │
                    │    данных?      │
                    │  (total >= 10)  │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ NO                          │ YES
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ ОТКАЗ:          │           │ 2. Метрики      │
    │ "Недостаточно   │           │    ниже порога? │
    │  данных"        │           │ (SR<0.9 OR      │
    └─────────────────┘           │  ACC<0.85)      │
                                  └────────┬────────┘
                                           │
                             ┌─────────────┴─────────────┐
                             │ NO                        │ YES
                             ▼                           ▼
                   ┌─────────────────┐         ┌─────────────────┐
                   │ ОТКАЗ:          │         │ 3. Capability   │
                   │ "Метрики в      │         │    разрешена?   │
                   │  норме"         │         │ (не blacklist)  │
                   └─────────────────┘         └────────┬────────┘
                                                        │
                                          ┌─────────────┴─────────────┐
                                          │ NO                        │ YES
                                          ▼                           ▼
                                ┌─────────────────┐         ┌─────────────────┐
                                │ ОТКАЗ:          │         │ 4. Нет активной │
                                │ "Запрещено      │         │    оптимизации? │
                                │  манифестом"    │         │ (lock file)     │
                                └─────────────────┘         └────────┬────────┘
                                                                     │
                                                       ┌─────────────┴─────────────┐
                                                       │ NO                        │ YES
                                                       ▼                           ▼
                                             ┌─────────────────┐         ┌─────────────────┐
                                             │ ОТКАЗ:          │         │ ✅ МОЖНО        │
                                             │ "Оптимизация    │         │ ЗАПУСКАТЬ       │
                                             │  выполняется"   │         │ ОПТИМИЗАЦИЮ     │
                                             └─────────────────┘         └─────────────────┘
```

---

### Критерии разрешения оптимизации

| Критерий | Условие | Почему |
|----------|---------|--------|
| **Достаточно данных** | `total_executions >= 10` | Нельзя оптимизировать по 1-2 выполнениям |
| **Метрики ниже порога** | `success_rate < 0.9` ИЛИ `accuracy < 0.85` | Если всё хорошо — не трогаем |
| **Не в blacklist** | Не совпадает с паттернами | Системные и security компоненты не трогаем |
| **Разрешено манифестом** | `auto_optimize: true` | Явное разрешение в конфигурации |
| **Не стабильная версия** | active < 30 дней ИЛИ метрики < 0.95 | Стабильные версии не оптимизируем |
| **Нет активной оптимизации** | lock file отсутствует | Защита от параллельных оптимизаций |

---

### Blacklist (нельзя оптимизировать)

```python
blacklist = [
    'core.system',      # Системные компоненты
    'security.*',       # Всё что начинается с 'security.'
    'auth.*',           # Аутентификация
    'audit.*',          # Аудит и логирование
]

# Примеры:
'core.system.init'        → ❌ Нельзя (паттерн 'core.system')
'security.validator'      → ❌ Нельзя (паттерн 'security.*')
'auth.login'              → ❌ Нельзя (паттерн 'auth.*')
'planning.create_plan'    → ✅ Можно (нет в blacklist)
'sql_generation.generate' → ✅ Можно (нет в blacklist)
```

---

### Manifest: явный запрет/разрешение

**data/manifests/skills/planning/manifest.yaml:**

```yaml
component_id: planning
component_type: skill
version: v1.0.0
status: active

# ← Явное разрешение/запрет оптимизации:
quality_metrics:
  auto_optimize: false  # ← Запрет автоматической оптимизации
  success_rate_target: 0.95
  accuracy_target: 0.90

# Если auto_optimize: false → только ручная оптимизация
```

---

### Примеры решений сервиса

#### Пример 1: Достаточно данных, метрики плохие

```python
metrics = AggregatedMetrics(
    capability='planning.create_plan',
    total_executions=100,      # >= 10 ✅
    success_rate=0.78,         # < 0.9 ✅
    accuracy=0.82              # < 0.85 ✅
)

needs_optimization = await optimization_service._needs_optimization(
    'planning.create_plan',
    metrics
)
# → True ✅ (можно оптимизировать)
```

---

#### Пример 2: Недостаточно данных

```python
metrics = AggregatedMetrics(
    capability='new_capability',
    total_executions=5,        # < 10 ❌
    success_rate=0.60,
    accuracy=0.70
)

needs_optimization = await optimization_service._needs_optimization(
    'new_capability',
    metrics
)
# → False ❌
# Лог: "Недостаточно данных для new_capability: 5 < 10"
```

---

#### Пример 3: Метрики в норме

```python
metrics = AggregatedMetrics(
    capability='stable_capability',
    total_executions=500,
    success_rate=0.96,         # >= 0.9 ✅
    accuracy=0.93              # >= 0.85 ✅
)

needs_optimization = await optimization_service._needs_optimization(
    'stable_capability',
    metrics
)
# → False ❌
# Лог: "Метрики stable_capability в норме: success_rate=96%, accuracy=93%"
```

---

#### Пример 4: Blacklist

```python
metrics = AggregatedMetrics(
    capability='security.validator',
    total_executions=100,
    success_rate=0.75,
    accuracy=0.80
)

needs_optimization = await optimization_service._needs_optimization(
    'security.validator',
    metrics
)
# → False ❌
# Лог: "Capability security.validator в blacklist (паттерн security.*)"
```

---

#### Пример 5: Запрет манифестом

```yaml
# data/manifests/skills/legacy/manifest.yaml
component_id: legacy
quality_metrics:
  auto_optimize: false  # ← Явный запрет
```

```python
metrics = AggregatedMetrics(
    capability='legacy.process',
    total_executions=100,
    success_rate=0.70,
    accuracy=0.65
)

needs_optimization = await optimization_service._needs_optimization(
    'legacy.process',
    metrics
)
# → False ❌
# Лог: "Оптимизация запрещена в манифесте legacy.process"
```

---

#### Пример 6: Активная оптимизация (lock)

```python
# Файл существует: data/locks/optimization_planning_create_plan.lock
# Возраст: 30 минут (< 1 часа)

needs_optimization = await optimization_service._needs_optimization(
    'planning.create_plan',
    metrics
)
# → False ❌
# Лог: "Оптимизация planning.create_plan уже выполняется"
```

---

### Полный цикл проверки

```python
async def start_optimization_cycle(
    self,
    capability: str,
    mode: OptimizationMode,
    ...
) -> OptimizationResult:
    # 1. Получаем метрики
    current_metrics = await self.metrics_collector.get_aggregated_metrics(...)
    
    # 2. Проверяем необходимость (для AUTOMATIC режима)
    if mode == OptimizationMode.AUTOMATIC:
        if not await self._needs_optimization(capability, current_metrics):
            return OptimizationResult(
                status='not_needed',
                reason='Метрики в норме или недостаточно данных'
            )
    
    # 3. Устанавливаем lock
    if not await self._acquire_optimization_lock(capability):
        return OptimizationResult(
            status='failed',
            reason='Оптимизация уже выполняется'
        )
    
    try:
        # 4. Запускаем оптимизацию
        # ... цикл итераций ...
        
        return OptimizationResult(
            status='completed',
            best_version=best_version,
            ...
        )
    finally:
        # 5. Освобождаем lock
        await self._release_optimization_lock(capability)
```

---

### Таблица решений

| Сценарий | total_exec | success_rate | accuracy | blacklist | manifest | lock | Решение |
|----------|------------|--------------|----------|-----------|----------|------|---------|
| Новая capability | 5 | 0.60 | 0.65 | ❌ | auto | ❌ | ❌ Недостаточно данных |
| Плохие метрики | 100 | 0.75 | 0.80 | ❌ | auto | ❌ | ✅ Оптимизировать |
| Хорошие метрики | 500 | 0.96 | 0.93 | ❌ | auto | ❌ | ❌ Метрики в норме |
| Security компонент | 100 | 0.70 | 0.75 | ✅ | auto | ❌ | ❌ Blacklist |
| Запрет манифеста | 100 | 0.70 | 0.75 | ❌ | false | ❌ | ❌ Запрет |
| Активная оптимизация | 100 | 0.70 | 0.75 | ❌ | auto | ✅ | ❌ Уже выполняется |
| Ручной режим | 100 | 0.95 | 0.92 | ❌ | auto | ❌ | ✅ Всегда можно |

---

### Рекомендации по настройке порогов

| Порог | Значение | Когда изменить |
|-------|----------|----------------|
| `total_executions >= 10` | Минимум данных | Увеличить до 50 для критичных компонентов |
| `success_rate < 0.9` | Надёжность | Увеличить до 0.95 для prod |
| `accuracy < 0.85` | Качество | Увеличить до 0.90 для важных capability |
| `lock_age < 3600` | Timeout | Уменьшить до 1800 для быстрых циклов |
| `days_active > 30` | Стабильность | Увеличить до 90 для стабильных версий |

---

### OptimizationResult

**Файл:** `core/models/data/benchmark.py`

```python
@dataclass
class OptimizationResult:
    """
    Результат цикла оптимизации.
    """
    status: str                      # 'completed', 'not_needed', 'failed'
    best_version: str = ""
    final_metrics: Optional[AggregatedMetrics] = None
    iterations: int = 0
    reason: str = ""                 # Для 'not_needed' или 'failed'
    improvement: float = 0.0         # Процент улучшения
```

---

### Пример использования

```python
# 1. Ручная оптимизация
result = await optimization_service.start_optimization_cycle(
    capability='planning.create_plan',
    mode=OptimizationMode.MANUAL,
    max_iterations=10
)

# 2. Оптимизация с целевой метрикой
result = await optimization_service.start_optimization_cycle(
    capability='sql_generation.generate',
    mode=OptimizationMode.TARGET,
    target_metric=TargetMetric(
        name='accuracy',
        target_value=0.95,
        current_value=0.87
    ),
    max_iterations=20,
    scenarios=[scenario_1, scenario_2]
)

# 3. Автоматическая оптимизация (при ухудшении)
result = await optimization_service.start_optimization_cycle(
    capability='text.summarize',
    mode=OptimizationMode.AUTOMATIC,
    max_iterations=5
)

print(f"""
Оптимизация завершена:
- Статус: {result.status}
- Лучшая версия: {result.best_version}
- Итераций: {result.iterations}
- Улучшение: {result.improvement:.1%}
""")
```

---

## 📋 Сводная таблица: Классы vs Словари

| Компонент | ❌ Словари (неправильно) | ✅ Классы (правильно) |
|-----------|-------------------------|----------------------|
| **Сценарий** | `{'goal': '...', 'expected': {...}}` | `BenchmarkScenario(...)` |
| **Ожидаемый ответ** | `{'steps': 5, 'fields': [...]}` | `ExpectedOutput(structured_data={...})` |
| **Критерий** | `{'type': 'min_count', 'value': 5}` | `EvaluationCriterion(name='min_count', ...)` |
| **Результат** | `{'accuracy': 0.73, 'success': True}` | `BenchmarkResult(accuracy=0.73, ...)` |
| **Оценка** | `{'score': 0.6, 'details': '...'}` | `CriterionScore(score=0.6, ...)` |

---

## 📊 Модели данных

### AggregatedMetrics

**Файл:** `core/models/data/metrics.py` (новый)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum


class MetricType(str, Enum):
    """Типы метрик"""
    GAUGE = "gauge"       # Точечное значение (accuracy, success_rate)
    COUNTER = "counter"   # Счётчик (tokens_used, cost)
    HISTOGRAM = "histogram"  # Распределение (latency)


@dataclass
class MetricRecord:
    """
    Отдельная запись метрики.
    """
    agent_id: str
    capability: str
    execution_time_ms: float
    success: bool
    tokens_used: int
    timestamp: datetime
    session_id: Optional[str] = None
    correlation_id: str = ""
    version: Optional[str] = None
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class AggregatedMetrics:
    """
    Агрегированные метрики для capability/версии.
    """
    capability: str
    version: str
    time_range: Tuple[datetime, datetime]
    
    # Основные метрики
    accuracy: float = 0.0           # Точность ответов
    success_rate: float = 0.0       # Процент успешных выполнений
    latency_ms: float = 0.0         # Среднее время выполнения
    latency_p95_ms: float = 0.0     # 95-й перцентиль
    latency_p99_ms: float = 0.0     # 99-й перцентиль
    tokens_used: int = 0            # Всего токенов
    total_executions: int = 0       # Всего выполнений
    error_rate: float = 0.0         # Процент ошибок
    
    # Дополнительные метрики
    cost: float = 0.0               # Стоимость выполнения
    retry_count: int = 0            # Количество повторных попыток
    
    def is_better_than(self, other: 'AggregatedMetrics', threshold: float = 0.05) -> bool:
        """Проверяет, лучше ли текущие метрики чем другие"""
        return (
            self.accuracy >= other.accuracy + threshold and
            self.success_rate >= other.success_rate + threshold and
            self.latency_ms <= other.latency_ms * 0.9  # На 10% быстрее
        )
```

### Benchmark Models

**Файл:** `core/models/data/benchmark.py` (новый)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class OptimizationMode(str, Enum):
    """Режимы оптимизации"""
    MANUAL = "manual"           # Ручная оптимизация по запросу
    AUTOMATIC = "automatic"     # Автоматический цикл при ухудшении
    TARGET = "target"           # Стремление к целевой метрике


@dataclass
class BenchmarkScenario:
    """
    Сценарий бенчмарка — описание тестовой задачи.
    """
    id: str
    name: str
    description: str
    goal: str                    # Цель, которую должен достичь агент
    input_data: Dict[str, Any]   # Входные данные
    expected_output: Dict[str, Any]  # Ожидаемый результат
    success_criteria: Dict[str, Any]  # Критерии успеха
    timeout_seconds: int = 300
    allowed_capabilities: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """
    Результат запуска бенчмарка.
    """
    scenario_id: str
    versions: Dict[str, str]     # {capability: version}
    metrics: AggregatedMetrics
    success: bool
    execution_time_ms: float
    timestamp: datetime
    agent_id: str
    session_id: str
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionComparison:
    """
    Сравнение двух версий capability.
    """
    capability: str
    version_a: str
    version_b: str
    scenarios_run: int
    improvement: float           # Процент улучшения
    best_version: str
    metrics_a: AggregatedMetrics
    metrics_b: AggregatedMetrics
    recommendation: str          # "promote", "reject", "needs_more_testing"


@dataclass
class FailureAnalysis:
    """
    Анализ неудач для генерации улучшений.
    """
    capability: str
    version: str
    failure_count: int
    total_executions: int
    error_patterns: List[Dict[str, Any]]
    common_failure_scenarios: List[str]
    suggested_fixes: List[str]


@dataclass
class TargetMetric:
    """
    Целевая метрика для оптимизации.
    """
    name: str                    # Например, "accuracy"
    target_value: float          # Целевое значение
    current_value: float         # Текущее значение
    tolerance: float = 0.02      # Допустимое отклонение
```

---

## 📊 Сбор метрик

### Через EventBus (рекомендуется)

**Файл:** `core/infrastructure/event_bus/event_bus.py` (расширить)

```python
class EventType(Enum):
    # ... существующие ...

    # ← НОВЫЕ для benchmark/learning:
    # Используем существующее METRIC_COLLECTED вместо METRIC_RECORDED
    BENCHMARK_STARTED = "benchmark.started"
    BENCHMARK_COMPLETED = "benchmark.completed"
    OPTIMIZATION_CYCLE_STARTED = "optimization.cycle_started"
    OPTIMIZATION_CYCLE_COMPLETED = "optimization.cycle_completed"
    VERSION_PROMOTED = "version.promoted"
    VERSION_REJECTED = "version.rejected"
```

### Инструментирование компонентов

**Файл:** `core/application/skills/base_skill.py` (расширить)

```python
class BaseSkill(BaseComponent):
    async def execute(self, capability, parameters, context):
        start_time = time.time()
        success = False

        try:
            # ← Существующая логика
            result = await self._execute_impl(capability, parameters, context)
            success = True
            return result

        finally:
            # ← Публикация метрик (всегда, даже при ошибке)
            await self._publish_metrics(
                capability=capability.name,
                execution_time_ms=(time.time() - start_time) * 1000,
                success=success,
                context=context
            )

    async def _publish_metrics(self, capability, execution_time_ms, success, context):
        """Публикация метрик в EventBus"""
        await self.application_context.infrastructure_context.event_bus.publish(
            EventType.SKILL_EXECUTED,
            data={
                'agent_id': self.application_context.id,
                'capability': capability,
                'execution_time_ms': execution_time_ms,
                'success': success,
                'session_id': getattr(context, 'session_id', None),
                'step_number': getattr(context, 'current_step', None)
            },
            source=self.name
        )
```

### Типы метрик

| Метрика | Тип | Описание |
|---------|-----|----------|
| `accuracy` | gauge | Точность ответов |
| `latency` | histogram | Время выполнения |
| `token_usage` | counter | Использование токенов |
| `success_rate` | gauge | Процент успешных выполнений |
| `cost` | counter | Стоимость выполнения |
| `error_rate` | gauge | Процент ошибок |

---

## 📏 Уровни агрегации метрик

### Два уровня сбора

```
┌─────────────────────────────────────────────────────────────┐
│                    УРОВНИ МЕТРИК                            │
└─────────────────────────────────────────────────────────────┘

1. Уровень ШАГА (capability-level)
   └── Публикуется при выполнении КАЖДОЙ capability
       └── EventType.SKILL_EXECUTED
       └── MetricRecord: capability, execution_time_ms, success

2. Уровень СЕССИИ (session-level)
   └── Агрегируется из всех шагов сессии
       └── BenchmarkResult: total_steps, total_time, overall_success
```

### Метрики уровня ШАГА

**Источник:** `BaseSkill._publish_metrics()` при каждом выполнении

**Запись в хранилище:**
```python
MetricRecord(
    agent_id='agent-123',
    capability='planning.create_plan',  # ← Конкретная capability
    version='v1.0.0',
    execution_time_ms=150.5,
    success=True,
    tokens_used=250,
    step_number=1,                       # ← Номер шага в сессии
    session_id='session-456',
    timestamp=datetime.now()
)
```

**Агрегация по шагам:**
```python
# Пример: метрики для planning.create_plan@v1.0.0 за неделю
AggregatedMetrics(
    capability='planning.create_plan',
    version='v1.0.0',
    total_executions=150,        # 150 вызовов capability
    success_rate=0.93,           # 93% успешных
    latency_ms=145.2,            # среднее время
    latency_p95_ms=320.0,        # 95-й перцентиль
)
```

**Использование:**
- Сравнение версий промптов/контрактов
- Выявление деградации конкретной capability
- Оптимизация отдельных компонентов

---

### Метрики уровня СЕССИИ

**Источник:** Агрегация всех шагов сессии + оценка бенчмарка

**Запись в хранилище:**
```python
SessionMetrics(
    agent_id='agent-123',
    session_id='session-456',
    scenario_id='benchmark-001',  # Для бенчмарков
    total_steps=5,                # 5 вызовов capability
    total_time_ms=2500.0,         # Сумма всех шагов
    total_tokens=1250,            # Сумма токенов
    success=True,                 # Все шаги успешны ИЛИ цель достигнута
    goal_accuracy=0.95,           # Насколько результат близок к цели
    capabilities_used=[           # Какие capability использованы
        'planning.create_plan',
        'sql_query.execute',
        'text.summarize'
    ],
    timestamp=datetime.now()
)
```

**Агрегация по сессиям:**
```python
# Пример: метрики сессий для бенчмарка planning@v1.0.0
SessionAggregatedMetrics(
    capability='planning.create_plan',
    version='v1.0.0',
    total_sessions=50,           # 50 тестовых сессий
    goal_success_rate=0.88,      # 88% сессий достигли цели
    avg_steps_per_session=4.2,   # среднее число шагов
    avg_time_per_session=2100.0, # среднее время сессии
)
```

**Использование:**
- Оценка качества работы агента в целом
- Бенчмарки: сравнение версий по достижению цели
- KPI: "% задач выполнено с первого раза"

---

### Сравнение уровней

| Характеристика | Уровень ШАГА | Уровень СЕССИИ |
|----------------|--------------|----------------|
| **Гранулярность** | Одна capability | Вся сессия агента |
| **Частота записи** | ~100-1000/час | ~10-100/час |
| **Что измеряет** | Производительность компонента | Достигнута ли цель |
| **Агрегация** | По capability + version | По сценарию + version |
| **Для оптимизации** | Промпты, контракты | Поведение агента, цепочки |
| **Пример вопроса** | "Насколько быстр planning?" | "Справляется ли агент с задачей?" |

---

### Пример: полный цикл метрик

```
Сессия: agent-123, session-456, goal="Создать SQL запрос"

Шаг 1: planning.create_plan@v1.0.0
  → execution_time_ms: 150, success: True, tokens: 200

Шаг 2: sql_generation.generate@v1.2.0
  → execution_time_ms: 300, success: True, tokens: 400

Шаг 3: sql_validator.validate@v1.0.0
  → execution_time_ms: 50, success: True, tokens: 50

└── Сессия завершена:
    total_steps: 3
    total_time_ms: 500
    total_tokens: 650
    success: True
    goal_accuracy: 1.0  # Цель достигнута полностью
```

---

### Реализация агрегации сессии

**Файл:** `core/infrastructure/metrics_collector.py` (дополнить)

```python
class MetricsCollector:
    async def _on_skill_executed(self, event: Event):
        """Сбор метрик шага"""
        # ... запись MetricRecord ...

    async def finalize_session_metrics(
        self,
        agent_id: str,
        session_id: str,
        scenario_id: Optional[str] = None
    ) -> SessionMetrics:
        """
        Агрегация метрик сессии после завершения.

        Вызывается когда агент завершил работу.
        """
        # 1. Получаем все шаги сессии
        step_records = await self.storage.get_records(
            agent_id=agent_id,
            session_id=session_id
        )

        # 2. Агрегируем
        total_steps = len(step_records)
        total_time = sum(r.execution_time_ms for r in step_records)
        total_tokens = sum(r.tokens_used for r in step_records)
        all_success = all(r.success for r in step_records)

        # 3. Оцениваем достижение цели (для бенчмарков)
        goal_accuracy = await self._calculate_goal_accuracy(
            session_id=session_id,
            scenario_id=scenario_id
        )

        return SessionMetrics(
            agent_id=agent_id,
            session_id=session_id,
            scenario_id=scenario_id,
            total_steps=total_steps,
            total_time_ms=total_time,
            total_tokens=total_tokens,
            success=all_success,
            goal_accuracy=goal_accuracy,
            capabilities_used=list(set(r.capability for r in step_records))
        )
```

---

### Когда вызывать агрегацию сессии

**Файл:** `core/application/agent/agent.py` (дополнить)

```python
class Agent:
    async def run(self, goal: str) -> AgentResult:
        session_id = str(uuid.uuid4())

        try:
            # ... выполнение сессии ...
            result = await self._execute_session(goal)

            # Агрегация метрик сессии
            session_metrics = await self.metrics_collector.finalize_session_metrics(
                agent_id=self.id,
                session_id=session_id,
                scenario_id=self.scenario_id  # Для бенчмарков
            )

            return result

        finally:
            # Публикация события завершения сессии
            await self.event_bus.publish(
                EventType.AGENT_COMPLETED,
                data={
                    'agent_id': self.id,
                    'session_id': session_id,
                    'session_metrics': session_metrics
                }
            )
```

---

## 📝 Сбор логов

### Централизованный LogCollector

**Файл:** `core/infrastructure/log_collector.py`

```python
class LogCollector:
    async def _on_capability_selected(self, event: Event):
        """Логирование выбора capability для анализа решений агента"""
        log_entry = LogEntry(
            timestamp=event.timestamp,
            agent_id=event.data.get('agent_id'),
            session_id=event.data.get('session_id'),
            log_type='capability_selection',
            data={
                'capability': event.data.get('capability'),
                'parameters': event.data.get('parameters'),
                'reasoning': event.data.get('reasoning'),  # ← Важно для обучения!
                'pattern_id': event.data.get('pattern_id'),
            },
            correlation_id=event.correlation_id
        )
        await self.storage.save(log_entry)

    async def _on_error(self, event: Event):
        """Логирование ошибок для анализа неудач"""
        log_entry = LogEntry(
            timestamp=event.timestamp,
            agent_id=event.data.get('agent_id'),
            session_id=event.data.get('session_id'),
            log_type='error',
            data={
                'capability': event.data.get('capability'),
                'error_type': event.data.get('error_type'),
                'error_message': event.data.get('error_message'),
                'stack_trace': event.data.get('stack_trace'),
                'step_number': event.data.get('step_number'),
                'context_snapshot': event.data.get('context_snapshot')
            },
            correlation_id=event.correlation_id
        )
        await self.storage.save(log_entry)
```

### Контекст выполнения для обучения

**Файл:** `core/models/data/execution.py` (расширить)

```python
@dataclass
class ExecutionContextSnapshot:
    """
    Снимок контекста выполнения для анализа.

    СОХРАНЯЕТСЯ В ЛОГИ ДЛЯ ОБУЧЕНИЯ:
    - Какие capability были доступны
    - Какой паттерн поведения использовался
    - Какие решения принимал агент
    - Какие ошибки возникали
    """

    agent_id: str
    session_id: str
    step_number: int
    timestamp: datetime

    # Контекст решения
    available_capabilities: List[str]
    selected_capability: str
    behavior_pattern: str
    reasoning: str

    # Параметры выполнения
    input_parameters: Dict[str, Any]
    output_result: Optional[Dict[str, Any]]

    # Метрики
    execution_time_ms: float
    tokens_used: int
    success: bool

    # Ошибки
    error_type: Optional[str]
    error_message: Optional[str]

    # Версии ресурсов
    prompt_version: str
    contract_version: str
```

---

## 🔄 Цикл обучения

### Полная схема цикла обучения

```
┌─────────────────────────────────────────────────────────────┐
│              ПОЛНЫЙ ЦИКЛ ОБУЧЕНИЯ                           │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │   START         │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Выбор режима   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    MANUAL     │   │  AUTOMATIC    │   │    TARGET     │
│  (по запросу) │   │(при ухудшении)│   │ (к цели 0.95) │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        │          ┌────────▼────────┐          │
        │          │Метрики упали?   │          │
        │          │  < threshold    │          │
        │          └────────┬────────┘          │
        │                   │ YES               │
        │                   ▼                   │
        └───────────────────┼───────────────────┘
                            │
                  ┌─────────▼──────────┐
                  │ 1. Анализ неудач   │
                  │  ───────────────── │
                  │ • Сбор error logs  │
                  │ • Выявление паттер-│
                  │   нов ошибок       │
                  │ • Генерация fix    │
                  │   suggestions (LLM)│
                  └─────────┬──────────┘
                            │
                  ┌─────────▼──────────┐
                  │ 2. Генерация новой │
                  │    версии промпта  │
                  │  ───────────────── │
                  │ • Загрузка текущего│
                  │   промпта          │
                  │ • LLM генерация    │
                  │   улучшений        │
                  │ • Сохранение как   │
                  │   DRAFT версии     │
                  └─────────┬──────────┘
                            │
                  ┌─────────▼──────────┐
                  │ 3. A/B тестирование│
                  │  ───────────────── │
                  │ • Запуск бенчмарка │
                  │   для v_current    │
                  │ • Запуск бенчмарка │
                  │   для v_candidate  │
                  │ • Сравнение        │
                  │   accuracy         │
                  └─────────┬──────────┘
                            │
                  ┌─────────▼──────────┐
                  │ 4. Принятие решения│
                  │  ───────────────── │
                  │ improvement > 5%?  │
                  └─────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │ YES                       │ NO
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │ 5. PROMOTE      │         │ 5. DISCARD      │
    │ ──��──────────── │         │ ─────────────── │
    │ • Смена статуса │         │ • Удаление DRAFT│
    │   DRAFT→ACTIVE  │         │ • Логирование   │
    │ • Обновление    │         │   причины       │
    │   registry.yaml │         │                 │
    │ • EventBus event│         │                 │
    └────────┬────────┘         └────────┬────────┘
             │                           │
             ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │ iteration < max │         │ iteration < max │
    └────────┬────────┘         └────────┬────────┘
             │ YES                       │ YES
             └─────────────┬─────────────┘
                           │
                           ▼ NO
                  ┌─────────────────┐
                  │ 6. FINISH       │
                  │ ─────────────── │
                  │ • Возврат результата  │
                  │ • Логирование   │
                  └─────────────────┘
```

---

### Детальное описание этапов

#### Этап 1: Анализ неудач (Failure Analysis)

**Входные данные:**
- Логи ошибок за последние 7 дней
- Метрики выполнения (success_rate, accuracy)

**Процесс:**
```python
failure_analysis = await optimization_service._analyze_failures(
    capability='planning.create_plan',
    version='v1.0.0'
)

# Результат:
FailureAnalysis(
    capability='planning.create_plan',
    version='v1.0.0',
    failure_count=15,
    total_executions=100,
    error_patterns=[
        {
            'type': 'ContractValidationError',
            'count': 10,
            'examples': ['missing field query', 'invalid type for param']
        },
        {
            'type': 'TimeoutError',
            'count': 5,
            'examples': ['exceeded 30s limit']
        }
    ],
    common_failure_scenarios=[
        'Step 3: Complex SQL generation with multiple joins',
        'Step 1: Planning with ambiguous requirements'
    ],
    suggested_fixes=[
        'Добавить валидацию обязательных полей в промпт',
        'Указать конкретные типы параметров',
        'Оптимизировать промпт для сокращения токенов'
    ]
)
```

---

#### Этап 2: Генерация новой версии

**Входные данные:**
- Текущий промпт
- FailureAnalysis
- Цель оптимизации

**Процесс:**
```python
new_version = await prompt_generator.generate_prompt_variant(
    capability='planning.create_plan',
    base_version='v1.0.0',
    optimization_goal='Улучшить точность и снизить ошибки валидации',
    failure_analysis=failure_analysis
)

# LLM промпт для генерации:
"""
Улучши промпт для агента.

Текущий промпт:
{content}

Выявленные проблемы:
- Тип ошибки: ContractValidationError (10 случаев)
  Примеры: ['missing field query', 'invalid type for param']
- Тип ошибки: TimeoutError (5 случаев)

Цель оптимизации:
Улучшить точность и снизить ошибки валидации

Сгенерируй улучшенную версию промпта:
1. Сохрани структуру и переменные
2. Устраняй выявленные проблемы
3. Добавь конкретные инструкции
"""

# Результат: 'v1.1.0' (DRAFT)
```

---

#### Этап 3: A/B тестирование

**Входные данные:**
- Текущая версия: v1.0.0
- Кандидат: v1.1.0-draft
- Набор бенчмарк сценариев

**Процесс:**
```python
comparison = await benchmark_service.compare_versions(
    version_a='v1.0.0',
    version_b='v1.1.0-draft',
    scenarios=[
        BenchmarkScenario(id='test_001', goal='...', ...),
        BenchmarkScenario(id='test_002', goal='...', ...),
        BenchmarkScenario(id='test_003', goal='...', ...),
    ]
)

# Результат:
VersionComparison(
    capability='planning.create_plan',
    version_a='v1.0.0',
    version_b='v1.1.0-draft',
    scenarios_run=3,
    improvement=0.12,  # 12% улучшение!
    best_version='v1.1.0-draft',
    metrics_a=AggregatedMetrics(accuracy=0.78, ...),
    metrics_b=AggregatedMetrics(accuracy=0.90, ...),
    recommendation='promote'
)
```

---

#### Этап 4: Принятие решения

**Критерии:**

| Улучшение | Решение | Действие |
|-----------|---------|----------|
| > +5% | ✅ PROMOTE | Продвинуть версию |
| -5% ... +5% | ⚠️ NEEDS_MORE_TESTING | Дополнительные тесты |
| < -5% | ❌ REJECT | Отклонить версию |

**Процесс:**
```python
if comparison.improvement > 0.05:
    await benchmark_service.promote_version(
        capability='planning.create_plan',
        from_version='v1.0.0',
        to_version='v1.1.0-draft'
    )
    # → v1.1.0-draft → ACTIVE
    # → v1.0.0 → INACTIVE
```

---

#### Этап 5: Продвижение версии (Promote)

**Процесс:**
```python
async def promote_version(capability, from_version, to_version):
    # 1. Обновление статусов промптов
    await data_repository.update_prompt_status(
        capability=capability,
        version=from_version,
        new_status=PromptStatus.INACTIVE
    )
    await data_repository.update_prompt_status(
        capability=capability,
        version=to_version,
        new_status=PromptStatus.ACTIVE
    )
    
    # 2. Обновление registry.yaml
    # prompt_versions:
    #   planning.create_plan: v1.1.0
    
    # 3. Публикация события
    await event_bus.publish(
        EventType.VERSION_PROMOTED,
        data={
            'capability': capability,
            'from_version': from_version,
            'to_version': to_version
        }
    )
```

---

### Режимы обучения

| Режим | Описание | Когда использовать | Триггер |
|-------|----------|-------------------|---------|
| **Manual** | Ручная оптимизация по запросу | Для точечных улучшений | Команда разработчика |
| **Automatic** | Автоматический цикл при ухудшении метрик | Для поддержания качества | success_rate < 0.9 |
| **Target** | Стремление к целевой метрике | Для достижения KPI | accuracy < target |

---

### Пример использования

```python
# scripts/run_optimization.py

async def main():
    # 1. Инициализация
    infra = await InfrastructureContext.create(config)
    app_ctx = await ApplicationContext.create_from_registry(infra, profile="prod")

    # 2. Получение сервисов обучения
    optimization_service = app_ctx.get_service("optimization_service")

    # 3. Запуск цикла оптимизации
    result = await optimization_service.start_optimization_cycle(
        capability="planning.create_plan",
        mode=OptimizationMode.TARGET,
        target_metric=TargetMetric(
            name="accuracy",
            target_value=0.95,
            current_value=0.87
        ),
        max_iterations=20
    )

    # 4. Отчёт
    print(f"""
Оптимизация завершена:
- Статус: {result.status}
- Лучшая версия: {result.best_version}
- Итераций: {result.iterations}
- Улучшение: {result.improvement:.1%}
- Финальная точность: {result.final_metrics.accuracy:.1%}
""")
```

---

### CLI скрипты для бенчмарков

#### scripts/run_benchmark.py

```python
#!/usr/bin/env python3
"""
Запуск бенчмарков для оценки качества агента.

ИСПОЛЬЗОВАНИЕ:
    python scripts/run_benchmark.py --capability planning.create_plan --version v1.0.0
    python scripts/run_benchmark.py --compare v1.0.0 v1.1.0-draft
    python scripts/run_benchmark.py --all
"""
import asyncio
import argparse
from pathlib import Path
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.services.benchmark_service import BenchmarkService
from core.application.services.accuracy_evaluator import AccuracyEvaluatorService


async def run_single_benchmark(capability: str, version: str, scenarios_dir: Path):
    """Запуск бенчмарка для одной версии"""
    # Инициализация
    infra = await InfrastructureContext.create(config)
    app_ctx = await ApplicationContext.create_from_registry(infra, profile="sandbox")
    
    # Получение сервисов
    evaluator = AccuracyEvaluatorService(llm_provider)
    benchmark_service = BenchmarkService(evaluator, metrics_collector, data_repository, llm_provider)
    
    # Загрузка сценариев
    scenarios = load_scenarios(scenarios_dir / capability)
    
    # Запуск бенчмарков
    results = []
    for scenario in scenarios:
        result = await benchmark_service.run_benchmark(scenario, version)
        results.append(result)
        
        print(f"  {scenario.name}: accuracy={result.accuracy:.1%}")
    
    # Агрегация
    avg_accuracy = sum(r.accuracy for r in results) / len(results)
    print(f"\nСредняя точность ({capability}@{version}): {avg_accuracy:.1%}")
    
    return avg_accuracy


async def compare_versions(capability: str, version_a: str, version_b: str, scenarios_dir: Path):
    """Сравнение двух версий"""
    infra = await InfrastructureContext.create(config)
    app_ctx = await ApplicationContext.create_from_registry(infra, profile="sandbox")
    
    evaluator = AccuracyEvaluatorService(llm_provider)
    benchmark_service = BenchmarkService(evaluator, metrics_collector, data_repository, llm_provider)
    
    scenarios = load_scenarios(scenarios_dir / capability)
    
    comparison = await benchmark_service.compare_versions(version_a, version_b, scenarios)
    
    print(f"""
Сравнение версий ({capability}):
  {version_a}: accuracy={comparison.metrics_a.accuracy:.1%}
  {version_b}: accuracy={comparison.metrics_b.accuracy:.1%}
  
  Улучшение: {comparison.improvement:+.1%}
  Рекомендация: {comparison.recommendation}
""")
    
    return comparison


def load_scenarios(scenarios_dir: Path) -> List[BenchmarkScenario]:
    """Загрузка сценариев из YAML файлов"""
    scenarios = []
    for file in scenarios_dir.glob('*.yaml'):
        with open(file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            scenarios.append(BenchmarkScenario(**data))
    return scenarios


def main():
    parser = argparse.ArgumentParser(description='Запуск бенчмарков Agent_v5')
    parser.add_argument('--capability', type=str, help='Имя capability для тестирования')
    parser.add_argument('--version', type=str, default='v1.0.0', help='Версия для тестирования')
    parser.add_argument('--compare', nargs=2, metavar='VERSION', help='Сравнить две версии')
    parser.add_argument('--all', action='store_true', help='Запустить все бенчмарки')
    parser.add_argument('--scenarios-dir', type=Path, default='data/benchmarks/scenarios')
    
    args = parser.parse_args()
    
    if args.compare:
        asyncio.run(compare_versions(args.capability, args.compare[0], args.compare[1], args.scenarios_dir))
    elif args.capability:
        asyncio.run(run_single_benchmark(args.capability, args.version, args.scenarios_dir))
    elif args.all:
        # Запуск всех доступных бенчмарков
        pass


if __name__ == '__main__':
    main()
```

#### scripts/run_optimization.py

```python
#!/usr/bin/env python3
"""
Запуск цикла оптимизации промптов.

ИСПОЛЬЗОВАНИЕ:
    python scripts/run_optimization.py --capability planning.create_plan --mode target --target-accuracy 0.95
    python scripts/run_optimization.py --capability sql_generation.generate --mode automatic
"""
import asyncio
import argparse
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.services.optimization_service import OptimizationService
from core.models.data.benchmark import OptimizationMode, TargetMetric


async def run_optimization(capability: str, mode: str, target_accuracy: float = None, max_iterations: int = 20):
    """Запуск цикла оптимизации"""
    # Инициализация
    infra = await InfrastructureContext.create(config)
    app_ctx = await ApplicationContext.create_from_registry(infra, profile="sandbox")
    
    # Получение сервиса оптимизации
    optimization_service = app_ctx.get_service("optimization_service")
    
    # Определение режима
    if mode == 'target':
        opt_mode = OptimizationMode.TARGET
        target_metric = TargetMetric(
            name='accuracy',
            target_value=target_accuracy or 0.95,
            current_value=0.0  # Будет получено из метрик
        )
    elif mode == 'automatic':
        opt_mode = OptimizationMode.AUTOMATIC
        target_metric = None
    else:
        opt_mode = OptimizationMode.MANUAL
        target_metric = None
    
    # Запуск оптимизации
    print(f"Запуск оптимизации {capability} (режим: {mode})...")
    
    result = await optimization_service.start_optimization_cycle(
        capability=capability,
        mode=opt_mode,
        target_metric=target_metric,
        max_iterations=max_iterations
    )
    
    # Вывод результата
    print(f"""
═══════════════════════════════���═══════════════════
Результаты оптимизации
═══════════════════════════════════════════════════
Статус:           {result.status}
Лучшая версия:    {result.best_version}
Итераций:         {result.iterations}
Улучшение:        {result.improvement:+.1%}
Финальная accuracy: {result.final_metrics.accuracy:.1%}
═══════════════════════════════════════════════════
""")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Оптимизация промптов Agent_v5')
    parser.add_argument('--capability', type=str, required=True, help='Имя capability')
    parser.add_argument('--mode', type=str, choices=['manual', 'automatic', 'target'], default='manual')
    parser.add_argument('--target-accuracy', type=float, help='Целевая точность (для target режима)')
    parser.add_argument('--max-iterations', type=int, default=20, help='Максимум итераций')
    
    args = parser.parse_args()
    
    asyncio.run(run_optimization(
        args.capability,
        args.mode,
        args.target_accuracy,
        args.max_iterations
    ))


if __name__ == '__main__':
    main()
```

---

### Примеры использования CLI

```bash
# 1. Запуск бенчмарка для одной версии
python scripts/run_benchmark.py --capability planning.create_plan --version v1.0.0

# 2. Сравнение двух версий
python scripts/run_benchmark.py --capability planning.create_plan --compare v1.0.0 v1.1.0-draft

# 3. Запуск оптимизации с целевой метрикой
python scripts/run_optimization.py --capability planning.create_plan --mode target --target-accuracy 0.95

# 4. Автоматическая оптимизация (при ухудшении)
python scripts/run_optimization.py --capability sql_generation.generate --mode automatic

# 5. Ручная оптимизация
python scripts/run_optimization.py --capability text.summarize --mode manual --max-iterations 10
```

---

## 📅 План внедрения

### 🎯 Стратегия реализации

**Принцип:** Данные → Тесты → Реализация → Проверка

```
┌─────────────────────────────────────────────────────────────┐
│              ЦИКЛ РАЗРАБОТКИ (для каждого этапа)            │
└─────────────────────────────────────────────────────────────┘

1. ДАННЫЕ
   └→ Создаём модели данных
   └→ Определяем интерфейсы
   └→ [✓] Можно тестировать без реализации

2. ТЕСТЫ
   └→ Пишем юнит-тесты на модели
   └→ Пишем интеграционные тесты
   └→ [✓] Тесты падают (реализации ещё нет)

3. РЕАЛИЗАЦИЯ
   └→ Пишем код реализации
   └→ Следуем интерфейсам из этапа 1
   └→ [✓] Тесты проходят

4. ПРОВЕРКА
   └→ Запускаем тесты
   └→ Если не проходят → исправляем реализацию
   └→ [✓] Все тесты зелёные → следующий этап
```

**Преимущества:**
- ✅ Маленькие этапы (2-4 часа на каждый)
- ✅ Тесты пишутся ДО реализации (TDD)
- ✅ Быстрая обратная связь
- ✅ Легко откатить если что-то не так

---

### 📋 Этап 1: Модели данных (Фундамент)

**Цель:** Создать все модели данных без реализации

#### Этап 1.1: Модели метрик

**Файлы:**
- `core/models/data/metrics.py` (новый)

**Задачи:**
1. Создать `MetricType` (Enum: GAUGE, COUNTER, HISTOGRAM)
2. Создать `MetricRecord` (dataclass)
3. Создать `AggregatedMetrics` (dataclass)
4. Написать юнит-тесты

**Тесты:**
- `tests/unit/models/test_metrics.py`
  - `test_metric_record_creation()`
  - `test_aggregated_metrics_calculation()`
  - `test_is_better_than()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~2 часа

---

#### Этап 1.2: Модели бенчмарков

**Файлы:**
- `core/models/data/benchmark.py` (новый)

**Задачи:**
1. Создать `EvaluationType` (Enum)
2. Создать `EvaluationCriterion` (dataclass)
3. Создать `BenchmarkScenario` (dataclass)
4. Создать `ExpectedOutput` (dataclass)
5. Создать `ActualOutput` (dataclass)
6. Создать `BenchmarkResult` (dataclass)
7. Создать `AccuracyEvaluation` (dataclass)
8. Создать `CriterionScore` (dataclass)
9. Создать `VersionComparison` (dataclass)
10. Создать `FailureAnalysis` (dataclass)
11. Создать `TargetMetric` (dataclass)
12. Создать `OptimizationMode` (Enum)
13. Создать `OptimizationResult` (dataclass)
14. Написать юнит-тесты

**Тесты:**
- `tests/unit/models/test_benchmark.py`
  - `test_benchmark_scenario_creation()`
  - `test_expected_output_validation()`
  - `test_accuracy_evaluation_calculation()`
  - `test_version_comparison()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~4 часа

---

#### Этап 1.3: Модели логов

**Файлы:**
- `core/models/data/benchmark.py` (дополнить)

**Задачи:**
1. Создать `LogEntry` (dataclass)
2. Создать `LogType` (Enum: CAPABILITY_SELECTION, ERROR, BENCHMARK)
3. Написать юнит-тесты

**Тесты:**
- `tests/unit/models/test_logs.py`
  - `test_log_entry_creation()`
  - `test_log_entry_serialization()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~1 час

---

#### Этап 1.4: Интерфейсы хранилищ

**Файлы:**
- `core/infrastructure/interfaces/metrics_log_interfaces.py` (новый)

**Задачи:**
1. Создать `IMetricsStorage` (ABC)
2. Создать `ILogStorage` (ABC)
3. Написать тесты на интерфейсы

**Тесты:**
- `tests/unit/interfaces/test_storage_interfaces.py`
  - `test_imetrics_storage_interface()`
  - `test_ilog_storage_interface()`

**Критерий готовности:** Интерфейсы определены, тесты проходят ✅

**Время:** ~2 часа

---

#### Этап 1.5: Расширение EventBus

**Файлы:**
- `core/infrastructure/event_bus/event_bus.py` (существующий)

**Задачи:**
1. Добавить `EventType.BENCHMARK_STARTED`
2. Добавить `EventType.BENCHMARK_COMPLETED`
3. Добавить `EventType.OPTIMIZATION_CYCLE_STARTED`
4. Добавить `EventType.OPTIMIZATION_CYCLE_COMPLETED`
5. Добавить `EventType.VERSION_PROMOTED`
6. Добавить `EventType.VERSION_REJECTED`
7. Написать тесты

**Тесты:**
- `tests/unit/event_bus/test_event_types.py`
  - `test_new_event_types_exist()`

**Критерий готовности:** Новые EventType добавлены ✅

**Время:** ~1 час

---

### 📋 Этап 2: Хранилища (Инфраструктура)

**Цель:** Реализовать хранилища для метрик и логов

#### Этап 2.1: FileSystemMetricsStorage

**Файлы:**
- `core/infrastructure/metrics_storage.py` (новый)

**Задачи:**
1. Реализовать `FileSystemMetricsStorage` (IMetricsStorage)
2. Метод `record(metric)`
3. Метод `get_records(capability, version, time_range)`
4. Метод `aggregate(capability, version, time_range)`
5. Метод `clear_old(older_than)`
6. Написать юнит-тесты

**Тесты:**
- `tests/unit/storage/test_metrics_storage.py`
  - `test_record_metric()`
  - `test_get_records_filtering()`
  - `test_aggregate_metrics()`
  - `test_clear_old_metrics()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~4 часа

---

#### Этап 2.2: FileSystemLogStorage

**Файлы:**
- `core/infrastructure/log_storage.py` (новый)

**Задачи:**
1. Реализовать `FileSystemLogStorage` (ILogStorage)
2. Метод `save(entry)`
3. Метод `get_by_session(agent_id, session_id)`
4. Метод `get_by_capability(capability, log_type)`
5. Метод `clear_old(older_than)`
6. Написать юнит-тесты

**Тесты:**
- `tests/unit/storage/test_log_storage.py`
  - `test_save_log_entry()`
  - `test_get_session_logs()`
  - `test_get_capability_logs()`
  - `test_clear_old_logs()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~4 часа

---

### 📋 Этап 3: Сбор метрик (Инфраструктура)

**Цель:** Реализовать сбор метрик через EventBus

#### Этап 3.1: MetricsCollector

**Файлы:**
- `core/infrastructure/metrics_collector.py` (новый)

**Задачи:**
1. Реализовать `MetricsCollector`
2. Подписка на `EventType.SKILL_EXECUTED`
3. Подписка на `EventType.CAPABILITY_SELECTED`
4. Подписка на `EventType.ERROR_OCCURRED`
5. Метод `initialize()`
6. Метод `_on_skill_executed(event)`
7. Метод `get_aggregated_metrics()`
8. Написать юнит-тесты

**Тесты:**
- `tests/unit/infrastructure/test_metrics_collector.py`
  - `test_metrics_collector_initialization()`
  - `test_on_skill_executed_records_metric()`
  - `test_get_aggregated_metrics()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~4 часа

---

#### Этап 3.2: LogCollector

**Файлы:**
- `core/infrastructure/log_collector.py` (новый)

**Задачи:**
1. Реализовать `LogCollector`
2. Подписка на события
3. Метод `_on_capability_selected(event)`
4. Метод `_on_error(event)`
5. Метод `get_session_logs()`
6. Написать юнит-тесты

**Тесты:**
- `tests/unit/infrastructure/test_log_collector.py`
  - `test_log_collector_initialization()`
  - `test_on_capability_selected_logs()`
  - `test_on_error_logs()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~4 часа

---

#### Этап 3.3: Интеграция с InfrastructureContext

**Файлы:**
- `core/infrastructure/context/infrastructure_context.py` (существующий)

**Задачи:**
1. Добавить `metrics_storage` в `__init__`
2. Добавить `log_storage` в `__init__`
3. Добавить `metrics_collector` в `__init__`
4. Добавить `log_collector` в `__init__`
5. Инициализация в `initialize()`
6. Написать интеграционные тесты

**Тесты:**
- `tests/integration/test_infrastructure_context.py`
  - `test_metrics_collector_initialized()`
  - `test_log_collector_initialized()`

**Критерий готовности:** Инфраструктура инициализируется с новыми компонентами ✅

**Время:** ~2 часа

---

### 📋 Этап 4: Оценка точности (Application)

**Цель:** Реализовать оценку accuracy для бенчмарков

#### Этап 4.1: AccuracyEvaluator Service

**Файлы:**
- `core/application/services/accuracy_evaluator.py` (новый)
- `core/application/evaluators/` (новая папка)

**Задачи:**
1. Создать `IEvaluationStrategy` (Protocol)
2. Реализовать `AccuracyEvaluatorService`
3. Реализовать `ExactMatchEvaluator`
4. Реализовать `CoverageEvaluator`
5. Реализовать `SemanticEvaluator`
6. Реализовать `HybridEvaluator`
7. Написать юнит-тесты

**Тесты:**
- `tests/unit/services/test_accuracy_evaluator.py`
  - `test_exact_match_evaluation()`
  - `test_coverage_evaluation()`
  - `test_semantic_evaluation()`
  - `test_hybrid_evaluation()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~6 часов

---

#### Этап 4.2: Тесты AccuracyEvaluator

**Файлы:**
- `tests/unit/services/test_accuracy_evaluator.py` (дополнить)

**Задачи:**
1. Тесты на различные сценарии оценки
2. Тесты на граничные значения
3. Тесты на обработку ошибок
4. Интеграционные тесты с LLM

**Критерий готовности:** Покрытие тестов ≥ 90% ✅

**Время:** ~3 часа

---

### 📋 Этап 5: Бенчмарки (Application)

**Цель:** Реализовать сервис бенчмарков

#### Этап 5.1: BenchmarkService

**Файлы:**
- `core/application/services/benchmark_service.py` (новый)

**Задачи:**
1. Реализовать `BenchmarkService`
2. Метод `run_benchmark(scenario, version)`
3. Метод `compare_versions(version_a, version_b, scenarios)`
4. Метод `promote_version(capability, from_version, to_version)`
5. Метод `_update_registry(capability, version)`
6. Интеграция с `AccuracyEvaluator`
7. Написать юнит-тесты

**Тесты:**
- `tests/unit/services/test_benchmark_service.py`
  - `test_run_benchmark()`
  - `test_compare_versions()`
  - `test_promote_version()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~6 часов

---

#### Этап 5.2: Тесты BenchmarkService

**Файлы:**
- `tests/unit/services/test_benchmark_service.py` (дополнить)
- `tests/integration/test_benchmark_service.py` (новый)

**Задачи:**
1. Моки для зависимостей
2. Интеграционные тесты
3. Тесты на статистическую значимость
4. Тесты на устойчивость результатов

**Критерий готовности:** Покрытие тестов ≥ 90% ✅

**Время:** ~4 часа

---

### 📋 Этап 6: Оптимизация (Application)

**Цель:** Реализовать сервис оптимизации

#### Этап 6.1: PromptContractGenerator

**Файлы:**
- `core/application/services/prompt_contract_generator.py` (новый)

**Задачи:**
1. Реализовать `PromptContractGenerator`
2. Метод `generate_prompt_variant()`
3. Метод `_save_prompt(prompt)`
4. Метод `_generate_matching_contract(prompt)`
5. Метод `_save_contract(contract)`
6. Интеграция с `FileSystemDataSource`
7. Написать юнит-тесты

**Тесты:**
- `tests/unit/services/test_prompt_contract_generator.py`
  - `test_generate_prompt_variant()`
  - `test_save_prompt_to_filesystem()`
  - `test_generate_contract()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~6 часов

---

#### Этап 6.2: OptimizationService

**Файлы:**
- `core/application/services/optimization_service.py` (новый)

**Задачи:**
1. Реализовать `OptimizationService`
2. Метод `start_optimization_cycle()`
3. Метод `_analyze_failures()`
4. Метод `_needs_optimization()`
5. Метод `_is_capability_optimizable()`
6. Методы для lock (acquire/release)
7. Интеграция с `PromptContractGenerator`
8. Написать юнит-тесты

**Тесты:**
- `tests/unit/services/test_optimization_service.py`
  - `test_start_optimization_cycle()`
  - `test_analyze_failures()`
  - `test_needs_optimization()`
  - `test_optimization_lock()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~6 часов

---

### 📋 Этап 7: Интеграция (Application)

**Цель:** Интегрировать все компоненты

#### Этап 7.1: Расширение DataRepository

**Файлы:**
- `core/application/data_repository.py` (существующий)

**Задачи:**
1. Добавить `update_prompt_status()`
2. Добавить `update_contract_status()`
3. Добавить `get_prompt_versions()`
4. Добавить `get_active_version()`
5. Добавить `get_draft_versions()`
6. Написать тесты

**Тесты:**
- `tests/unit/test_data_repository.py`
  - `test_update_prompt_status()`
  - `test_get_prompt_versions()`
  - `test_get_active_version()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~4 часа

---

#### Этап 7.2: Расширение FileSystemDataSource

**Файлы:**
- `core/infrastructure/storage/file_system_data_source.py` (существующий)

**Задачи:**
1. Добавить `save_prompt()`
2. Добавить `save_contract()`
3. Написать тесты

**Тесты:**
- `tests/unit/storage/test_file_system_data_source.py`
  - `test_save_prompt()`
  - `test_save_contract()`

**Критерий готовности:** Все тесты проходят ✅

**Время:** ~3 часа

---

#### Этап 7.3: Расширение BaseSkill

**Файлы:**
- `core/application/skills/base_skill.py` (существующий)

**Задачи:**
1. Добавить `_publish_metrics()`
2. Интеграция с `MetricsCollector`
3. Публикация при выполнении
4. Написать тесты

**Тесты:**
- `tests/unit/skills/test_base_skill.py`
  - `test_publish_metrics_on_execute()`

**Критерий готовности:** Метрики публикуются при выполнении ✅

**Время:** ~3 часа

---

### 📋 Этап 8: CLI скрипты

**Цель:** Создать скрипты для запуска бенчмарков

#### Этап 8.1: run_benchmark.py

**Файлы:**
- `scripts/run_benchmark.py` (новый)

**Задачи:**
1. CLI аргументы (--capability, --version, --compare)
2. Запуск бенчмарков
3. Вывод результатов
4. Написать тесты

**Тесты:**
- `tests/test_cli/test_run_benchmark.py`

**Критерий готовности:** Скрипт работает ✅

**Время:** ~3 часа

---

#### Этап 8.2: run_optimization.py

**Файлы:**
- `scripts/run_optimization.py` (новый)

**Задачи:**
1. CLI аргументы (--capability, --mode, --target-accuracy)
2. Запуск оптимизации
3. Вывод результатов
4. Написать тесты

**Тесты:**
- `tests/test_cli/test_run_optimization.py`

**Критерий готовности:** Скрипт работает ✅

**Время:** ~3 часа

---

### 📋 Этап 9: E2E тестирование

**Цель:** Проверить полный цикл работы

#### Этап 9.1: E2E тесты бенчмарков

**Файлы:**
- `tests/e2e/test_benchmark_cycle.py` (новый)

**Задачи:**
1. Тест полного цикла бенчмарка
2. Тест сравнения версий
3. Тест продвижения версии

**Критерий готовности:** Все E2E тесты проходят ✅

**Время:** ~4 часа

---

#### Этап 9.2: E2E тесты оптимизации

**Файлы:**
- `tests/e2e/test_optimization_cycle.py` (новый)

**Задачи:**
1. Тест полного цикла оптимизации
2. Тест анализа неудач
3. Тест генерации новой версии

**Критерий готовности:** Все E2E тесты проходят ✅

**Время:** ~4 часа

---

### 📋 Этап 10: Документация и полировка

**Цель:** Завершить работу

#### Этап 10.1: Обновление документации

**Файлы:**
- `docs/BENCHMARK_LEARNING_PLAN.md` (существующий)

**Задачи:**
1. Обновить статусы задач
2. Добавить примеры использования
3. Обновить README

**Критерий готовности:** Документация актуальна ✅

**Время:** ~2 часа

---

#### Этап 10.2: Финальная проверка

**Задачи:**
1. Запустить все тесты
2. Проверить покрытие (≥ 90%)
3. Исправить замечания
4. Создать релизный тег

**Критерий готовности:** Все тесты проходят, покрытие ≥ 90% ✅

**Время:** ~4 часа

---

## 📊 Сводная таблица этапов

| Этап | Название | Задач | Время | Статус |
|------|----------|-------|-------|--------|
| 1 | Модели данных | 5 | ~10 часов | ✅ |
| 2 | Хранилища | 2 | ~8 часов | ✅ |
| 3 | Сбор метрик | 3 | ~10 часов | ✅ |
| 4 | Оценка точности | 2 | ~9 часов | ✅ |
| 5 | Бенчмарки | 2 | ~10 часов | ✅ |
| 6 | Оптимизация | 2 | ~12 часов | ✅ |
| 7 | Интеграция | 3 | ~10 часов | ✅ |
| 8 | CLI скрипты | 2 | ~6 часов | ⬜ |
| 9 | E2E тесты | 2 | ~8 часов | ⬜ |
| 10 | Документация | 2 | ~6 часов | ⬜ |

**Итого:** 25 задач, ~89 часов (~11 рабочих дней)

---

## 🎯 Приоритеты

### 🔴 Критические (Этапы 1-3)
- Без них не работает сбор метрик
- Время: ~28 часов

### 🟠 Важные (Этапы 4-6)
- Без них не работает оценка и оптимизация
- Время: ~31 часов

### 🟡 Желательные (Этапы 7-10)
- Интеграция и полировка
- Время: ~30 часов

---

## 📈 Прогресс

```
[████████████████████████████████████████████████████████████] 7/10 этапов выполнено (70%)
[██████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░] 20/25 задач выполнено (80%)
```

**Последнее обновление:** 2026-02-18
**Выполнено:** Этапы 1-7 (Модели + Хранилища + Сбор метрик + Оценка + Бенчмарки + Оптимизация + Интеграция)
**Тестов:** 321 тест, все проходят ✅
**Коммитов:** 16

### ✅ Выполнено (Этапы 1-7)

**Этап 1: Модели данных**
- `core/models/data/metrics.py`: MetricType, MetricRecord, AggregatedMetrics
- `core/models/data/benchmark.py`: 14 моделей + 4 Enum
- `core/infrastructure/interfaces/metrics_log_interfaces.py`: IMetricsStorage, ILogStorage
- `core/infrastructure/event_bus/event_bus.py`: 9 новых EventType
- Тесты: 97 тестов

**Этап 2: Хранилища**
- `core/infrastructure/metrics_storage.py`: FileSystemMetricsStorage
- `core/infrastructure/log_storage.py`: FileSystemLogStorage
- Тесты: 34 теста

**Этап 3: Сбор метрик**
- `core/infrastructure/metrics_collector.py`: MetricsCollector (подписка на события)
- `core/infrastructure/log_collector.py`: LogCollector (структурированное логирование)
- `core/infrastructure/context/infrastructure_context.py`: интеграция сборщиков
- Тесты: 45 тестов (unit: 39, integration: 6)

**Этап 4: Оценка точности**
- `core/application/services/accuracy_evaluator.py`: AccuracyEvaluatorService
- ExactMatchEvaluator, CoverageEvaluator, SemanticEvaluator, HybridEvaluator
- Тесты: 38 тестов

**Этап 5: Бенчмарки**
- `core/application/services/benchmark_service.py`: BenchmarkService
- run_benchmark, compare_versions, promote_version, auto_promote_if_better
- Тесты: 23 теста

**Этап 6: Оптимизация**
- `core/application/services/prompt_contract_generator.py`: PromptContractGenerator
- `core/application/services/optimization_service.py`: OptimizationService
- Тесты: 49 тестов (PromptContractGenerator: 30, OptimizationService: 30)

**Этап 7: Интеграция**
- `core/application/data_repository.py`: методы управления версиями (get_prompt_versions, get_active_version, update_prompt_status, add_prompt, etc.)
- `core/infrastructure/storage/file_system_data_source.py`: save_prompt, save_contract
- `core/application/skills/base_skill.py`: _publish_metrics()
- Тесты: 15 тестов интеграции

### ⬜ В ожидании (Этапы 8-10)

---

## 🔗 Ссылки

- [План внедрения](#-план-внедрения)
- [Изменение существующих компонентов](#-изменение-существующих-компонентов)
- [Тестирование](#-тестирование)

---

## 🔗 Интеграция с существующими компонентами

### EventBus (Расширить)

**Файл:** `core/infrastructure/event_bus/event_bus.py`

```python
class EventType(Enum):
    # Существующие события
    SYSTEM_INITIALIZED = "system.initialized"
    AGENT_CREATED = "agent.created"
    SKILL_EXECUTED = "skill.executed"
    METRIC_COLLECTED = "metric.collected"  # ← Уже су��ествует, используем

    # ← НОВЫЕ для benchmark/learning:
    BENCHMARK_STARTED = "benchmark.started"
    BENCHMARK_COMPLETED = "benchmark.completed"
    OPTIMIZATION_CYCLE_STARTED = "optimization.cycle_started"
    OPTIMIZATION_CYCLE_COMPLETED = "optimization.cycle_completed"
    VERSION_PROMOTED = "version.promoted"
    VERSION_REJECTED = "version.rejected"
```

### DataRepository (Расширить)

**Файл:** `core/application/data_repository.py`

```python
class DataRepository:
    async def get_prompt_versions(self, capability: str) -> List[Prompt]:
        """Получить все версии промпта для capability"""
        versions = []
        for (cap, ver), prompt in self._prompts_index.items():
            if cap == capability:
                versions.append(prompt)
        return sorted(versions, key=lambda p: p.version)

    async def compare_prompts(
        self,
        capability: str,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """Сравнить две версии промпта"""
        prompt_a = self.get_prompt(capability, version_a)
        prompt_b = self.get_prompt(capability, version_b)
        
        return {
            'version_a': version_a,
            'version_b': version_b,
            'content_length_a': len(prompt_a.content),
            'content_length_b': len(prompt_b.content),
            'variables_a': [v.name for v in prompt_a.variables],
            'variables_b': [v.name for v in prompt_b.variables],
            'metadata_diff': self._compare_metadata(prompt_a, prompt_b)
        }

    async def promote_version(
        self,
        capability: str,
        from_version: str,
        to_version: str
    ) -> bool:
        """
        Продвинут�� версию в active статус.
        ПРИМЕЧАНИЕ: Требует изменения статуса в файловой системе.
        """
        # Получаем промпт
        prompt = self.get_prompt(capability, to_version)
        
        # В реальной реализации:
        # 1. Найти файл промпта
        # 2. Обновить статус на ACTIVE
        # 3. Обновить registry.yaml
        # 4. Перезагрузить DataRepository
        
        raise NotImplementedError("Требуется реализация через FileSystemDataSource")
```

### Manifest (Расширить)

**Файл:** `core/models/data/manifest.py` (расширить)

```python
@dataclass
class PerformanceMetrics:
    """Секция метрик производительности в манифесте"""
    accuracy_target: float = 0.95
    latency_target_ms: int = 1000
    success_rate_target: float = 0.98
    auto_optimize: bool = False
    optimization_mode: str = "manual"  # manual | automatic | target


@dataclass
class Manifest:
    # ... существующие поля ...
    
    # ← НОВОЕ: секция метрик
    performance_metrics: Optional[PerformanceMetrics] = None
```

**Пример манифеста:**

```yaml
# data/manifests/skills/planning/manifest.yaml

component_id: planning
component_type: skill
version: v1.0.0
status: active
owner: alexey

# ← ДОБАВИТЬ секцию метрик:
performance_metrics:
  accuracy_target: 0.95
  latency_target_ms: 1000
  success_rate_target: 0.98
  auto_optimize: true
  optimization_mode: target  # manual | automatic | target

changelog:
  - version: v1.0.0
    date: "2026-02-17"
    author: alexey
    changes:
      - "Initial release"
      - "Added performance_metrics section"
```

---

## 🔧 Изменение существующих компонентов

### 1. Расширение Manifest

**Файл:** `core/models/data/manifest.py`

**Изменения:**
- Добавить класс `PerformanceMetrics`
- Добавить поле `performance_metrics` в `Manifest`

### 2. Расширение BaseSkill

**Файл:** `core/application/skills/base_skill.py`

**Изменения:**
- Добавить метод `_publish_metrics()`
- Вызывать в `execute()` после выполнения

### 3. Расширение EventBus

**Файл:** `core/infrastructure/event_bus/event_bus.py`

**Изменения:**
- Добавить новые `EventType` для бенчмарков

### 4. Расширение DataRepository

**Файл:** `core/application/data_repository.py`

**Изменения:**
- Добавить методы для работы с версиями
- Добавить методы сравнения и продвижения

---

## 🧪 Тестирование

### Юнит-тесты

**Файл:** `tests/unit/test_metrics_collector.py`

```python
import pytest
from datetime import datetime
from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.metrics_storage import MetricsStorage
from core.infrastructure.event_bus.event_bus import EventBus, EventType


@pytest.mark.asyncio
async def test_metrics_collector_records_skill_execution():
    """Тест: MetricsCollector записывает метрики выполнения навыка"""
    event_bus = EventBus()
    storage = MetricsStorage()  # Mock или in-memory
    collector = MetricsCollector(event_bus, storage)
    
    await collector.initialize()

    # Публикуем событие
    await event_bus.publish(
        EventType.SKILL_EXECUTED,
        data={
            'agent_id': 'test_agent',
            'capability': 'planning.create_plan',
            'execution_time_ms': 150,
            'success': True,
            'tokens_used': 100
        }
    )

    # Проверяем, что метрика записана
    metrics = await storage.get_metrics('planning.create_plan')
    assert len(metrics) == 1
    assert metrics[0].execution_time_ms == 150
    assert metrics[0].success == True


@pytest.mark.asyncio
async def test_aggregated_metrics_calculation():
    """Тест: Агрегация метрик работает корректно"""
    from core.models.data.metrics import AggregatedMetrics, MetricRecord
    
    records = [
        MetricRecord(
            agent_id='test',
            capability='test.cap',
            execution_time_ms=100,
            success=True,
            tokens_used=50,
            timestamp=datetime.now()
        ),
        MetricRecord(
            agent_id='test',
            capability='test.cap',
            execution_time_ms=200,
            success=False,
            tokens_used=60,
            timestamp=datetime.now()
        ),
    ]
    
    aggregated = AggregatedMetrics(
        capability='test.cap',
        version='v1.0.0',
        time_range=(datetime.now(), datetime.now()),
        total_executions=2,
        success_rate=0.5,  # 1 из 2 успешно
        latency_ms=150.0,  # среднее
        tokens_used=110
    )
    
    assert aggregated.success_rate == 0.5
    assert aggregated.latency_ms == 150.0
```

### Интеграционные тесты

**Файл:** `tests/integration/test_benchmark_service.py`

```python
import pytest
from core.application.services.benchmark_service import BenchmarkService
from core.models.data.benchmark import BenchmarkScenario, VersionComparison


@pytest.mark.asyncio
async def test_benchmark_service_compares_versions():
    """Тест: BenchmarkService сравнивает версии"""
    benchmark_service = BenchmarkService(
        metrics_collector=mock_metrics_collector,
        prompt_service=mock_prompt_service,
        contract_service=mock_contract_service,
        data_repository=mock_data_repository
    )

    scenario = BenchmarkScenario(
        id='test_scenario_1',
        name='Test Planning',
        description='Test planning scenario',
        goal='Create a plan for task X',
        input_data={'task': 'test'},
        expected_output={'plan': ['step1', 'step2']},
        success_criteria={'min_steps': 2}
    )

    result = await benchmark_service.compare_versions(
        capability='planning.create_plan',
        version_a='v1.0.0',
        version_b='v1.1.0-draft',
        scenarios=[scenario]
    )

    assert isinstance(result, VersionComparison)
    assert result.scenarios_run == 1
```

### E2E тесты

**Файл:** `tests/e2e/test_learning_cycle.py`

```python
import pytest
from core.application.services.learning_orchestrator import LearningOrchestratorService
from core.application.services.optimization_service import OptimizationService
from core.models.data.benchmark import OptimizationMode, TargetMetric


@pytest.mark.asyncio
async def test_full_learning_cycle():
    """Тест: Полный цикл обучения"""
    # 1. Запускаем бенчмарк
    benchmark_result = await benchmark_service.run_benchmark(
        scenario=test_scenario,
        agent_config=test_config
    )

    # 2. Генерируем новую версию
    new_version = await generator.generate_prompt_variant(
        capability='planning.create_plan',
        base_version='v1.0.0',
        optimization_goal='improve accuracy',
        failure_analysis=failure_analysis
    )

    # 3. Сравниваем версии
    comparison = await benchmark_service.compare_versions(
        capability='planning.create_plan',
        version_a='v1.0.0',
        version_b=new_version,
        scenarios=[test_scenario]
    )

    # 4. Продвигаем если лучше
    if comparison.improvement > 0.05:  # 5% улучшение
        promoted = await benchmark_service.auto_promote_if_better(
            capability='planning.create_plan',
            candidate_version=new_version,
            current_version='v1.0.0',
            metric_threshold=0.05
        )
        assert promoted == True
```

---

## ⚠️ Риски и митигация

| Риск | Влияние | Митигация |
|------|---------|-----------|
| Сложность интеграции | Высокое | Начинать с изолированного сервиса, постепенно интегрировать |
| Производительность | Среднее | Кэшировать метрики, асинхронная запись |
| Хранение данных | Среднее | Использовать SQLite для начала, потом PostgreSQL |
| Переобучение промптов | Высокое | Ограничивать количество итераций, валидировать на holdout наборе |
| Стоимость LLM вызовов | Высокое | Батчить запросы, использовать mock для тестов |

---

## 📈 Целевые метрики

| Метрика | Текущее | Цель | Срок |
|---------|---------|------|------|
| Точность агента | - | ≥ 0.95 | 3 месяца |
| Время оптимизации | - | ≤ 1 час | 2 месяца |
| Покрытие тестами | 78% | ≥ 90% | 3 месяца |
| Время инициализации | ~1200 мс | ≤ 100 мс | 2 месяца |

---

## 🎯 Следующие шаги

### Сегодня-завтра
- [ ] Создать `core/models/data/metrics.py`
- [ ] Создать `core/models/data/benchmark.py`
- [ ] Обновить `core/infrastructure/event_bus/event_bus.py`

### Неделя 1
- [ ] Реализовать `MetricsCollector` в Infrastructure
- [ ] Реализовать `LogCollector` в Infrastructure
- [ ] Создать `MetricsStorage` и `LogStorage`

### Неделя 2
- [ ] Создать `BenchmarkService` в Application
- [ ] Интегрировать с EventBus
- [ ] Написать юнит-тесты

### Неделя 3
- [ ] Создать `LearningOrchestrator`
- [ ] Создать `PromptContractGenerator`
- [ ] Написать интеграционные тесты

### Неделя 4
- [ ] Расширить `Manifest` с `performance_metrics`
- [ ] Расширить `BaseSkill` с `_publish_metrics()`
- [ ] Создать скрипты запуска бенчмарков

---

## 🔗 Ссылки

- [Архитектурный чек-лист](./architecture/checklist.md)
- [Идеальная архитектура](./architecture/ideal.md)
- [Руководство по компонентам](./COMPONENTS_GUIDE.md)
- [API Reference](./API_REFERENCE.md)
- [Troubleshooting](./TROUBLESHOOTING.md)

---

*Документ автоматически поддерживается в актуальном состоянии*
*Последнее обновление: 2026-02-17*

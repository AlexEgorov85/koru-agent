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
- [Модели данных](#-модели-данных)
- [Сбор метрик](#-сбор-метрик)
- [Сбор логов](#-сбор-логов)
- [Цикл обучения](#-цикл-обучения)
- [План внедрения](#-план-внедрения)
- [Интеграция с существующими компонентами](#-интеграция-с-существующими-компонентами)
- [Изменение существующих компонентов](#-изменение-существующих-компонентов)
- [Тестирование](#-тестирование)
- [Риски и митигация](#-риски-и-митигация)

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
    """

    def __init__(self, llm_provider: Any, file_tool: Any):
        self.llm_provider = llm_provider
        self.file_tool = file_tool

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

### Архитектурный поток

```
Start Optimization
       │
       ▼
  ┌─────────┐
  │ Mode?   │
  └────┬────┘
       ├─────────────┬─────────────┐
       ▼             ▼             ▼
  ┌────────┐   ┌──────────┐  ┌──────────┐
  │ Manual │   │Automatic │  │  Target  │
  └───┬────┘   └────┬─────┘  └────┬─────┘
      │            │              │
      │            ▼              │
      │     Metrics Degraded?     │
      │        ┌──┴──┐            │
      │        │     │            │
      │        ▼     ▼            │
      │      Yes    No            │
      │       │     │             │
      │       ▼     └─────────────┤
      │    Run Benchmark          │
      │                           │
      └───────────┬───────────────┘
                  ▼
         ┌────────────────┐
         │Analyze Failures│
         └───────┬────────┘
                 ▼
         ┌──────────────────┐
         │Generate Candidate│
         │    Prompt        │
         └───────┬──────────┘
                 ▼
         ┌────────────────┐
         │  Run A/B Test  │
         └───────┬────────┘
                 ▼
         ┌───────────────┐
         │Better Metrics?│
         └───────┬───────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
      Yes                No
        │                 │
        ▼                 ▼
  ┌──────────┐     ┌──────────┐
  │  Promote │     │ Discard  │
  │ Version  │     │ Candidate│
  └────┬─────┘     └────┬─────┘
       │                │
       ▼                ▼
  ┌──────────┐   ┌──────────────┐
  │  Update  │   │Max Iterations│
  │ Registry │   │   Reached?   │
  └────┬─────┘   └──────┬───────┘
       │                │
       └────────────────┤
                        ▼
                  End Optimization
```

### Режимы обучения

| Режим | Описание | Когда использовать |
|-------|----------|-------------------|
| **Manual** | Ручная оптимизация по запросу | Для точечных улучшений |
| **Automatic** | Автоматический цикл при ухудшении метрик | Для поддержания качества |
| **Target** | Стремление к целевой метрике | Для достижения KPI |

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
    print(f"Оптимизация завершена: {result.status}")
    print(f"Лучшая версия: {result.best_version}")
    print(f"Финальная точность: {result.final_metrics.accuracy}")
```

---

## 📅 План внедрения

### Этап 1: Фундамент (1-2 недели)

| Задача | Файлы | Приоритет | Статус |
|--------|-------|-----------|--------|
| Создать модели метрик | `core/models/data/metrics.py` | 🔴 | ⬜ |
| Создать модели бенчмарков | `core/models/data/benchmark.py` | 🔴 | ⬜ |
| Расширить EventBus | `core/infrastructure/event_bus/event_bus.py` | 🔴 | ⬜ |
| Создать MetricsStorage | `core/infrastructure/metrics_storage.py` | 🔴 | ⬜ |
| Создать LogStorage | `core/infrastructure/log_storage.py` | 🔴 | ⬜ |

### Этап 2: Сервисы (2-3 недели)

| Задача | Файлы | Приоритет | Статус |
|--------|-------|-----------|--------|
| MetricsCollector Service | `core/infrastructure/metrics_collector.py` | 🔴 | ⬜ |
| LogCollector Service | `core/infrastructure/log_collector.py` | 🔴 | ⬜ |
| BenchmarkService | `core/application/services/benchmark_service.py` | 🔴 | ⬜ |
| Интеграция с EventBus | Все сервисы | 🟠 | ⬜ |

### Этап 3: Оптимизация (2-3 недели)

| Задача | Файлы | Приоритет | Статус |
|--------|-------|-----------|--------|
| LearningOrchestrator | `core/application/services/learning_orchestrator.py` | 🟠 | ⬜ |
| OptimizationService | `core/application/services/optimization_service.py` | 🟠 | ⬜ |
| PromptContractGenerator | `core/application/services/prompt_contract_generator.py` | 🟠 | ⬜ |
| A/B тестирование версий | `core/application/data_repository.py` | 🟠 | ⬜ |

### Этап 4: Интеграция (1-2 недели)

| Задача | Файлы | Приоритет | Статус |
|--------|-------|-----------|--------|
| Расширить Manifest | `core/models/data/manifest.py` | 🟡 | ⬜ |
| Расширить BaseSkill | `core/application/skills/base_skill.py` | 🟡 | ⬜ |
| Скрипты запуска | `scripts/run_benchmark.py` | 🟡 | ⬜ |
| Документация | `docs/learning_system.md` | 🟡 | ⬜ |

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
    METRIC_COLLECTED = "metric.collected"  # ← Уже существует, используем

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
        Продвинуть версию в active статус.
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

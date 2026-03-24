# 📋 План доработки архитектуры оптимизации v2

## 🎯 Цель

Создать **полноценную систему оптимизации на основе анализа полного пути агента** (traces), а не только агрегированных метрик.

---

## 📊 Текущее состояние

### ✅ Реализовано (v2)
- [x] 8 компонентов модульной архитектуры
- [x] Модели данных (OptimizationSample, PromptVersion, EvaluationResult)
- [x] 47 unit-тестов
- [x] CLI для запуска
- [x] Documentation

### ❌ Проблемы текущей реализации
1. **DatasetBuilder** собирает только агрегированные метрики, а не полные traces
2. **Нет анализа промптов и ответов LLM**
3. **Нет анализа пути агента** (шаги, действия, контекст)
4. **PromptGenerator** использует простые мутации, а не целевые улучшения
5. **Нет связи с SessionHandler** для получения детальных логов

---

## 🏗️ План доработки (4 этапа)

### ЭТАП 1: Сбор полных execution traces
**Срок:** 2-3 дня  
**Сложность:** Средняя

#### 1.1. Модели для traces
```python
# core/models/data/execution_trace.py

@dataclass
class LLMRequest:
    prompt: str
    system_prompt: str
    temperature: float
    max_tokens: int
    timestamp: datetime

@dataclass
class LLMResponse:
    content: str
    tokens_used: int
    latency_ms: float
    model: str
    timestamp: datetime

@dataclass
class StepTrace:
    """След одного шага агента"""
    step_number: int
    capability: str
    goal: str
    
    # Промпт и ответ
    llm_request: LLMRequest
    llm_response: LLMResponse
    
    # Действие
    action: Optional[Action]
    action_result: Optional[ActionResult]
    
    # Ошибки
    errors: List[ErrorDetail]
    
    # Метрики
    time_ms: float
    tokens_used: int

@dataclass
class ExecutionTrace:
    """Полный след выполнения сессии"""
    session_id: str
    agent_id: str
    goal: str
    
    # Полный путь
    steps: List[StepTrace]
    
    # Итог
    success: bool
    total_time_ms: float
    total_tokens: int
    final_answer: Optional[str]
    error: Optional[str]
    
    # Метаданные
    started_at: datetime
    completed_at: datetime
```

#### 1.2. SessionHandler расширения
```python
# core/session_context/session_handler.py

class SessionHandler:
    async def get_execution_trace(self, session_id: str) -> ExecutionTrace:
        """Восстановление полного trace из логов"""
        pass
    
    async def get_traces_by_capability(
        self,
        capability: str,
        limit: int = 100,
        success_filter: Optional[bool] = None
    ) -> List[ExecutionTrace]:
        """Получение traces для capability"""
        pass
    
    async def get_failed_traces(
        self,
        capability: str,
        limit: int = 50
    ) -> List[ExecutionTrace]:
        """Получение только неудачных traces"""
        pass
```

#### 1.3. TraceCollector
```python
# core/application/components/optimization/trace_collector.py

class TraceCollector:
    """Сбор и реконструкция execution traces"""
    
    def __init__(self, session_handler: SessionHandler):
        self.session_handler = session_handler
    
    async def collect_traces(
        self,
        capability: str,
        min_samples: int = 50,
        include_success: bool = True,
        include_failure: bool = True
    ) -> List[ExecutionTrace]:
        """Сбор traces для оптимизации"""
        pass
    
    def _reconstruct_trace(self, logs: List[LogEntry]) -> ExecutionTrace:
        """Реконструкция trace из логов"""
        pass
```

---

### ЭТАП 2: Анализ паттернов и проблем
**Срок:** 3-4 дня  
**Сложность:** Высокая

#### 2.1. PatternAnalyzer
```python
# core/application/components/optimization/pattern_analyzer.py

class ExecutionPattern(Enum):
    REPEATED_RETRY = "repeated_retry"
    LONG_CHAIN = "long_chain"
    CONTEXT_LOSS = "context_loss"
    SCHEMA_VIOLATION = "schema_violation"
    SYNTAX_ERROR = "syntax_error"
    TIMEOUT = "timeout"
    SUCCESSFUL_SHORT = "successful_short"

@dataclass
class Pattern:
    type: ExecutionPattern
    description: str
    frequency: int
    affected_capabilities: List[str]
    recommendation: str
    example_traces: List[str]  # session_ids

class PatternAnalyzer:
    """Анализ паттернов выполнения"""
    
    def analyze(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        patterns = []
        patterns.extend(self._find_repeated_retries(traces))
        patterns.extend(self._find_long_chains(traces))
        patterns.extend(self._find_context_loss(traces))
        patterns.extend(self._find_schema_violations(traces))
        patterns.extend(self._find_syntax_errors(traces))
        return patterns
    
    def _find_repeated_retries(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """Поиск повторяющихся retry"""
        # Если один и тот же запрос повторяется多次
        pass
    
    def _find_long_chains(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """Поиск длинных цепочек шагов"""
        # Если >10 шагов для простой задачи
        pass
```

#### 2.2. PromptResponseAnalyzer
```python
# core/application/components/optimization/prompt_analyzer.py

@dataclass
class PromptIssue:
    type: str  # 'missing_examples', 'ambiguous', 'no_constraints'
    capability: str
    prompt: str
    description: str
    severity: str  # 'high', 'medium', 'low'
    suggestion: str

@dataclass
class ResponseIssue:
    type: str  # 'schema_violation', 'too_verbose', 'off_topic'
    capability: str
    response: str
    expected_schema: Dict
    description: str
    severity: str

class PromptResponseAnalyzer:
    """Анализ промптов и ответов LLM"""
    
    def analyze_prompts(
        self,
        traces: List[ExecutionTrace]
    ) -> List[PromptIssue]:
        issues = []
        issues.extend(self._find_missing_examples(traces))
        issues.extend(self._find_ambiguous_prompts(traces))
        issues.extend(self._find_missing_constraints(traces))
        return issues
    
    def analyze_responses(
        self,
        traces: List[ExecutionTrace]
    ) -> List[ResponseIssue]:
        issues = []
        issues.extend(self._find_schema_violations(traces))
        issues.extend(self._find_verbose_responses(traces))
        return issues
    
    def _find_missing_examples(self, traces: List[ExecutionTrace]) -> List[PromptIssue]:
        """Поиск промптов без примеров"""
        # Если частые ошибки → нужны примеры
        pass
```

#### 2.3. RootCauseAnalyzer
```python
# core/application/components/optimization/root_cause_analyzer.py

@dataclass
class RootCause:
    problem: str
    cause: str
    fix: str
    priority: str  # 'critical', 'high', 'medium', 'low'
    affected_capabilities: List[str]
    evidence: List[str]  # session_ids или trace ids

class RootCauseAnalyzer:
    """Поиск корневых причин проблем"""
    
    def analyze(
        self,
        patterns: List[Pattern],
        prompt_issues: List[PromptIssue],
        response_issues: List[ResponseIssue]
    ) -> List[RootCause]:
        """
        Сопоставление паттернов и проблем для поиска причин
        """
        root_causes = []
        
        # Пример: SQL syntax errors + missing examples → нужны примеры SQL
        if self._has_pattern(patterns, 'SYNTAX_ERROR'):
            if self._has_issue_type(prompt_issues, 'missing_examples'):
                root_causes.append(RootCause(
                    problem="SQL syntax errors",
                    cause="No SQL examples in prompt",
                    fix="Add SQL examples to prompt",
                    priority="high",
                    affected_capabilities=self._get_affected(prompt_issues),
                    evidence=self._get_evidence(patterns)
                ))
        
        return root_causes
```

---

### ЭТАП 3: Умная генерация улучшений
**Срок:** 3-4 дня  
**Сложность:** Высокая

#### 3.1. Умный PromptGenerator
```python
# core/application/components/optimization/prompt_generator.py (v2)

class ImprovementStrategy(Enum):
    ADD_EXAMPLES = "add_examples"
    ADD_CONSTRAINTS = "add_constraints"
    CLARIFY_INSTRUCTIONS = "clarify_instructions"
    ADD_ERROR_HANDLING = "add_error_handling"
    SIMPLIFY = "simplify"
    ADD_CONTEXT_PRESERVATION = "add_context_preservation"

@dataclass
class Improvement:
    strategy: ImprovementStrategy
    description: str
    root_cause: RootCause
    examples: Optional[List[str]] = None
    constraints: Optional[List[str]] = None

class PromptGenerator:
    """Умная генерация улучшений на основе анализа"""
    
    async def generate_improvements(
        self,
        original_prompt: Prompt,
        root_causes: List[RootCause],
        traces: List[ExecutionTrace]
    ) -> List[Prompt]:
        """
        Генерация улучшенных промптов на основе корневых причин
        """
        improvements = self._create_improvements(root_causes)
        candidates = []
        
        for improvement in improvements:
            candidate = await self._apply_improvement(
                original_prompt, improvement, traces
            )
            candidates.append(candidate)
        
        return candidates
    
    async def _apply_improvement(
        self,
        prompt: Prompt,
        improvement: Improvement,
        traces: List[ExecutionTrace]
    ) -> Prompt:
        """Применение конкретного улучшения"""
        
        if improvement.strategy == ImprovementStrategy.ADD_EXAMPLES:
            # Извлекаем успешные примеры из traces
            examples = self._extract_successful_examples(traces)
            return self._add_examples(prompt, examples)
        
        if improvement.strategy == ImprovementStrategy.ADD_CONSTRAINTS:
            # Извлекаем нарушения schema из traces
            violations = self._extract_violations(traces)
            return self._add_constraints(prompt, violations)
        
        # ... другие стратегии
```

#### 3.2. ExampleExtractor
```python
# core/application/components/optimization/example_extractor.py

class ExampleExtractor:
    """Извлечение примеров из успешных traces"""
    
    def extract_good_examples(
        self,
        traces: List[ExecutionTrace],
        capability: str,
        limit: int = 5
    ) -> List[Example]:
        """Извлечение хороших примеров"""
        # Фильтруем успешные traces
        successful = [t for t in traces if t.success and t.capability == capability]
        
        # Выбираем лучшие (короткие, без ошибок)
        best = sorted(successful, key=lambda t: (t.total_time_ms, len(t.steps)))[:limit]
        
        return [self._create_example(t) for t in best]
    
    def extract_error_examples(
        self,
        traces: List[ExecutionTrace],
        error_type: str
    ) -> List[ErrorExample]:
        """Извлечение примеров ошибок для добавления в промпт"""
        # Находим traces с конкретным типом ошибок
        pass
```

---

### ЭТАП 4: Интеграция и удаление старой версии
**Срок:** 2-3 дня  
**Сложность:** Средняя

#### 4.1. Обновление DatasetBuilder
```python
# core/application/components/optimization/dataset_builder.py (v2)

class DatasetBuilder:
    """Построение датасета из full traces"""
    
    async def build(self, capability: str) -> BenchmarkDataset:
        # Используем TraceCollector вместо MetricsCollector
        traces = await self.trace_collector.collect_traces(capability)
        
        # Конвертируем traces в OptimizationSample
        samples = []
        for trace in traces:
            sample = self._trace_to_sample(trace)
            samples.append(sample)
        
        return BenchmarkDataset(
            id=str(uuid.uuid4()),
            capability=capability,
            samples=samples
        )
    
    def _trace_to_sample(self, trace: ExecutionTrace) -> OptimizationSample:
        """Конвертация trace в sample"""
        return OptimizationSample(
            id=trace.session_id,
            input=trace.goal,
            context={
                'steps': len(trace.steps),
                'total_time_ms': trace.total_time_ms,
                'capabilities_used': [s.capability for s in trace.steps]
            },
            expected_behavior=None,  # Можно извлечь из контрактов
            actual_output=trace.final_answer,
            success=trace.success,
            error=trace.error,
            metadata={
                'trace': trace.to_dict(),  # Полный trace
                'started_at': trace.started_at.isoformat()
            }
        )
```

#### 4.2. Обновление OptimizationOrchestrator
```python
# core/application/components/optimization/orchestrator.py (v2)

class OptimizationOrchestrator:
    """Оркестрация с полным анализом traces"""
    
    async def optimize(
        self,
        capability: str,
        mode: OptimizationMode = OptimizationMode.ACCURACY
    ) -> OptimizationResult:
        # 1. Сбор traces
        traces = await self.trace_collector.collect_traces(capability)
        
        # 2. Анализ паттернов
        patterns = self.pattern_analyzer.analyze(traces)
        
        # 3. Анализ промптов/ответов
        prompt_issues = self.prompt_analyzer.analyze_prompts(traces)
        response_issues = self.prompt_analyzer.analyze_responses(traces)
        
        # 4. Поиск корневых причин
        root_causes = self.root_cause_analyzer.analyze(
            patterns, prompt_issues, response_issues
        )
        
        # 5. Генерация улучшений
        baseline = await self.version_manager.get_active(capability)
        candidates = await self.prompt_generator.generate_improvements(
            baseline, root_causes, traces
        )
        
        # 6. Тестирование и оценка (как раньше)
        # ...
```

#### 4.3. Удаление старой архитектуры

**Файлы для удаления:**

```
# Старый OptimizationService
core/application/services/optimization_service.py  ❌ УДАЛИТЬ
core/application/services/prompt_contract_generator.py  ❌ УДАЛИТЬ (заменить на v2)
core/application/services/benchmark_service.py  ❌ УДАЛИТЬ (заменить на BenchmarkRunner + Evaluator)

# Старые тесты
tests/e2e/test_optimization_cycle.py  ❌ УДАЛИТЬ
tests/unit/services/test_optimization_service.py  ❌ УДАЛИТЬ

# CLI скрипт старой версии
scripts/cli/run_optimization.py  ❌ УДАЛИТЬ (заменить на run_optimization_v2.py)
```

**Файлы для переименования:**

```
scripts/cli/run_optimization_v2.py  →  scripts/cli/run_optimization.py
```

**Обновление импортов:**

```python
# Было:
from core.application.services.optimization_service import OptimizationService

# Стало:
from core.application.components.optimization import OptimizationOrchestrator
```

---

## 📅 Итоговый план

| Этап | Задачи | Срок | Статус |
|------|--------|------|--------|
| **ЭТАП 1** | Модели traces, SessionHandler расширения, TraceCollector | 2-3 дня | ⏳ Pending |
| **ЭТАП 2** | PatternAnalyzer, PromptAnalyzer, RootCauseAnalyzer | 3-4 дня | ⏳ Pending |
| **ЭТАП 3** | Умный PromptGenerator, ExampleExtractor | 3-4 дня | ⏳ Pending |
| **ЭТАП 4** | Интеграция, удаление старой версии | 2-3 дня | ⏳ Pending |

**Общий срок:** 10-14 рабочих дней

---

## ✅ Критерии готовности

### Функциональные
- [ ] Сбор полных execution traces
- [ ] Анализ паттернов выполнения (≥5 паттернов)
- [ ] Анализ промптов и ответов
- [ ] Поиск корневых причин
- [ ] Умная генерация улучшений (≥4 стратегий)
- [ ] Интеграция с SessionHandler

### Технические
- [ ] Unit-тесты ≥80% покрытие
- [ ] Integration-тесты для полного цикла
- [ ] Документация обновлена
- [ ] Старая версия удалена
- [ ] Миграция завершена

### Метрики качества
- [ ] Оптимизация на основе traces, а не только метрик
- [ ] ≥3 типа улучшений генерируется автоматически
- [ ] ≥50% улучшений принимаются SafetyLayer
- [ ] Regression rate = 0

---

## 🚀 Следующие шаги

1. **Создать task list** для каждого этапа
2. **Начать с ЭТАПА 1** (модели traces)
3. **Постепенная миграция** — новая версия параллельно со старой
4. **Тестирование на реальных данных** перед удалением старой версии

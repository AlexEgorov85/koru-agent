"""
PatternAnalyzer — анализ паттернов выполнения.

КОМПОНЕНТЫ:
- PatternAnalyzer: выявление паттернов в execution traces

FEATURES:
- 5+ паттернов выполнения
- Поиск проблемных мест
- Рекомендации по улучшению
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from core.models.data.execution_trace import ExecutionTrace, StepTrace, ErrorType


class ExecutionPattern(Enum):
    """
    Типы паттернов выполнения.

    PATTERNS:
    - REPEATED_RETRY: повторяющиеся retry
    - LONG_CHAIN: длинная цепочка шагов
    - CONTEXT_LOSS: потеря контекста
    - SCHEMA_VIOLATION: нарушение схемы
    - SYNTAX_ERROR: синтаксические ошибки
    - TIMEOUT: таймауты
    - SUCCESSFUL_SHORT: успешное короткое выполнение
    - CIRCULAR_DEPENDENCY: циклические зависимости
    """
    REPEATED_RETRY = "repeated_retry"
    LONG_CHAIN = "long_chain"
    CONTEXT_LOSS = "context_loss"
    SCHEMA_VIOLATION = "schema_violation"
    SYNTAX_ERROR = "syntax_error"
    TIMEOUT = "timeout"
    SUCCESSFUL_SHORT = "successful_short"
    CIRCULAR_DEPENDENCY = "circular_dependency"


@dataclass
class Pattern:
    """
    Паттерн выполнения.

    ATTRIBUTES:
    - type: тип паттерна
    - description: описание
    - frequency: частота встречаемости
    - affected_capabilities: затронутые способности
    - recommendation: рекомендация по улучшению
    - example_traces: примеры session_ids
    - severity: серьёзность (critical/high/medium/low)
    """
    type: ExecutionPattern
    description: str
    frequency: int = 1
    affected_capabilities: List[str] = field(default_factory=list)
    recommendation: str = ""
    example_traces: List[str] = field(default_factory=list)
    severity: str = "medium"  # critical, high, medium, low

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'type': self.type.value,
            'description': self.description,
            'frequency': self.frequency,
            'affected_capabilities': self.affected_capabilities,
            'recommendation': self.recommendation,
            'example_traces': self.example_traces,
            'severity': self.severity
        }


class PatternAnalyzer:
    """
    Анализатор паттернов выполнения.

    RESPONSIBILITIES:
    - Выявление паттернов в traces
    - Поиск проблемных мест
    - Генерация рекомендаций

    USAGE:
    ```python
    analyzer = PatternAnalyzer()
    patterns = analyzer.analyze(traces)
    ```
    """

    def __init__(self):
        """Инициализация анализатора"""
        # Пороги для обнаружения паттернов
        self.thresholds = {
            'long_chain_steps': 10,  # >10 шагов = длинная цепочка
            'repeated_retry_count': 2,  # ≥2 повторов = паттерн
            'context_loss_window': 5,  # потеря контекста в пределах 5 шагов
            'timeout_ms': 30000,  # 30 секунд = таймаут
            'short_successful_steps': 3,  # ≤3 шагов = короткое успешное
        }

    def analyze(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Анализ traces на паттерны.

        ARGS:
        - traces: список execution traces

        RETURNS:
        - List[Pattern]: список обнаруженных паттернов
        """
        patterns = []

        patterns.extend(self._find_repeated_retries(traces))
        patterns.extend(self._find_long_chains(traces))
        patterns.extend(self._find_context_loss(traces))
        patterns.extend(self._find_schema_violations(traces))
        patterns.extend(self._find_syntax_errors(traces))
        patterns.extend(self._find_timeouts(traces))
        patterns.extend(self._find_successful_short(traces))
        patterns.extend(self._find_circular_dependencies(traces))

        return patterns

    def _find_repeated_retries(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск повторяющихся retry.

        Паттерн: один и тот же запрос повторяется多次
        """
        patterns = []

        # Группировка по goal + capability
        goal_capability_counts: Dict[str, Dict[str, int]] = {}

        for trace in traces:
            for step in trace.steps:
                key = f"{step.capability}:{step.goal}"
                if step.capability not in goal_capability_counts:
                    goal_capability_counts[step.capability] = {}
                goal_capability_counts[step.capability][step.goal] = \
                    goal_capability_counts[step.capability].get(step.goal, 0) + 1

        # Поиск повторов
        for capability, goals in goal_capability_counts.items():
            for goal, count in goals.items():
                if count >= self.thresholds['repeated_retry_count']:
                    # Найти примеры
                    example_sessions = []
                    for trace in traces:
                        for step in trace.steps:
                            if step.capability == capability and step.goal == goal:
                                example_sessions.append(trace.session_id)
                                if len(example_sessions) >= 3:
                                    break

                    patterns.append(Pattern(
                        type=ExecutionPattern.REPEATED_RETRY,
                        description=f"Повторяющийся запрос к {capability}: {goal[:50]}...",
                        frequency=count,
                        affected_capabilities=[capability],
                        recommendation="Добавить обработку ошибок в промпт или улучшить валидацию входных данных",
                        example_traces=example_sessions,
                        severity="high" if count >= 5 else "medium"
                    ))

        return patterns

    def _find_long_chains(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск длинных цепочек шагов.

        Паттерн: >10 шагов для задачи
        """
        patterns = []

        long_traces = [t for t in traces if t.step_count > self.thresholds['long_chain_steps']]

        if long_traces:
            # Группировка по capability
            capabilities: Set[str] = set()
            for trace in long_traces:
                capabilities.update(trace.get_capabilities_used())

            avg_steps = sum(t.step_count for t in long_traces) / len(long_traces)

            patterns.append(Pattern(
                type=ExecutionPattern.LONG_CHAIN,
                description=f"Длинные цепочки выполнения (среднее: {avg_steps:.1f} шагов)",
                frequency=len(long_traces),
                affected_capabilities=list(capabilities),
                recommendation="Упростить планирование или разбить задачу на подзадачи",
                example_traces=[t.session_id for t in long_traces[:3]],
                severity="high" if avg_steps > 15 else "medium"
            ))

        return patterns

    def _find_context_loss(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск потери контекста.

        Паттерн: агент задаёт вопросы которые уже отвечены
        """
        patterns = []

        # Поиск traces где есть ошибки context_loss
        context_loss_traces = []
        for trace in traces:
            for step in trace.steps:
                for error in step.errors:
                    if error.error_type == ErrorType.CONTEXT_LOSS:
                        context_loss_traces.append(trace)
                        break

        if context_loss_traces:
            capabilities: Set[str] = set()
            for trace in context_loss_traces:
                capabilities.update(trace.get_capabilities_used())

            patterns.append(Pattern(
                type=ExecutionPattern.CONTEXT_LOSS,
                description="Агент теряет контекст и задаёт повторные вопросы",
                frequency=len(context_loss_traces),
                affected_capabilities=list(capabilities),
                recommendation="Усилить инструкции по сохранению контекста в промпте",
                example_traces=[t.session_id for t in context_loss_traces[:3]],
                severity="high"
            ))

        return patterns

    def _find_schema_violations(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск нарушений схемы.

        Паттерн: ответы LLM не соответствуют контракту
        """
        patterns = []

        # Поиск traces где есть ошибки schema_violation
        violation_traces = []
        for trace in traces:
            for step in trace.steps:
                for error in step.errors:
                    if error.error_type == ErrorType.SCHEMA_VIOLATION:
                        violation_traces.append(trace)
                        break

        if violation_traces:
            capabilities: Set[str] = set()
            for trace in violation_traces:
                capabilities.update(trace.get_capabilities_used())

            patterns.append(Pattern(
                type=ExecutionPattern.SCHEMA_VIOLATION,
                description="Ответы LLM не соответствуют JSON схеме контракта",
                frequency=len(violation_traces),
                affected_capabilities=list(capabilities),
                recommendation="Добавить примеры правильного формата в промпт",
                example_traces=[t.session_id for t in violation_traces[:3]],
                severity="high"
            ))

        return patterns

    def _find_syntax_errors(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск синтаксических ошибок.

        Паттерн: частые SQL/syntax ошибки
        """
        patterns = []

        # Поиск traces где есть ошибки syntax_error
        syntax_error_traces = []
        for trace in traces:
            error_types = trace.get_errors_by_type()
            if 'syntax_error' in error_types:
                syntax_error_traces.append(trace)

        if syntax_error_traces:
            capabilities: Set[str] = set()
            for trace in syntax_error_traces:
                capabilities.update(trace.get_capabilities_used())

            patterns.append(Pattern(
                type=ExecutionPattern.SYNTAX_ERROR,
                description="Частые синтаксические ошибки (SQL, JSON, etc)",
                frequency=len(syntax_error_traces),
                affected_capabilities=list(capabilities),
                recommendation="Добавить примеры синтаксиса в промпт",
                example_traces=[t.session_id for t in syntax_error_traces[:3]],
                severity="high"
            ))

        return patterns

    def _find_timeouts(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск таймаутов.

        Паттерн: выполнения превышают лимит времени
        """
        patterns = []

        timeout_traces = [t for t in traces if t.total_time_ms > self.thresholds['timeout_ms']]

        if timeout_traces:
            capabilities: Set[str] = set()
            for trace in timeout_traces:
                capabilities.update(trace.get_capabilities_used())

            avg_time = sum(t.total_time_ms for t in timeout_traces) / len(timeout_traces)

            patterns.append(Pattern(
                type=ExecutionPattern.TIMEOUT,
                description=f"Таймауты выполнения (среднее: {avg_time/1000:.1f}с)",
                frequency=len(timeout_traces),
                affected_capabilities=list(capabilities),
                recommendation="Добавить обработку таймаутов или оптимизировать запросы",
                example_traces=[t.session_id for t in timeout_traces[:3]],
                severity="medium"
            ))

        return patterns

    def _find_successful_short(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск успешных коротких выполнений.

        Паттерн: ≤3 шагов, без ошибок — это хороший пример!
        """
        patterns = []

        short_successful = [
            t for t in traces
            if t.success and t.step_count <= self.thresholds['short_successful_steps']
        ]

        if short_successful:
            capabilities: Set[str] = set()
            for trace in short_successful:
                capabilities.update(trace.get_capabilities_used())

            patterns.append(Pattern(
                type=ExecutionPattern.SUCCESSFUL_SHORT,
                description="Успешные короткие выполнения (хорошие примеры)",
                frequency=len(short_successful),
                affected_capabilities=list(capabilities),
                recommendation="Использовать как few-shot примеры в промпте",
                example_traces=[t.session_id for t in short_successful[:5]],
                severity="low"  # Это хороший паттерн
            ))

        return patterns

    def _find_circular_dependencies(self, traces: List[ExecutionTrace]) -> List[Pattern]:
        """
        Поиск циклических зависимостей.

        Паттерн: одна и та же capability вызывается 3+ раз ПОДРЯД без прогресса
        """
        patterns = []

        circular_traces = []
        repeated_capabilities: Dict[str, int] = {}

        for trace in traces:
            capabilities = [s.capability for s in trace.steps]
            
            # Проверка на 3+ одинаковых capability подряд
            consecutive_count = 1
            max_consecutive = 1
            current_cap = None
            
            for cap in capabilities:
                if cap == current_cap:
                    consecutive_count += 1
                    max_consecutive = max(max_consecutive, consecutive_count)
                else:
                    consecutive_count = 1
                    current_cap = cap
            
            # Флагим только если 3+ одинаковых capability подряд
            if max_consecutive >= 3:
                circular_traces.append(trace)
                
                # Подсчитываем какие capability повторяются
                for cap in set(capabilities):
                    if capabilities.count(cap) >= 3:
                        repeated_capabilities[cap] = repeated_capabilities.get(cap, 0) + 1

        if circular_traces:
            # Сортируем по частоте повторений
            top_repeated = sorted(repeated_capabilities.items(), key=lambda x: x[1], reverse=True)[:3]
            
            patterns.append(Pattern(
                type=ExecutionPattern.CIRCULAR_DEPENDENCY,
                description=f"Многократные вызовы без прогресса: {', '.join([c[0] for c in top_repeated])}",
                frequency=len(circular_traces),
                affected_capabilities=list(repeated_capabilities.keys()),
                recommendation="Добавить кэширование результатов или лимит повторов (max 2)",
                example_traces=[t.session_id for t in circular_traces[:3]],
                severity="medium"  # Снижаем severity — это может быть легитимный retry
            ))

        return patterns

    def get_pattern_stats(self, patterns: List[Pattern]) -> Dict[str, Any]:
        """
        Получение статистики паттернов.

        ARGS:
        - patterns: список паттернов

        RETURNS:
        - Dict[str, Any]: статистика
        """
        if not patterns:
            return {'total_patterns': 0}

        # Группировка по типам
        by_type = {}
        for pattern in patterns:
            type_name = pattern.type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(pattern)

        # Группировка по серьёзности
        by_severity = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        for pattern in patterns:
            by_severity[pattern.severity] = by_severity.get(pattern.severity, 0) + 1

        return {
            'total_patterns': len(patterns),
            'by_type': {k: len(v) for k, v in by_type.items()},
            'by_severity': by_severity,
            'most_common': patterns[0].type.value if patterns else None,
            'critical_count': by_severity['critical'] + by_severity['high']
        }

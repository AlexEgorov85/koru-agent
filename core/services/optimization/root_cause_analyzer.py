"""
RootCauseAnalyzer — поиск корневых причин проблем.

КОМПОНЕНТЫ:
- RootCauseAnalyzer: сопоставление паттернов и проблем

FEATURES:
- Поиск корневых причин
- Приоритизация проблем
- Рекомендации по исправлению
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from .pattern_analyzer import Pattern, ExecutionPattern
from .prompt_analyzer import PromptIssue, ResponseIssue


class Priority(Enum):
    """Приоритет исправления"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class RootCause:
    """
    Корневая причина проблемы.

    ATTRIBUTES:
    - problem: описание проблемы
    - cause: корневая причина
    - fix: рекомендация по исправлению
    - priority: приоритет
    - affected_capabilities: затронутые способности
    - evidence: доказательства (session_ids)
    - related_patterns: связанные паттерны
    - related_issues: связанные проблемы
    """
    problem: str
    cause: str
    fix: str
    priority: Priority = Priority.MEDIUM
    affected_capabilities: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    related_patterns: List[str] = field(default_factory=list)
    related_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'problem': self.problem,
            'cause': self.cause,
            'fix': self.fix,
            'priority': self.priority.value,
            'affected_capabilities': self.affected_capabilities,
            'evidence': self.evidence,
            'related_patterns': self.related_patterns,
            'related_issues': self.related_issues
        }


class RootCauseAnalyzer:
    """
    Анализатор корневых причин.

    RESPONSIBILITIES:
    - Сопоставление паттернов и проблем
    - Поиск корневых причин
    - Приоритизация исправлений

    USAGE:
    ```python
    analyzer = RootCauseAnalyzer()
    root_causes = analyzer.analyze(patterns, prompt_issues, response_issues)
    ```
    """

    def __init__(self):
        """Инициализация анализатора"""
        # Матрица соответствий: Pattern + Issue → RootCause
        self.cause_matrix = {
            (ExecutionPattern.SYNTAX_ERROR, 'missing_examples'): {
                'cause': "Отсутствие примеров синтаксиса в промпте",
                'fix': "Добавить few-shot примеры правильного синтаксиса",
                'priority': Priority.HIGH
            },
            (ExecutionPattern.SYNTAX_ERROR, 'no_constraints'): {
                'cause': "Отсутствие ограничений на формат ввода",
                'fix': "Добавить явные правила валидации",
                'priority': Priority.HIGH
            },
            (ExecutionPattern.SCHEMA_VIOLATION, 'missing_examples'): {
                'cause': "Отсутствие примеров правильного JSON формата",
                'fix': "Добавить примеры output формата в промпт",
                'priority': Priority.HIGH
            },
            (ExecutionPattern.SCHEMA_VIOLATION, 'no_constraints'): {
                'cause': "Отсутствие constraints на output схему",
                'fix': "Добавить JSON Schema или строгие правила",
                'priority': Priority.HIGH
            },
            (ExecutionPattern.REPEATED_RETRY, 'no_error_handling'): {
                'cause': "Отсутствие обработки ошибок в промпте",
                'fix': "Добавить инструкции по graceful error handling",
                'priority': Priority.HIGH
            },
            (ExecutionPattern.LONG_CHAIN, 'ambiguous'): {
                'cause': "Неясные инструкции приводят к лишним шагам",
                'fix': "Уточнить инструкции и добавить примеры коротких путей",
                'priority': Priority.MEDIUM
            },
            (ExecutionPattern.CONTEXT_LOSS, 'missing_examples'): {
                'cause': "Отсутствие примеров сохранения контекста",
                'fix': "Добавить примеры с явным указанием контекста",
                'priority': Priority.HIGH
            },
            (ExecutionPattern.TIMEOUT, 'no_constraints'): {
                'cause': "Отсутствие ограничений на время/размер",
                'fix': "Добавить ограничения на время выполнения",
                'priority': Priority.MEDIUM
            },
        }

    def analyze(
        self,
        patterns: List[Pattern],
        prompt_issues: List[PromptIssue],
        response_issues: List[ResponseIssue]
    ) -> List[RootCause]:
        """
        Анализ и поиск корневых причин.

        ARGS:
        - patterns: обнаруженные паттерны
        - prompt_issues: проблемы промптов
        - response_issues: проблемы ответов

        RETURNS:
        - List[RootCause]: список корневых причин
        """
        root_causes = []

        # Сопоставление паттернов с проблемами промптов
        root_causes.extend(self._match_patterns_with_prompt_issues(patterns, prompt_issues))

        # Сопоставление паттернов с проблемами ответов
        root_causes.extend(self._match_patterns_with_response_issues(patterns, response_issues))

        # Добавление причин для standalone проблем
        root_causes.extend(self._find_standalone_causes(prompt_issues, response_issues))

        # Приоритизация
        root_causes.sort(key=lambda rc: self._priority_order(rc.priority))

        return root_causes

    def _match_patterns_with_prompt_issues(
        self,
        patterns: List[Pattern],
        prompt_issues: List[PromptIssue]
    ) -> List[RootCause]:
        """Сопоставление паттернов с проблемами промптов"""
        root_causes = []

        for pattern in patterns:
            for issue in prompt_issues:
                # Проверка пересечения capabilities
                common_capabilities = set(pattern.affected_capabilities) & {issue.capability}
                if not common_capabilities:
                    continue

                # Поиск в матрице
                key = (pattern.type, issue.issue_type)
                if key in self.cause_matrix:
                    cause_info = self.cause_matrix[key]

                    root_causes.append(RootCause(
                        problem=pattern.description,
                        cause=cause_info['cause'],
                        fix=cause_info['fix'],
                        priority=cause_info['priority'],
                        affected_capabilities=list(common_capabilities),
                        evidence=pattern.example_traces + issue.examples,
                        related_patterns=[pattern.type.value],
                        related_issues=[issue.issue_type]
                    ))

        return root_causes

    def _match_patterns_with_response_issues(
        self,
        patterns: List[Pattern],
        response_issues: List[ResponseIssue]
    ) -> List[RootCause]:
        """Сопоставление паттернов с проблемами ответов"""
        root_causes = []

        for pattern in patterns:
            if pattern.type == ExecutionPattern.SCHEMA_VIOLATION:
                # Поиск response issues с schema_violation
                schema_issues = [i for i in response_issues if i.issue_type == 'schema_violation']
                
                if schema_issues:
                    common_capabilities = set(pattern.affected_capabilities) & {i.capability for i in schema_issues}
                    
                    if common_capabilities:
                        root_causes.append(RootCause(
                            problem=pattern.description,
                            cause="Ответы LLM не соответствуют контракту",
                            fix="Добавить примеры правильного формата и constraints",
                            priority=Priority.HIGH,
                            affected_capabilities=list(common_capabilities),
                            evidence=pattern.example_traces,
                            related_patterns=[pattern.type.value],
                            related_issues=['schema_violation']
                        ))

        return root_causes

    def _find_standalone_causes(
        self,
        prompt_issues: List[PromptIssue],
        response_issues: List[ResponseIssue]
    ) -> List[RootCause]:
        """Поиск причин для standalone проблем"""
        root_causes = []

        # Проблемы промптов без связанных паттернов
        standalone_prompt_causes = {
            'missing_examples': ("Отсутствие примеров", "Добавить few-shot примеры", Priority.MEDIUM),
            'ambiguous': ("Неоднозначные формулировки", "Заменить на конкретные инструкции", Priority.MEDIUM),
            'no_constraints': ("Отсутствие ограничений", "Добавить явные правила", Priority.MEDIUM),
            'no_error_handling': ("Отсутствие обработки ошибок", "Добавить error handling инструкции", Priority.MEDIUM),
        }

        for issue in prompt_issues:
            if issue.issue_type in standalone_prompt_causes:
                cause_info = standalone_prompt_causes[issue.issue_type]
                root_causes.append(RootCause(
                    problem=issue.description,
                    cause=cause_info[0],
                    fix=cause_info[1],
                    priority=cause_info[2],
                    affected_capabilities=[issue.capability],
                    evidence=issue.examples,
                    related_issues=[issue.issue_type]
                ))

        # Проблемы ответов
        standalone_response_causes = {
            'too_verbose': ("Слишком подробные ответы", "Ограничить длину в промпте", Priority.LOW),
            'incomplete': ("Неполные ответы", "Добавить требования к полноте", Priority.MEDIUM),
        }

        for issue in response_issues:
            if issue.issue_type in standalone_response_causes:
                cause_info = standalone_response_causes[issue.issue_type]
                root_causes.append(RootCause(
                    problem=issue.description,
                    cause=cause_info[0],
                    fix=cause_info[1],
                    priority=cause_info[2],
                    affected_capabilities=[issue.capability],
                    related_issues=[issue.issue_type]
                ))

        return root_causes

    def _priority_order(self, priority: Priority) -> int:
        """Порядок сортировки приоритетов"""
        order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3
        }
        return order.get(priority, 4)

    def get_root_cause_stats(self, root_causes: List[RootCause]) -> Dict[str, Any]:
        """
        Получение статистики корневых причин.

        ARGS:
        - root_causes: список причин

        RETURNS:
        - Dict[str, Any]: статистика
        """
        if not root_causes:
            return {'total_root_causes': 0}

        # По приоритетам
        by_priority = {}
        for rc in root_causes:
            p = rc.priority.value
            by_priority[p] = by_priority.get(p, 0) + 1

        # По причинам
        by_cause = {}
        for rc in root_causes:
            by_cause[rc.cause] = by_cause.get(rc.cause, 0) + 1

        # По affected capabilities
        all_capabilities: Set[str] = set()
        for rc in root_causes:
            all_capabilities.update(rc.affected_capabilities)

        return {
            'total_root_causes': len(root_causes),
            'by_priority': by_priority,
            'top_causes': sorted(by_cause.items(), key=lambda x: x[1], reverse=True)[:5],
            'affected_capabilities_count': len(all_capabilities),
            'critical_high_count': by_priority.get('critical', 0) + by_priority.get('high', 0)
        }

    def get_fix_recommendations(
        self,
        root_causes: List[RootCause],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Получение рекомендаций по исправлению.

        ARGS:
        - root_causes: список причин
        - limit: максимум рекомендаций

        RETURNS:
        - List[Dict]: рекомендации
        """
        recommendations = []

        for rc in root_causes[:limit]:
            recommendations.append({
                'priority': rc.priority.value,
                'capability': rc.affected_capabilities[0] if rc.affected_capabilities else 'unknown',
                'problem': rc.problem,
                'fix': rc.fix,
                'evidence_count': len(rc.evidence)
            })

        return recommendations

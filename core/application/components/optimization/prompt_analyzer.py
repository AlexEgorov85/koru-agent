"""
PromptResponseAnalyzer — анализ промптов и ответов LLM.

КОМПОНЕНТЫ:
- PromptResponseAnalyzer: анализ качества промптов и ответов

FEATURES:
- Поиск проблем в промптах (missing examples, ambiguous, no constraints)
- Поиск проблем в ответах (schema violations, verbose, off-topic)
- Рекомендации по улучшению
"""
import json
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from core.models.data.execution_trace import ExecutionTrace, StepTrace, LLMRequest, LLMResponse


@dataclass
class PromptIssue:
    """
    Проблема в промпте.

    ATTRIBUTES:
    - issue_type: тип проблемы
    - capability: название способности
    - prompt: текст промпта
    - description: описание проблемы
    - severity: серьёзность
    - suggestion: предложение по улучшению
    - examples: примеры из traces
    """
    issue_type: str  # missing_examples, ambiguous, no_constraints, no_error_handling
    capability: str
    prompt: str
    description: str
    severity: str = "medium"  # critical, high, medium, low
    suggestion: str = ""
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'issue_type': self.issue_type,
            'capability': self.capability,
            'prompt': self.prompt[:200] + '...' if len(self.prompt) > 200 else self.prompt,
            'description': self.description,
            'severity': self.severity,
            'suggestion': self.suggestion,
            'examples': self.examples
        }


@dataclass
class ResponseIssue:
    """
    Проблема в ответе LLM.

    ATTRIBUTES:
    - issue_type: тип проблемы
    - capability: название способности
    - response: текст ответа
    - expected_schema: ожидаемая схема
    - description: описание проблемы
    - severity: серьёзность
    """
    issue_type: str  # schema_violation, too_verbose, off_topic, incomplete
    capability: str
    response: str
    expected_schema: Optional[Dict[str, Any]] = None
    description: str = ""
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'issue_type': self.issue_type,
            'capability': self.capability,
            'response': self.response[:200] + '...' if len(self.response) > 200 else self.response,
            'expected_schema': self.expected_schema,
            'description': self.description,
            'severity': self.severity
        }


class PromptResponseAnalyzer:
    """
    Анализатор промптов и ответов LLM.

    RESPONSIBILITIES:
    - Анализ промптов на проблемы
    - Анализ ответов на проблемы
    - Генерация рекомендаций

    USAGE:
    ```python
    analyzer = PromptResponseAnalyzer()
    prompt_issues = analyzer.analyze_prompts(traces)
    response_issues = analyzer.analyze_responses(traces)
    ```
    """

    def __init__(self):
        """Инициализация анализатора"""
        # Пороги
        self.thresholds = {
            'max_response_tokens': 500,  # >500 токенов = слишком подробно
            'min_examples_in_prompt': 1,  # <1 примера = missing examples
            'ambiguity_keywords': ['может быть', 'возможно', 'примерно', 'etc', 'и т.д.'],
        }

    def analyze_prompts(
        self,
        traces: List[ExecutionTrace]
    ) -> List[PromptIssue]:
        """
        Анализ промптов на проблемы.

        ARGS:
        - traces: список execution traces

        RETURNS:
        - List[PromptIssue]: список проблем
        """
        issues = []

        issues.extend(self._find_missing_examples(traces))
        issues.extend(self._find_ambiguous_prompts(traces))
        issues.extend(self._find_missing_constraints(traces))
        issues.extend(self._find_missing_error_handling(traces))

        return issues

    def analyze_responses(
        self,
        traces: List[ExecutionTrace]
    ) -> List[ResponseIssue]:
        """
        Анализ ответов на проблемы.

        ARGS:
        - traces: список execution traces

        RETURNS:
        - List[ResponseIssue]: список проблем
        """
        issues = []

        issues.extend(self._find_schema_violations(traces))
        issues.extend(self._find_verbose_responses(traces))
        issues.extend(self._find_incomplete_responses(traces))

        return issues

    def _find_missing_examples(self, traces: List[ExecutionTrace]) -> List[PromptIssue]:
        """
        Поиск промптов без примеров.

        Логика: если частые ошибки → нужны примеры
        """
        issues = []
        capabilities_with_errors: Dict[str, List[ExecutionTrace]] = {}

        # Группировка traces с ошибками по capability
        for trace in traces:
            if not trace.success:
                for capability in trace.get_capabilities_used():
                    if capability not in capabilities_with_errors:
                        capabilities_with_errors[capability] = []
                    capabilities_with_errors[capability].append(trace)

        # Проверка промптов для capability с ошибками
        for capability, error_traces in capabilities_with_errors.items():
            if len(error_traces) < 2:
                continue  # Недостаточно данных

            # Проверка есть ли примеры в промптах
            has_examples = False
            sample_prompt = ""

            for trace in error_traces:
                for step in trace.steps:
                    if step.capability == capability and step.llm_request:
                        sample_prompt = step.llm_request.prompt
                        # Поиск примеров в промпте
                        if self._prompt_has_examples(step.llm_request.prompt):
                            has_examples = True
                            break
                if has_examples:
                    break

            if not has_examples and sample_prompt:
                issues.append(PromptIssue(
                    issue_type='missing_examples',
                    capability=capability,
                    prompt=sample_prompt,
                    description=f"Промпт не содержит примеров, но есть {len(error_traces)} неудачных выполнений",
                    severity="high",
                    suggestion="Добавить few-shot примеры правильного выполнения",
                    examples=[t.session_id for t in error_traces[:3]]
                ))

        return issues

    def _find_ambiguous_prompts(self, traces: List[ExecutionTrace]) -> List[PromptIssue]:
        """
        Поиск неоднозначных промптов.

        Логика: поиск ambiguity keywords
        """
        issues = []
        ambiguous_prompts: Dict[str, List[str]] = {}  # capability -> prompts

        for trace in traces:
            for step in trace.steps:
                if step.llm_request:
                    prompt = step.llm_request.prompt
                    # Поиск неоднозначных слов
                    for keyword in self.thresholds['ambiguity_keywords']:
                        if keyword.lower() in prompt.lower():
                            if step.capability not in ambiguous_prompts:
                                ambiguous_prompts[step.capability] = []
                            if prompt not in ambiguous_prompts[step.capability]:
                                ambiguous_prompts[step.capability].append(prompt)

        # Создание issues
        for capability, prompts in ambiguous_prompts.items():
            if prompts:
                issues.append(PromptIssue(
                    issue_type='ambiguous',
                    capability=capability,
                    prompt=prompts[0],
                    description=f"Найдены неоднозначные формулировки в промпте",
                    severity="medium",
                    suggestion="Заменить неоднозначные слова на конкретные инструкции",
                    examples=[trace.session_id for trace in traces if any(s.capability == capability for s in trace.steps)][:3]
                ))

        return issues

    def _find_missing_constraints(self, traces: List[ExecutionTrace]) -> List[PromptIssue]:
        """
        Поиск промптов без ограничений.

        Логика: если есть schema violations → нужны constraints
        """
        issues = []
        capabilities_with_violations: Dict[str, List[ExecutionTrace]] = {}

        # Поиск traces с schema violations
        for trace in traces:
            for step in trace.steps:
                for error in step.errors:
                    if error.error_type.value == 'schema_violation':
                        if step.capability not in capabilities_with_violations:
                            capabilities_with_violations[step.capability] = []
                        capabilities_with_violations[step.capability].append(trace)

        # Проверка промптов
        for capability, violation_traces in capabilities_with_violations.items():
            sample_prompt = ""
            has_constraints = False

            for trace in violation_traces:
                for step in trace.steps:
                    if step.capability == capability and step.llm_request:
                        sample_prompt = step.llm_request.prompt
                        # Поиск ограничений в промпте
                        if self._prompt_has_constraints(step.llm_request.prompt):
                            has_constraints = True
                            break
                if has_constraints:
                    break

            if not has_constraints and sample_prompt:
                issues.append(PromptIssue(
                    issue_type='no_constraints',
                    capability=capability,
                    prompt=sample_prompt,
                    description=f"Промпт не содержит ограничений, но есть {len(violation_traces)} нарушений схемы",
                    severity="high",
                    suggestion="Добавить явные ограничения и правила валидации",
                    examples=[t.session_id for t in violation_traces[:3]]
                ))

        return issues

    def _find_missing_error_handling(self, traces: List[ExecutionTrace]) -> List[PromptIssue]:
        """
        Поиск промптов без обработки ошибок.

        Логика: если есть repeated retries → нужна error handling
        """
        issues = []
        capabilities_with_retries: Dict[str, int] = {}

        # Подсчёт повторов
        goal_counts: Dict[str, int] = {}
        for trace in traces:
            for step in trace.steps:
                key = f"{step.capability}:{step.goal}"
                goal_counts[key] = goal_counts.get(key, 0) + 1

        # Поиск повторов
        for key, count in goal_counts.items():
            if count >= 2:
                capability = key.split(':')[0]
                capabilities_with_retries[capability] = capabilities_with_retries.get(capability, 0) + count

        # Проверка промптов
        for capability, retry_count in capabilities_with_retries.items():
            sample_prompt = ""
            has_error_handling = False

            for trace in traces:
                for step in trace.steps:
                    if step.capability == capability and step.llm_request:
                        sample_prompt = step.llm_request.prompt
                        # Поиск обработки ошибок
                        if self._prompt_has_error_handling(step.llm_request.prompt):
                            has_error_handling = True
                            break
                if has_error_handling:
                    break

            if not has_error_handling and sample_prompt:
                issues.append(PromptIssue(
                    issue_type='no_error_handling',
                    capability=capability,
                    prompt=sample_prompt,
                    description=f"Промпт не содержит обработки ошибок, но есть {retry_count} повторов",
                    severity="medium",
                    suggestion="Добавить инструкции по обработке ошибок",
                    examples=[]
                ))

        return issues

    def _find_schema_violations(self, traces: List[ExecutionTrace]) -> List[ResponseIssue]:
        """
        Поиск нарушений схемы в ответах.
        """
        issues = []

        for trace in traces:
            for step in trace.steps:
                for error in step.errors:
                    if error.error_type.value == 'schema_violation':
                        if step.llm_response:
                            issues.append(ResponseIssue(
                                issue_type='schema_violation',
                                capability=step.capability,
                                response=step.llm_response.content,
                                description=f"Ответ не соответствует схеме: {error.message}",
                                severity="high"
                            ))

        return issues

    def _find_verbose_responses(self, traces: List[ExecutionTrace]) -> List[ResponseIssue]:
        """
        Поиск слишком подробных ответов.
        """
        issues = []

        for trace in traces:
            for step in trace.steps:
                if step.llm_response:
                    tokens = step.llm_response.tokens_used
                    if tokens > self.thresholds['max_response_tokens']:
                        issues.append(ResponseIssue(
                            issue_type='too_verbose',
                            capability=step.capability,
                            response=step.llm_response.content,
                            description=f"Слишком подробный ответ ({tokens} токенов)",
                            severity="low",
                            suggestion="Ограничить длину ответа в промпте"
                        ))

        return issues

    def _find_incomplete_responses(self, traces: List[ExecutionTrace]) -> List[ResponseIssue]:
        """
        Поиск неполных ответов.
        """
        issues = []

        for trace in traces:
            for step in trace.steps:
                if step.llm_response:
                    content = step.llm_response.content
                    # Проверка на обрывки
                    if content and not content.strip().endswith(('.', '}', ']', ')')):
                        issues.append(ResponseIssue(
                            issue_type='incomplete',
                            capability=step.capability,
                            response=content,
                            description="Ответ обрывается на полуслове",
                            severity="medium"
                        ))

        return issues

    # === Helper методы ===

    def _prompt_has_examples(self, prompt: str) -> bool:
        """Проверка наличия примеров в промпте"""
        example_keywords = ['пример:', 'example:', 'например', 'e.g.', 'input:', 'output:']
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in example_keywords)

    def _prompt_has_constraints(self, prompt: str) -> bool:
        """Проверка наличия ограничений в промпте"""
        constraint_keywords = ['ограничение', 'constraint', 'правило', 'rule', 'должен', 'must', 'нельзя', 'cannot']
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in constraint_keywords)

    def _prompt_has_error_handling(self, prompt: str) -> bool:
        """Проверка наличия обработки ошибок в промпте"""
        error_keywords = ['ошибка', 'error', 'если ошибка', 'if error', 'обработ', 'handle']
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in error_keywords)

    def get_analysis_stats(
        self,
        prompt_issues: List[PromptIssue],
        response_issues: List[ResponseIssue]
    ) -> Dict[str, Any]:
        """
        Получение статистики анализа.

        ARGS:
        - prompt_issues: проблемы промптов
        - response_issues: проблемы ответов

        RETURNS:
        - Dict[str, Any]: статистика
        """
        # Группировка по типам
        prompt_by_type = {}
        for issue in prompt_issues:
            t = issue.issue_type
            prompt_by_type[t] = prompt_by_type.get(t, 0) + 1

        response_by_type = {}
        for issue in response_issues:
            t = issue.issue_type
            response_by_type[t] = response_by_type.get(t, 0) + 1

        # Группировка по серьёзности
        by_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for issue in prompt_issues + response_issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

        return {
            'total_prompt_issues': len(prompt_issues),
            'total_response_issues': len(response_issues),
            'prompt_by_type': prompt_by_type,
            'response_by_type': response_by_type,
            'by_severity': by_severity,
            'critical_high_count': by_severity['critical'] + by_severity['high']
        }

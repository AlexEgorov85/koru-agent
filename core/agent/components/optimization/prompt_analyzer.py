"""
PromptResponseAnalyzer — анализ промптов и ответов LLM.

КОМПОНЕНТЫ:
- PromptResponseAnalyzer: анализ качества промптов и ответов
- SessionPromptAnalyzer: анализ промптов на основе лога сессии

FEATURES:
- Поиск проблем в промптах (missing examples, ambiguous, no constraints)
- Поиск проблем в ответах (schema violations, verbose, off-topic)
- Рекомендации по улучшению
- Session-based prompt analysis
"""
import json
from pathlib import Path
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


# === Session Log Analysis ===

@dataclass
class SessionBasedIssue:
    """Проблема обнаруженная через анализ лога сессии"""
    capability: str
    prompt_file: str
    issue_type: str
    severity: str
    description: str
    section: Optional[str] = None
    suggested_fix: Optional[str] = None


class SessionPromptAnalyzer:
    """
    Анализатор промптов на основе лога сессии.
    
    АНАЛИЗИРУЕТ:
    - Какие capability используются в сессии
    - Какие промпты соответствуют этим capability
    - Конкретные проблемы и рекомендации
    """
    
    ACTION_TO_CAPABILITY = {
        'book_library.execute_script': 'behavior.react.act',
        'book_library.search_books': 'behavior.react.think',
        'final_answer.generate': 'final_answer.generate',
        'data_analysis.analyze_step_data': 'data_analysis',
        'planning.create_plan': 'planning',
        'planning.update_plan': 'planning',
    }
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path('data')
        self.issues: List[SessionBasedIssue] = []
    
    def analyze_from_session(
        self,
        actions: List[Dict],
        patterns: Dict[str, int],
        failed_actions: List[Dict]
    ) -> List[SessionBasedIssue]:
        """Анализ сессии и генерация проблем с промптами."""
        self.issues = []
        
        # 1. Проверяем паттерны
        
        # Агент предпочитает execute_script вместо search_books
        execute_count = patterns.get('uses_execute_script', 0)
        search_count = patterns.get('uses_search_books', 0)
        
        if execute_count > search_count * 1.5 and search_count > 0:
            self.issues.append(SessionBasedIssue(
                capability='behavior.react.think',
                prompt_file='data/prompts/behavior/behavior/behavior.react.think.user_v1.0.0.yaml',
                issue_type='wrong_tool_selection',
                severity='high',
                description=(
                    f"Agent uses execute_script ({execute_count} times) "
                    f"more often than search_books ({search_count} times). "
                    f"Need clear rules for tool selection."
                ),
                section='ПРАВИЛА ВЫБОРА',
                suggested_fix=self._tool_selection_fix()
            ))
        
        # Зацикливание
        loops = patterns.get('loops', 0)
        if loops >= 2:
            self.issues.append(SessionBasedIssue(
                capability='behavior.react.think',
                prompt_file='data/prompts/behavior/behavior/behavior.react.think.user_v1.0.0.yaml',
                issue_type='looping',
                severity='high',
                description=f"Agent loops {loops} times. Need clear stop rules.",
                section='ПРИМЕР',
                suggested_fix=self._looping_fix()
            ))
        
        # 2. Проверяем ошибки
        for failed in failed_actions:
            error = failed.get('error', '')
            reasoning = failed.get('reasoning', '')
            action = failed.get('action', '')
            error_text = error + reasoning  # Проверяем и то и другое
            
            if 'Input validation failed' in error_text:
                if 'get_books_by_year_range' in error_text:
                    self.issues.append(SessionBasedIssue(
                        capability='behavior.react.act',
                        prompt_file='data/prompts/behavior/behavior/behavior.react.act.user_v1.0.0.yaml',
                        issue_type='incorrect_parameters',
                        severity='high',
                        description="Agent calls get_books_by_year_range with incomplete parameters.",
                        section='ДОСТУПНЫЕ СКРИПТЫ',
                        suggested_fix=self._parameters_fix()
                    ))
        
        return self.issues
    
    def _tool_selection_fix(self) -> str:
        return """Add to 'ПРАВИЛА ВЫБОРА ИНСТРУМЕНТА' section:

1. book_library.execute_script - for SIMPLE queries:
   - Search by author (get_books_by_author)
   - Search by genre (get_books_by_genre)
   - Search by title (get_books_by_title_pattern)
   - Get all books (get_all_books)

2. book_library.search_books - for COMPLEX queries:
   - Queries with one parameter (e.g. "books after 1850")
   - Queries with multiple conditions
   - Queries not covered by ready scripts

IMPORTANT: If ready script requires parameters not in query - use search_books"""
    
    def _looping_fix(self) -> str:
        return """Add stop example to 'ПРИМЕР' section:

=== STOP EXAMPLE ===
{
  "thought": "Data already received in step 1. Task complete.",
  "decision": {
    "next_action": "final_answer.generate",
    "stop_condition": true
  }
}

STOP CRITERIA: If data matches goal -> immediately call final_answer.generate"""
    
    def _parameters_fix(self) -> str:
        return """Update get_books_by_year_range in 'ДОСТУПНЫЕ СКРИПТЫ':

- get_books_by_year_range - books by year range
  (parameters year_from and year_to are OPTIONAL!
   year_from=0 default, year_to=9999 default)"""
    
    def get_report(self) -> Dict[str, Any]:
        """Получить отчёт анализа."""
        return {
            'issues': [
                {
                    'capability': issue.capability,
                    'file': issue.prompt_file,
                    'type': issue.issue_type,
                    'severity': issue.severity,
                    'description': issue.description,
                    'section': issue.section,
                    'suggested_fix': issue.suggested_fix,
                }
                for issue in self.issues
            ],
            'summary': {
                'total': len(self.issues),
                'high': len([i for i in self.issues if i.severity == 'high']),
                'medium': len([i for i in self.issues if i.severity == 'medium']),
                'low': len([i for i in self.issues if i.severity == 'low']),
            }
        }


def analyze_prompts_from_session(session_report: Dict, data_dir: Path = None) -> Dict[str, Any]:
    """
    Анализ промптов на основе отчёта сессии.
    
    ARGS:
        session_report: отчёт от SessionLogParser
        data_dir: директория с данными
    
    RETURNS:
        Dict с детальным анализом и рекомендациями
    """
    analyzer = SessionPromptAnalyzer(data_dir)
    
    patterns = session_report.get('patterns', {})
    failed_actions = session_report.get('failed_actions', [])
    
    analyzer.analyze_from_session(
        actions=[{'action': a.get('action', ''), 'error': a.get('error', '')} 
                 for a in failed_actions],
        patterns=patterns,
        failed_actions=failed_actions
    )
    
    return analyzer.get_report()

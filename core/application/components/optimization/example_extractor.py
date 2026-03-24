"""
ExampleExtractor — извлечение примеров из traces.

КОМПОНЕНТЫ:
- ExampleExtractor: извлечение хороших и плохих примеров

FEATURES:
- Извлечение успешных примеров для few-shot обучения
- Извлечение примеров ошибок для анализа
- Форматирование примеров для промпта
"""
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from core.models.data.execution_trace import ExecutionTrace, StepTrace, LLMRequest, LLMResponse


@dataclass
class Example:
    """
    Пример выполнения.

    ATTRIBUTES:
    - id: идентификатор примера
    - capability: название способности
    - input: входные данные
    - output: выходные данные
    - success: успешность
    - steps: количество шагов
    - time_ms: время выполнения
    - session_id: идентификатор сессии
    - metadata: дополнительные метаданные
    """
    id: str
    capability: str
    input: str
    output: str
    success: bool
    steps: int = 1
    time_ms: float = 0.0
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_format(self, include_input: bool = True, include_output: bool = True) -> str:
        """
        Форматирование для вставки в промпт.

        ARGS:
        - include_input: включать ли input
        - include_output: включать ли output

        RETURNS:
        - str: отформатированный пример
        """
        parts = []

        if include_input:
            parts.append(f"INPUT: {self.input}")

        if include_output:
            parts.append(f"OUTPUT: {self.output}")

        if self.metadata.get('notes'):
            parts.append(f"NOTES: {self.metadata['notes']}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'capability': self.capability,
            'input': self.input,
            'output': self.output,
            'success': self.success,
            'steps': self.steps,
            'time_ms': self.time_ms,
            'session_id': self.session_id,
            'metadata': self.metadata
        }


@dataclass
class ErrorExample:
    """
    Пример ошибки.

    ATTRIBUTES:
    - id: идентификатор
    - capability: название способности
    - input: входные данные
    - error: текст ошибки
    - error_type: тип ошибки
    - session_id: идентификатор сессии
    - fix_suggestion: предложение по исправлению
    """
    id: str
    capability: str
    input: str
    error: str
    error_type: str
    session_id: str
    fix_suggestion: str = ""

    def to_prompt_format(self) -> str:
        """Форматирование для вставки в промпт"""
        return f"""WRONG EXAMPLE:
INPUT: {self.input}
ERROR: {self.error}
CORRECT APPROACH: {self.fix_suggestion or 'Handle this case gracefully'}"""

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'capability': self.capability,
            'input': self.input,
            'error': self.error,
            'error_type': self.error_type,
            'session_id': self.session_id,
            'fix_suggestion': self.fix_suggestion
        }


class ExampleExtractor:
    """
    Извлекатель примеров из execution traces.

    RESPONSIBILITIES:
    - Извлечение успешных примеров
    - Извлечение примеров ошибок
    - Форматирование для промпта

    USAGE:
    ```python
    extractor = ExampleExtractor()
    good_examples = extractor.extract_good_examples(traces, 'book_library.search_books')
    error_examples = extractor.extract_error_examples(traces, 'syntax_error')
    ```
    """

    def __init__(self):
        """Инициализация экстрактора"""
        # Критерии для хороших примеров
        self.good_example_criteria = {
            'max_steps': 5,  # ≤5 шагов
            'max_time_ms': 5000,  # ≤5 секунд
            'must_have_output': True,
        }

    def extract_good_examples(
        self,
        traces: List[ExecutionTrace],
        capability: Optional[str] = None,
        limit: int = 5
    ) -> List[Example]:
        """
        Извлечение хороших примеров.

        ARGS:
        - traces: список execution traces
        - capability: фильтр по способности (опционально)
        - limit: максимум примеров

        RETURNS:
        - List[Example]: список хороших примеров
        """
        good_examples = []

        # Фильтрация успешных traces
        successful_traces = [t for t in traces if t.success]

        # Дополнительная фильтрация по capability
        if capability:
            successful_traces = [
                t for t in successful_traces
                if capability in t.get_capabilities_used()
            ]

        # Сортировка по эффективности (меньше шагов и времени = лучше)
        successful_traces.sort(key=lambda t: (t.step_count, t.total_time_ms))

        # Извлечение примеров
        for trace in successful_traces[:limit]:
            example = self._create_example_from_trace(trace, is_good=True)
            if example:
                good_examples.append(example)

        return good_examples

    def extract_error_examples(
        self,
        traces: List[ExecutionTrace],
        error_type: Optional[str] = None,
        capability: Optional[str] = None,
        limit: int = 5
    ) -> List[ErrorExample]:
        """
        Извлечение примеров ошибок.

        ARGS:
        - traces: список execution traces
        - error_type: фильтр по типу ошибки (опционально)
        - capability: фильтр по способности (опционально)
        - limit: максимум примеров

        RETURNS:
        - List[ErrorExample]: список примеров ошибок
        """
        error_examples = []

        for trace in traces:
            if len(error_examples) >= limit:
                break

            # Поиск ошибок в шагах
            for step in trace.steps:
                if len(error_examples) >= limit:
                    break

                for error in step.errors:
                    # Фильтр по error_type
                    if error_type and error.error_type.value != error_type:
                        continue

                    # Фильтр по capability
                    if capability and step.capability != capability:
                        continue

                    example = self._create_error_example_from_step(step, error, trace.session_id)
                    if example:
                        error_examples.append(example)

        return error_examples

    def extract_few_shot_examples(
        self,
        traces: List[ExecutionTrace],
        capability: str,
        num_good: int = 3,
        num_bad: int = 2
    ) -> Tuple[List[Example], List[ErrorExample]]:
        """
        Извлечение few-shot примеров (хорошие + плохие).

        ARGS:
        - traces: список execution traces
        - capability: название способности
        - num_good: количество хороших примеров
        - num_bad: количество плохих примеров

        RETURNS:
        - Tuple[List[Example], List[ErrorExample]]: (хорошие, плохие)
        """
        good_examples = self.extract_good_examples(
            traces,
            capability=capability,
            limit=num_good
        )

        error_examples = self.extract_error_examples(
            traces,
            capability=capability,
            limit=num_bad
        )

        return good_examples, error_examples

    def format_examples_for_prompt(
        self,
        good_examples: List[Example],
        error_examples: Optional[List[ErrorExample]] = None,
        section_title: str = "EXAMPLES"
    ) -> str:
        """
        Форматирование примеров для вставки в промпт.

        ARGS:
        - good_examples: хорошие примеры
        - error_examples: примеры ошибок (опционально)
        - section_title: заголовок секции

        RETURNS:
        - str: отформатированные примеры
        """
        parts = [f"# {section_title}\n"]

        # Хорошие примеры
        if good_examples:
            parts.append("## Good Examples\n")
            for i, example in enumerate(good_examples, 1):
                parts.append(f"### Example {i}")
                parts.append(example.to_prompt_format())
                parts.append("")

        # Примеры ошибок
        if error_examples:
            parts.append("## Common Mistakes\n")
            for i, example in enumerate(error_examples, 1):
                parts.append(f"### Mistake {i}")
                parts.append(example.to_prompt_format())
                parts.append("")

        return "\n".join(parts)

    def _create_example_from_trace(
        self,
        trace: ExecutionTrace,
        is_good: bool = True
    ) -> Optional[Example]:
        """
        Создание примера из trace.

        ARGS:
        - trace: execution trace
        - is_good: хороший ли пример

        RETURNS:
        - Optional[Example]: пример или None
        """
        # Проверка критериев для хорошего примера
        if is_good:
            if trace.step_count > self.good_example_criteria['max_steps']:
                return None
            if trace.total_time_ms > self.good_example_criteria['max_time_ms']:
                return None
            if not trace.final_answer:
                return None

        # Извлечение input/output
        input_text = trace.goal
        output_text = trace.final_answer or ""

        # Метаданные
        metadata = {
            'notes': f"Completed in {trace.step_count} steps, {trace.total_time_ms/1000:.1f}s"
        }

        return Example(
            id=f"example_{trace.session_id}",
            capability=trace.get_capabilities_used()[0] if trace.get_capabilities_used() else "unknown",
            input=input_text,
            output=output_text,
            success=trace.success,
            steps=trace.step_count,
            time_ms=trace.total_time_ms,
            session_id=trace.session_id,
            metadata=metadata
        )

    def _create_error_example_from_step(
        self,
        step: StepTrace,
        error,
        session_id: str
    ) -> Optional[ErrorExample]:
        """
        Создание примера ошибки из шага.

        ARGS:
        - step: шаг с ошибкой
        - error: объект ошибки
        - session_id: идентификатор сессии

        RETURNS:
        - Optional[ErrorExample]: пример ошибки или None
        """
        if not error:
            return None

        # Генерация предложения по исправлению
        fix_suggestion = self._generate_fix_suggestion(error)

        return ErrorExample(
            id=f"error_{session_id}_{step.step_number}",
            capability=step.capability,
            input=step.goal,
            error=error.message,
            error_type=error.error_type.value,
            session_id=session_id,
            fix_suggestion=fix_suggestion
        )

    def _generate_fix_suggestion(self, error) -> str:
        """
        Генерация предложения по исправлению ошибки.

        ARGS:
        - error: объект ошибки

        RETURNS:
        - str: предложение по исправлению
        """
        error_type = error.error_type.value

        suggestions = {
            'syntax_error': "Check syntax and use proper formatting",
            'validation_error': "Validate input against schema before processing",
            'timeout': "Add timeout handling and retry logic",
            'connection_error': "Implement connection pooling and retry mechanism",
            'logic_error': "Review decision logic and add edge case handling",
            'context_loss': "Maintain context explicitly in each step",
            'schema_violation': "Follow the exact output schema format",
            'unknown': "Add comprehensive error handling"
        }

        return suggestions.get(error_type, suggestions['unknown'])

    def get_extraction_stats(
        self,
        good_examples: List[Example],
        error_examples: List[ErrorExample]
    ) -> Dict[str, Any]:
        """
        Получение статистики извлечения.

        ARGS:
        - good_examples: хорошие примеры
        - error_examples: примеры ошибок

        RETURNS:
        - Dict[str, Any]: статистика
        """
        # Статистика хороших примеров
        good_stats = {
            'total': len(good_examples),
            'avg_steps': sum(e.steps for e in good_examples) / len(good_examples) if good_examples else 0,
            'avg_time_ms': sum(e.time_ms for e in good_examples) / len(good_examples) if good_examples else 0,
        }

        # Статистика примеров ошибок
        error_by_type = {}
        for example in error_examples:
            t = example.error_type
            error_by_type[t] = error_by_type.get(t, 0) + 1

        error_stats = {
            'total': len(error_examples),
            'by_type': error_by_type
        }

        return {
            'good_examples': good_stats,
            'error_examples': error_stats
        }

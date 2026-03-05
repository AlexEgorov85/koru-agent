"""
Сервис оценки точности (Accuracy Evaluator).

КОМПОНЕНТЫ:
- IEvaluationStrategy: протокол стратегии оценки
- AccuracyEvaluatorService: основной сервис оценки
- ExactMatchEvaluator: точное совпадение
- CoverageEvaluator: оценка покрытия
- SemanticEvaluator: семантическая оценка (через LLM)
- HybridEvaluator: гибридная оценка

FEATURES:
- Различные стратегии оценки результатов
- Поддержка JSON Schema валидации
- Семантическая оценка через LLM
- Гибридные стратегии
"""
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Tuple
from dataclasses import dataclass

from core.models.data.benchmark import (
    ExpectedOutput,
    ActualOutput,
    EvaluationCriterion,
    EvaluationType,
    CriterionScore,
)


# ============================================================================
# Протоколы и интерфейсы
# ============================================================================


class IEvaluationStrategy(Protocol):
    """
    Протокол стратегии оценки.

    RESPONSIBILITIES:
    - Оценка соответствия фактического вывода ожидаемому
    - Возврат оценки (0.0-1.0)
    """

    async def evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput
    ) -> Tuple[float, str]:
        """
        Оценка соответствия вывода.

        ARGS:
        - expected: ожидаемый вывод
        - actual: фактический вывод

        RETURNS:
        - Tuple[float, str]: (оценка 0.0-1.0, детали оценки)
        """
        ...


# ============================================================================
# Стратегии оценки
# ============================================================================


class ExactMatchEvaluator:
    """
    Оценка точного совпадения.

    USE CASES:
    - Точное совпадение строк
    - Точное совпадение JSON
    - Бинарная оценка (pass/fail)
    """

    async def evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput
    ) -> Tuple[float, str]:
        """
        Оценка точного совпадения.

        ЛОГИКА:
        1. Если expected.content - строка: точное совпадение строк
        2. Если expected.content - dict: сравнение JSON
        3. Если есть schema: валидация по схеме
        """
        expected_content = expected.content
        actual_content = actual.content

        # Проверка None
        if expected_content is None and actual_content is None:
            return (1.0, "Оба значения None")

        if expected_content is None or actual_content is None:
            return (0.0, "Одно из значений None")

        # Проверка схемы если указана
        if expected.schema:
            schema_valid, schema_msg = self._validate_schema(actual_content, expected.schema)
            if not schema_valid:
                return (0.0, f"Не прошла валидация схемы: {schema_msg}")

        # Точное сравнение
        if isinstance(expected_content, str) and isinstance(actual_content, str):
            # Нормализация строк (удаление лишних пробелов)
            expected_normalized = self._normalize_string(expected_content)
            actual_normalized = self._normalize_string(actual_content)

            if expected_normalized == actual_normalized:
                return (1.0, "Точное совпадение строк")
            else:
                return (0.0, "Строки не совпадают")

        # Сравнение dict/списков
        if isinstance(expected_content, (dict, list)) and isinstance(actual_content, (dict, list)):
            try:
                # Сериализация в JSON для сравнения
                expected_json = json.dumps(expected_content, sort_keys=True, ensure_ascii=False)
                actual_json = json.dumps(actual_content, sort_keys=True, ensure_ascii=False)

                if expected_json == actual_json:
                    return (1.0, "Точное совпадение JSON")
                else:
                    return (0.0, "JSON не совпадают")
            except (TypeError, ValueError) as e:
                return (0.0, f"Ошибка сравнения JSON: {e}")

        # Простое сравнение
        if expected_content == actual_content:
            return (1.0, "Точное совпадение")

        return (0.0, "Значения не совпадают")

    def _normalize_string(self, s: str) -> str:
        """Нормализация строки"""
        # Удаление лишних пробелов
        s = re.sub(r'\s+', ' ', s.strip())
        return s

    def _validate_schema(self, content: Any, schema: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Валидация контента по JSON Schema.

        Упрощённая валидация без внешних библиотек.
        """
        if not isinstance(schema, dict):
            return (False, "Неверный формат схемы")

        # Проверка типа
        schema_type = schema.get('type')
        if schema_type:
            if schema_type == 'object' and not isinstance(content, dict):
                return (False, f"Ожидался объект, получено {type(content).__name__}")
            if schema_type == 'array' and not isinstance(content, list):
                return (False, f"Ожидался массив, получено {type(content).__name__}")
            if schema_type == 'string' and not isinstance(content, str):
                return (False, f"Ожидалась строка, получено {type(content).__name__}")
            if schema_type == 'number' and not isinstance(content, (int, float)):
                return (False, f"Ожидалось число, получено {type(content).__name__}")
            if schema_type == 'boolean' and not isinstance(content, bool):
                return (False, f"Ожидался boolean, получено {type(content).__name__}")

        # Проверка required полей
        if isinstance(content, dict) and 'required' in schema:
            for field in schema['required']:
                if field not in content:
                    return (False, f"Отсутствует обязательное поле: {field}")

        return (True, "Валидация пройдена")


class CoverageEvaluator:
    """
    Оценка покрытия (coverage).

    USE CASES:
    - Оценка полноты ответа
    - Проверка наличия ключевых элементов
    - Частичное совпадение
    """

    async def evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput
    ) -> Tuple[float, str]:
        """
        Оценка покрытия.

        ЛОГИКА:
        1. Извлечение ключевых элементов из expected
        2. Проверка наличия в actual
        3. Расчёт процента покрытия
        """
        expected_content = expected.content
        actual_content = actual.content

        if expected_content is None:
            return (1.0, "Ожидаемый контент пуст")

        if actual_content is None:
            return (0.0, "Фактический контент пуст")

        # Для строк: проверка ключевых фраз
        if isinstance(expected_content, str):
            return self._evaluate_text_coverage(expected_content, actual_content)

        # Для dict: проверка ключей
        if isinstance(expected_content, dict):
            return self._evaluate_dict_coverage(expected_content, actual_content)

        # Для списков: проверка элементов
        if isinstance(expected_content, list):
            return self._evaluate_list_coverage(expected_content, actual_content)

        return (0.0, "Неподдерживаемый тип контента")

    def _evaluate_text_coverage(self, expected: str, actual: Any) -> Tuple[float, str]:
        """Оценка покрытия текста"""
        if not isinstance(actual, str):
            actual = str(actual)

        # Извлечение ключевых слов (простая эвристика)
        expected_words = set(self._extract_keywords(expected))
        if not expected_words:
            return (1.0, "Нет ключевых слов для проверки")

        actual_lower = actual.lower()
        matched_words = [w for w in expected_words if w in actual_lower]

        coverage = len(matched_words) / len(expected_words)

        if coverage == 1.0:
            return (1.0, "Полное покрытие ключевых слов")
        elif coverage >= 0.8:
            return (coverage, f"Покрытие {coverage:.0%}: найдено {len(matched_words)}/{len(expected_words)} ключевых слов")
        elif coverage >= 0.5:
            return (coverage, f"Частичное покрытие {coverage:.0%}")
        else:
            return (coverage, f"Низкое покрытие {coverage:.0%}")

    def _evaluate_dict_coverage(self, expected: dict, actual: Any) -> Tuple[float, str]:
        """Оценка покрытия dict"""
        if not isinstance(actual, dict):
            return (0.0, "Ожидался dict")

        if not expected:
            return (1.0, "Ожидаемый dict пуст")

        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())

        matched_keys = expected_keys & actual_keys
        coverage = len(matched_keys) / len(expected_keys)

        # Проверка значений для совпавших ключей
        value_matches = 0
        for key in matched_keys:
            if expected[key] == actual[key]:
                value_matches += 1

        value_coverage = value_matches / len(matched_keys) if matched_keys else 0

        if coverage == 1.0 and value_coverage == 1.0:
            return (1.0, "Полное совпадение ключей и значений")
        elif coverage == 1.0:
            return (0.8, f"Все ключи на месте, {value_coverage:.0%} значений совпадают")
        else:
            return (coverage, f"Найдено {len(matched_keys)}/{len(expected_keys)} ключей")

    def _evaluate_list_coverage(self, expected: list, actual: Any) -> Tuple[float, str]:
        """Оценка покрытия списка"""
        if not isinstance(actual, list):
            return (0.0, "Ожидался список")

        if not expected:
            return (1.0, "Ожидаемый список пуст")

        # Проверка наличия элементов
        matched = 0
        for item in expected:
            if item in actual:
                matched += 1

        coverage = matched / len(expected)

        if coverage == 1.0:
            return (1.0, "Все элементы найдены")
        else:
            return (coverage, f"Найдено {matched}/{len(expected)} элементов")

    def _extract_keywords(self, text: str) -> List[str]:
        """Извлечение ключевых слов"""
        # Простая эвристика: слова > 3 символов
        words = re.findall(r'\b[a-zA-Zа-яА-ЯёЁ]{4,}\b', text.lower())
        # Исключение стоп-слов
        stop_words = {'this', 'that', 'with', 'have', 'from', 'they', 'been', 'would', 'there', 'their'}
        keywords = [w for w in words if w not in stop_words]
        return keywords


class SemanticEvaluator:
    """
    Семантическая оценка через LLM.

    USE CASES:
    - Оценка смысла ответа
    - Гибкая оценка качества
    - Субъективные критерии

    NOTE: Требует доступа к LLM для оценки.
    """

    def __init__(self, llm_provider=None):
        """
        Инициализация оценщика.

        ARGS:
        - llm_provider: провайдер LLM для семантической оценки
        """
        self.llm_provider = llm_provider

    async def evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput
    ) -> Tuple[float, str]:
        """
        Семантическая оценка.

        ЛОГИКА:
        1. Формирование промпта для LLM
        2. Вызов LLM для оценки
        3. Парсинг ответа (оценка 0-1)
        """
        # Если нет LLM провайдера, используем эвристическую оценку
        if not self.llm_provider:
            return await self._heuristic_evaluate(expected, actual)

        # Формирование промпта
        prompt = self._build_evaluation_prompt(expected, actual)

        try:
            # Вызов LLM через executor (единообразно с другими компонентами)
            # Получаем executor из parent context если доступен
            executor = getattr(self, 'executor', None)
            
            if executor:
                result = await executor.execute_action(
                    action_name="llm.generate",
                    llm_provider=self.llm_provider,
                    parameters={
                        'prompt': prompt,
                        'temperature': 0.1,
                        'max_tokens': 500
                    }
                )
                response = result['data']['content']
            else:
                # Fallback: прямой вызов если executor недоступен
                response = await self.llm_provider.generate(prompt)
            
            score, details = self._parse_llm_response(response)
            return (score, details)
        except Exception as e:
            # Fallback на эвристическую оценку
            return await self._heuristic_evaluate(expected, actual)

    async def _heuristic_evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput
    ) -> Tuple[float, str]:
        """Эвристическая оценка без LLM"""
        # Использование CoverageEvaluator как fallback
        coverage_eval = CoverageEvaluator()
        return await coverage_eval.evaluate(expected, actual)

    def _build_evaluation_prompt(self, expected: ExpectedOutput, actual: ActualOutput) -> str:
        """Формирование промпта для оценки"""
        return f"""
Оцени соответствие ответа ожидаемому результату.

ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
{expected.content}

ФАКТИЧЕСКИЙ ОТВЕТ:
{actual.content}

КРИТЕРИИ ОЦЕНКИ:
- Смысловое соответствие
- Полнота ответа
- Точность информации

ФОРМАТ ОТВЕТА:
Оценка: <число от 0.0 до 1.0>
Обоснование: <краткое объяснение>
"""

    def _parse_llm_response(self, response: str) -> Tuple[float, str]:
        """Парсинг ответа LLM"""
        # Поиск оценки в ответе
        score_match = re.search(r'[Оо]ценка[:\s]*([0-9.]+)', response)
        if score_match:
            try:
                score = float(score_match.group(1))
                score = max(0.0, min(1.0, score))  # Ограничение 0-1

                # Поиск обоснования
                details_match = re.search(r'[Оо]боснование[:\s]*(.+)', response, re.DOTALL)
                details = details_match.group(1).strip() if details_match else response

                return (score, details)
            except ValueError:
                pass

        # Если не удалось распарсить, возвращаем среднюю оценку
        return (0.5, "Не удалось распарсить оценку LLM")


class HybridEvaluator:
    """
    Гибридный оценщик.

    USE CASES:
    - Комбинация нескольких стратегий
    - Взвешенная оценка
    - Надёжная оценка качества

    COMBINES:
    - ExactMatch (вес: 0.3)
    - Coverage (вес: 0.4)
    - Semantic (вес: 0.3)
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        llm_provider=None
    ):
        """
        Инициализация гибридного оценщика.

        ARGS:
        - weights: веса стратегий {'exact': 0.3, 'coverage': 0.4, 'semantic': 0.3}
        - llm_provider: провайдер LLM для семантической оценки
        """
        self.weights = weights or {
            'exact': 0.3,
            'coverage': 0.4,
            'semantic': 0.3
        }

        self.exact_evaluator = ExactMatchEvaluator()
        self.coverage_evaluator = CoverageEvaluator()
        self.semantic_evaluator = SemanticEvaluator(llm_provider)

    async def evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput
    ) -> Tuple[float, str]:
        """
        Гибридная оценка.

        ЛОГИКА:
        1. Оценка каждой стратегией
        2. Взвешенное усреднение
        3. Возврат综合ной оценки
        """
        # Оценка каждой стратегией
        exact_score, exact_details = await self.exact_evaluator.evaluate(expected, actual)
        coverage_score, coverage_details = await self.coverage_evaluator.evaluate(expected, actual)
        semantic_score, semantic_details = await self.semantic_evaluator.evaluate(expected, actual)

        # Взвешенное усреднение
        final_score = (
            self.weights.get('exact', 0) * exact_score +
            self.weights.get('coverage', 0) * coverage_score +
            self.weights.get('semantic', 0) * semantic_score
        )

        # Формирование деталей
        details = (
            f"Exact Match: {exact_score:.2f} ({exact_details})\n"
            f"Coverage: {coverage_score:.2f} ({coverage_details})\n"
            f"Semantic: {semantic_score:.2f} ({semantic_details})\n"
            f"Итоговая оценка: {final_score:.2f}"
        )

        return (final_score, details)


# ============================================================================
# Основной сервис оценки
# ============================================================================


@dataclass
class EvaluationResult:
    """Результат оценки"""
    score: float
    passed: bool
    details: str
    criterion: str
    evaluation_type: EvaluationType


class AccuracyEvaluatorService:
    """
    Сервис оценки точности выполнения бенчмарков.

    RESPONSIBILITIES:
    - Выбор стратегии оценки на основе критерия
    - Оценка соответствия вывода
    - Агрегация результатов по нескольким критериям

    USAGE:
    ```python
    evaluator = AccuracyEvaluatorService()
    result = await evaluator.evaluate(expected_output, actual_output, criterion)
    ```
    """

    def __init__(self, llm_provider=None):
        """
        Инициализация сервиса оценки.

        ARGS:
        - llm_provider: провайдер LLM для семантической оценки
        """
        self.llm_provider = llm_provider

        # Инициализация оценщиков
        self._evaluators = {
            EvaluationType.EXACT_MATCH: ExactMatchEvaluator(),
            EvaluationType.COVERAGE: CoverageEvaluator(),
            EvaluationType.SEMANTIC: SemanticEvaluator(llm_provider),
            EvaluationType.CUSTOM: HybridEvaluator(llm_provider=llm_provider),
        }

    async def evaluate(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput,
        criterion: EvaluationCriterion
    ) -> EvaluationResult:
        """
        Оценка соответствия вывода критерию.

        ARGS:
        - expected: ожидаемый вывод
        - actual: фактический вывод
        - criterion: критерий оценки

        RETURNS:
        - EvaluationResult: результат оценки
        """
        # Выбор оценщика
        evaluator = self._get_evaluator(criterion.evaluation_type)

        # Оценка
        score, details = await evaluator.evaluate(expected, actual)

        # Проверка порога
        passed = score >= criterion.threshold

        return EvaluationResult(
            score=score,
            passed=passed,
            details=details,
            criterion=criterion.name,
            evaluation_type=criterion.evaluation_type
        )

    async def evaluate_multiple(
        self,
        expected: ExpectedOutput,
        actual: ActualOutput,
        criteria: List[EvaluationCriterion]
    ) -> List[EvaluationResult]:
        """
        Оценка по нескольким критериям.

        ARGS:
        - expected: ожидаемый вывод
        - actual: фактический вывод
        - criteria: список критериев оценки

        RETURNS:
        - List[EvaluationResult]: результаты оценки
        """
        results = []
        for criterion in criteria:
            result = await self.evaluate(expected, actual, criterion)
            results.append(result)
        return results

    def _get_evaluator(self, evaluation_type: EvaluationType):
        """Получение оценщика по типу"""
        evaluator = self._evaluators.get(evaluation_type)
        if not evaluator:
            # Fallback на CoverageEvaluator
            return self._evaluators[EvaluationType.COVERAGE]
        return evaluator

    def register_evaluator(
        self,
        evaluation_type: EvaluationType,
        evaluator: IEvaluationStrategy
    ) -> None:
        """
        Регистрация пользовательского оценщика.

        ARGS:
        - evaluation_type: тип оценки
        - evaluator: стратегия оценки
        """
        self._evaluators[evaluation_type] = evaluator

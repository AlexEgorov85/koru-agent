"""
PromptAnalyzer — анализ ошибок бенчмарка через LLM.

НАЗНАЧЕНИЕ:
- Анализирует результаты бенчмарка (успешные и проваленные тесты)
- Находит корневые причины ошибок
- Генерирует конкретные предложения по улучшению промптов
- Использует LLM для анализа, а не примитивный поиск ключевых слов
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from core.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.models.enums.common_enums import ComponentType
from core.agent.components.action_executor import ExecutionContext


@dataclass
class PromptAnalyzerInput(ServiceInput):
    """Входные данные для анализа."""
    benchmark_results: List[Dict[str, Any]]
    capability: str
    baseline_accuracy: float


@dataclass
class PromptAnalyzerOutput(ServiceOutput):
    """Результат анализа."""
    root_causes: List[str] = field(default_factory=list)
    prompt_changes: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    analysis_text: str = ""


class PromptAnalyzer(BaseService):
    """
    Анализатор ошибок бенчмарка через LLM.

    RESPONSIBILITIES:
    - Формирует контекст с результатами бенчмарка
    - Отправляет в LLM запрос на анализ
    - Парсит структурированный ответ
    - Возвращает конкретные предложения по улучшению

    USAGE:
    ```python
    analyzer = PromptAnalyzer(application_context, event_bus)
    await analyzer.initialize()
    result = await analyzer.analyze(PromptAnalyzerInput(
        benchmark_results=results,
        capability="book_library",
        baseline_accuracy=0.5
    ))
    ```
    """

    DEPENDENCIES = ["event_bus"]

    def __init__(self, application_context, event_bus=None):
        super().__init__(application_context)
        self._event_bus = event_bus
        self._executor = None

    @property
    def name(self) -> str:
        return "prompt_analyzer"

    @property
    def component_type(self) -> ComponentType:
        return ComponentType.SERVICE

    async def initialize(self) -> bool:
        if self._is_initialized:
            return True
        if self._application_context:
            self._executor = self._application_context.executor
        return await super().initialize()

    async def analyze(self, input_data: PromptAnalyzerInput) -> PromptAnalyzerOutput:
        """Анализ результатов бенчмарка через LLM."""
        if not self._executor:
            return self._fallback_analysis(input_data)

        context = self._build_analysis_context(input_data)
        prompt = self._build_prompt(context)

        try:
            exec_context = ExecutionContext()
            result = await self._executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": prompt,
                    "structured_output": {
                        "type": "object",
                        "properties": {
                            "root_causes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Корневые причины ошибок (1-3 пункта)"
                            },
                            "prompt_changes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Конкретные изменения в промпт (2-4 пункта)"
                            },
                            "examples": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "failed_goal": {"type": "string"},
                                        "expected": {"type": "string"},
                                        "actual": {"type": "string"},
                                        "fix": {"type": "string"}
                                    }
                                },
                                "description": "Примеры ошибок и их исправлений"
                            }
                        },
                        "required": ["root_causes", "prompt_changes"]
                    }
                },
                context=exec_context
            )

            if result.status.value == "completed" and result.data:
                return self._parse_llm_response(result.data, input_data)

        except Exception as e:
            await self._log_error(f"LLM analysis failed: {e}")

        return self._fallback_analysis(input_data)

    def _build_analysis_context(self, input_data: PromptAnalyzerInput) -> Dict[str, Any]:
        failed = [r for r in input_data.benchmark_results if not r.get('success')]
        succeeded = [r for r in input_data.benchmark_results if r.get('success')]

        failed_details = []
        for r in failed:
            failed_details.append({
                "goal": r.get('goal', ''),
                "expected": r.get('expected', {}),
                "actual": r.get('output', '')[:500],
                "error": r.get('error', '')
            })

        return {
            "capability": input_data.capability,
            "baseline_accuracy": input_data.baseline_accuracy,
            "total": len(input_data.benchmark_results),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "failed_details": failed_details
        }

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        failed_list = "\n".join([
            f"- Запрос: {d['goal']}\n  Ожидалось: {d['expected']}\n  Получено: {d['actual']}\n  Ошибка: {d['error']}"
            for d in context['failed_details']
        ])

        return f"""Ты — аналитик качества промптов для AI-агента.

## Задача
Проанализируй ошибки бенчмарка и предложи конкретные улучшения промпта.

## Контекст
- Capability: {context['capability']}
- Точность: {context['baseline_accuracy']:.0%} ({context['succeeded']}/{context['total']})
- Провалено: {context['failed']} тестов

## Ошибки
{failed_list if failed_list else "Нет детальных данных об ошибках"}

## Требования к ответу
1. Найди 1-3 корневые причины ошибок
2. Предложи 2-4 конкретных изменения в промпт
3. Приведи примеры: что ожидалось vs что получено

Верни ответ в формате JSON."""

    def _parse_llm_response(self, data: Any, input_data: PromptAnalyzerInput) -> PromptAnalyzerOutput:
        if isinstance(data, dict):
            return PromptAnalyzerOutput(
                root_causes=data.get('root_causes', []),
                prompt_changes=data.get('prompt_changes', []),
                examples=data.get('examples', []),
                confidence=0.8,
                analysis_text=str(data)
            )
        return self._fallback_analysis(input_data)

    def _fallback_analysis(self, input_data: PromptAnalyzerInput) -> PromptAnalyzerOutput:
        """Fallback если LLM недоступен."""
        failed = [r for r in input_data.benchmark_results if not r.get('success')]

        root_causes = []
        prompt_changes = []

        for r in failed:
            error = r.get('error', '').lower()
            output = r.get('output', '').lower()

            if 'timeout' in error:
                if "LLM таймауты" not in root_causes:
                    root_causes.append("LLM таймауты")
                    prompt_changes.append("Упростить структуру ответа, уменьшить max_tokens")
            elif 'json' in error or 'parse' in error:
                if "Парсинг JSON" not in root_causes:
                    root_causes.append("Ошибки парсинга JSON")
                    prompt_changes.append("Добавить больше примеров JSON в промпт")
            elif 'sql' in error:
                if "Генерация SQL" not in root_causes:
                    root_causes.append("Ошибки генерации SQL")
                    prompt_changes.append("Улучшить инструкции по генерации SQL")
            elif 'не найден' in output or 'not found' in output:
                if "Валидация параметров" not in root_causes:
                    root_causes.append("Валидация параметров")
                    prompt_changes.append("Добавить правила проверки входных данных")

        if not root_causes:
            root_causes.append("Недостаточная точность ответов")
            prompt_changes.append("Добавить примеры успешных ответов в промпт")

        return PromptAnalyzerOutput(
            root_causes=root_causes,
            prompt_changes=prompt_changes,
            confidence=0.5,
            analysis_text="Fallback analysis (LLM unavailable)"
        )

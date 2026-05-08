"""
Навык анализа данных — оркестратор стратегий.

АРХИТЕКТУРА:
- DataAnalysisSkill — тонкий оркестратор (НЕ содержит логику анализа)
- Стратегии (PythonStrategy, LLMStrategy, MapReduceStrategy) — изолированные режимы
- base_strategy.py — контракт для всех стратегий
- prompts.py — чистые функции рендеринга

ДОБАВЛЕНИЕ НОВОГО РЕЖИМА:
1. Новый файл в strategies/
2. Одна строка регистрации в __init__

ИСПОЛЬЗОВАНИЕ:
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Какие ключевые темы?",
            "step_id": 1,
            "mode": "auto"  # Опционально: python, llm, mapreduce, auto
        },
        context=execution_context
    )
"""
import time
from typing import Any, Dict, List, Optional

from core.components.skills.skill import Skill
from core.components.skills.data_analysis.base_strategy import AbstractStrategy, AnalysisInput, AnalysisResult
from core.components.skills.data_analysis.strategies import PythonStrategy, LLMStrategy, MapReduceStrategy
from core.models.data.capability import Capability


class DataAnalysisSkill(Skill):
    """Оркестратор анализа данных. Делегирует выполнение стратегиям."""

    name: str = "data_analysis"

    DEFAULT_CONTEXT_WINDOW = 8192
    DEFAULT_MAX_NEW_TOKENS = 2000

    @property
    def description(self) -> str:
        return "Анализ данных с LLM и MapReduce"

    def __init__(
        self,
        name: str,
        component_config: Any,
        executor: Any,
        application_context: Any = None,
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context,
        )
        self._context_window = self.DEFAULT_CONTEXT_WINDOW
        self._max_new_tokens = self.DEFAULT_MAX_NEW_TOKENS

        self._strategies: List[AbstractStrategy] = [
            PythonStrategy(self),
            LLMStrategy(self),
            MapReduceStrategy(self),
        ]

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="data_analysis.analyze_step_data",
                description="Анализ данных шага с LLM и MapReduce",
                skill_name=self.name,
                supported_strategies=["react"],
                visible=True,
                meta={"mapreduce": True},
            )
        ]

    async def initialize(self) -> bool:
        return await super().initialize()

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        context: Any,
    ) -> Dict[str, Any]:
        start_time = time.time()

        params_dict = self._normalize_parameters(parameters)

        question = params_dict.get("question")
        step_id = params_dict.get("step_id")
        mode_override = params_dict.get("mode")

        if not question:
            raise ValueError("Параметр 'question' обязателен")
        if step_id is None:
            raise ValueError("Параметр 'step_id' обязателен")

        data = self._get_step_data(context, step_id)
        if data is None:
            raise ValueError(f"Данные шага {step_id} не найдены")

        rows = self._normalize_to_rows(data)

        strategies = self._select_strategies(rows, question, mode_override)

        input_data = AnalysisInput(
            data=rows,
            question=question,
            step_id=step_id,
            execution_context=context,
            capabilities=[],
        )

        result = await self._execute_with_fallback(strategies, input_data)

        processing_time = round((time.time() - start_time) * 1000, 2)
        result.metadata["processing_time_ms"] = processing_time

        await self._save_result_to_context(
            context, question, result.answer, step_id, result.metadata,
        )

        return {
            "answer": result.answer,
            "execution_status": "error" if result.error else "success",
            "execution_error": result.error,
            "confidence": result.confidence,
            "executed_operations": result.operations,
            "metadata": result.metadata,
        }

    def _normalize_parameters(self, parameters: Any) -> Dict[str, Any]:
        """Нормализация параметров к словарю."""
        if hasattr(parameters, 'model_dump'):
            return parameters.model_dump()
        elif hasattr(parameters, 'dict'):
            return parameters.dict()
        elif isinstance(parameters, dict):
            return parameters
        raise ValueError(f"Неподдерживаемый тип параметров: {type(parameters)}")

    def _normalize_to_rows(self, data: Any) -> List[Dict[str, Any]]:
        """Приводит данные к единому формату List[Dict]."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                return data
            return data
        if isinstance(data, dict):
            if "rows" in data and isinstance(data["rows"], list):
                return self._normalize_to_rows(data["rows"])
            if "data" in data:
                return self._normalize_to_rows(data["data"])
            return [data]
        if isinstance(data, str):
            return [{"text": data}]
        return [{"content": str(data)}]

    def _select_strategies(
        self,
        data: List[Dict],
        question: str,
        mode_override: Optional[str],
    ) -> List[AbstractStrategy]:
        """Выбирает стратегии на основе mode_override или can_handle."""
        if mode_override and mode_override != "auto":
            for s in self._strategies:
                if s.name == mode_override:
                    return [s]
            raise ValueError(f"Неизвестный режим: {mode_override}")

        candidates = [s for s in self._strategies if s.can_handle(data, question)]
        return candidates if candidates else [self._strategies[-1]]

    async def _execute_with_fallback(
        self,
        strategies: List[AbstractStrategy],
        input_data: AnalysisInput,
    ) -> AnalysisResult:
        """Пытает стратегии по порядку. Если первая вернула ошибку/пусто — следующая."""

        for strategy in strategies:
            result = await strategy.execute(input_data)
            if result.error:
                continue
            if result.answer and len(result.answer.strip()) > 0:
                return result

        return AnalysisResult(
            answer="Не удалось проанализировать данные",
            confidence=0.0,
            operations=[],
            metadata={},
        )

    def _get_step_data(self, execution_context: Any, step_id: int) -> Any:
        """Получает данные шага из контекста через observation_item_ids."""
        session = None

        if hasattr(execution_context, 'session_context'):
            session = execution_context.session_context
        elif hasattr(execution_context, 'step_context'):
            session = execution_context

        if session is None:
            return None

        if not hasattr(session, 'step_context') or not hasattr(session, 'data_context'):
            return None

        steps = session.step_context.steps
        if not isinstance(steps, list):
            return None

        step = next((s for s in steps if s.step_number == step_id), None)
        if step is None:
            return None

        if not hasattr(step, 'observation_item_ids') or not step.observation_item_ids:
            return None

        obs_id = step.observation_item_ids[0]
        obs_item = session.data_context.get_item(obs_id, raise_on_missing=False)

        if obs_item is None:
            return None

        content = obs_item.content if hasattr(obs_item, 'content') else obs_item

        if isinstance(content, dict):
            if "rows" in content:
                return content["rows"]
            if "data" in content:
                return content["data"]
            if "type" in content and "data" in content:
                return content["data"]

        return content

    async def _save_result_to_context(
        self,
        execution_context: Any,
        question: str,
        answer: str,
        step_id: int,
        metadata: Dict[str, Any],
    ) -> None:
        """Сохраняет результат анализа в контекст сессии."""
        try:
            session_context = self._get_session_context(execution_context)
            if not session_context:
                return

            result_content = (
                f"=== РЕЗУЛЬТАТ АНАЛИЗА ===\n"
                f"Вопрос: {question}\n\n"
                f"Ответ:\n{answer}\n\n"
                f"---\n"
                f"Метаданные: {metadata}\n"
            )
            session_context.record_observation(
                observation_data=result_content,
                source="data_analysis.analyze_step_data",
                step_number=step_id + 1,
                metadata={
                    "skill": "data_analysis",
                    "question": question,
                    **metadata,
                },
            )
        except Exception:
            pass

    def _get_session_context(self, context: Any) -> Any:
        if hasattr(context, 'session_context'):
            sc = context.session_context
            if sc and hasattr(sc, 'record_observation'):
                return sc
        if hasattr(context, '_session_context'):
            sc = context._session_context
            if sc and hasattr(sc, 'record_observation'):
                return sc
        return None

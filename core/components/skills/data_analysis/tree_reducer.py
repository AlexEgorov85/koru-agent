"""
TreeReducer — итеративное слияние summary с tree-reduce паттерном.

ОТВЕТСТВЕННОСТЬ:
- Итеративное слияние summary от batch-процессора
- Tree-reduce: если summary > threshold → рекурсивный синтез
- Финальный ответ ≤ max_output_tokens
- Сохранение ключевых фактов без потери контекста

АРХИТЕКТУРА:
- Бинарное слияние: 2 summary → 1 merged
- Повторение пока count > 1
- LLM для синтеза при каждом слиянии

ПРИМЕР:
>>> reducer = TreeReducer(executor, context)
>>> final = await reducer.reduce(summaries, max_output_tokens=2000)
"""
from typing import List, Dict, Any, Optional
from core.infrastructure.logging.event_types import LogEventType
from core.models.data.execution import ExecutionStatus


class TreeReducer:
    """
    Tree-reduce синтезатор для объединения summary.

    АРХИТЕКТУРА:
    - Бинарное слияние: пара summary → один merged
    - Повторение until count == 1
    - Threshold для определения необходимости синтеза
    """

    def __init__(
        self,
        executor: Any,
        execution_context: Any,
        max_output_tokens: int = 3000,
        threshold_tokens: int = 1500
    ):
        self.executor = executor
        self.execution_context = execution_context
        self.max_output_tokens = max_output_tokens
        self.threshold_tokens = threshold_tokens

    async def reduce(
        self,
        summaries: List[Dict[str, Any]],
        question: str = ""
    ) -> str:
        """
        Tree-reduce синтез summary в финальный ответ.

        ARGS:
        - summaries: List[Dict] — [{"content": "...", "metadata": {...}}]
        - question: str — вопрос для контекста

        RETURNS:
        - str: финальный объединённый ответ

        EXAMPLE:
        >>> summaries = [{"content": "Чанк 1..."}, {"content": "Чанк 2..."}]
        >>> final = await reducer.reduce(summaries, "Какие тренды?")
        "Объединённый ответ..."
        """
        if not summaries:
            return "Нет данных для анализа"

        if len(summaries) == 1:
            return summaries[0].get("content", "")

        self._log_info(
            f"🌲 [TreeReducer] Начало: {len(summaries)} summaries",
            event_type=LogEventType.INFO
        )

        current_summaries = summaries
        iteration = 0

        while len(current_summaries) > 1:
            iteration += 1
            self._log_info(
                f"🌲 [TreeReducer] Итерация {iteration}: {len(current_summaries)} → ",
                event_type=LogEventType.INFO
            )

            merged = []
            for i in range(0, len(current_summaries), 2):
                if i + 1 < len(current_summaries):
                    pair = [current_summaries[i], current_summaries[i + 1]]
                    merged_result = await self._merge_pair(pair, question, iteration)
                    merged.append(merged_result)
                else:
                    merged.append(current_summaries[i])

            current_summaries = merged

            self._log_info(
                f"🌲 [TreeReducer] Итерация {iteration} завершена: {len(current_summaries)} summaries",
                event_type=LogEventType.INFO
            )

        final_summary = current_summaries[0].get("content", "") if current_summaries else ""

        if len(final_summary) > self.threshold_tokens:
            final_summary = await self._final_synthesis(final_summary, question)

        return final_summary

    async def _merge_pair(
        self,
        pair: List[Dict[str, Any]],
        question: str,
        iteration: int
    ) -> Dict[str, Any]:
        """Слияние пары summary в один."""
        content1 = pair[0].get("content", "")
        content2 = pair[1].get("content", "")

        combined_text = f"Часть A:\n{content1}\n\nЧасть B:\n{content2}"

        if len(combined_text) <= self.threshold_tokens:
            return {"content": combined_text, "merged": True, "iteration": iteration}

        prompt = self._build_merge_prompt(question, content1, content2)

        try:
            result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": self.max_output_tokens // 2
                },
                context=self.execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                merged_content = result.result or combined_text
                return {"content": merged_content, "merged": True, "iteration": iteration}
            else:
                self._log_warning(
                    f"⚠️ [TreeReducer] LLM merge failed: {result.error}",
                    event_type=LogEventType.WARNING
                )
                return {"content": combined_text, "merged": False, "iteration": iteration}

        except Exception as e:
            self._log_warning(
                f"⚠️ [TreeReducer] Merge error: {e}",
                event_type=LogEventType.WARNING
            )
            return {"content": combined_text, "merged": False, "iteration": iteration}

    async def _final_synthesis(
        self,
        content: str,
        question: str
    ) -> str:
        """Финальный синтез для сокращения до max_tokens."""
        prompt = self._build_final_prompt(question, content)

        try:
            result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.2,
                    "max_tokens": self.max_output_tokens
                },
                context=self.execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return result.result or content

        except Exception as e:
            self._log_warning(
                f"⚠️ [TreeReducer] Final synthesis failed: {e}",
                event_type=LogEventType.WARNING
            )

        return content[:self.max_output_tokens * 4]

    def _build_merge_prompt(self, question: str, content1: str, content2: str) -> str:
        """Построение промпта для слияния."""
        return f"""Ты — аналитик данных. Объедини два фрагмента анализа в один связный текст.

Вопрос: {question}

Фрагмент A:
{content1}

Фрагмент B:
{content2}

Инструкции:
- Объедини информацию из обоих фрагментов
- Убери дублирующиеся факты
- Сохрани все ключевые данные и выводы
- Пиши на русском языке
- Не выдумывай факты, которых нет в исходных данных

Объединённый анализ:"""

    def _build_final_prompt(self, question: str, content: str) -> str:
        """Построение промпта для финального синтеза."""
        return f"""Ты — аналитик данных. Сократи и уточни текст анализа.

Вопрос: {question}

Текущий анализ:
{content}

Инструкции:
- Сократи текст до основных фактов и выводов
- Сохрани все важные цифры и метрики
- Убери повторы и_water
- Пиши на русском языке
- Не добавляй информацию, которой нет в исходном тексте

Сокращённый анализ (не более {self.max_output_tokens} токенов):"""

    def _log_info(self, message: str, event_type: LogEventType) -> None:
        import logging
        log = logging.getLogger(__name__)
        log.info(message, extra={"event_type": event_type})

    def _log_warning(self, message: str, event_type: LogEventType) -> None:
        import logging
        log = logging.getLogger(__name__)
        log.warning(message, extra={"event_type": event_type})
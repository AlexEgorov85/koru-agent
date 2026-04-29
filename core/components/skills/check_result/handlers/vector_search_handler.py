import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionStatus
from core.components.action_executor import ExecutionContext
from core.components.skills.handlers.base_handler import SkillHandler
from core.components.tools.vector_search_tool import VectorSearchDefaults


class VectorSearchHandler(SkillHandler):
    """
    Обработчик семантического поиска по нарушениям (violations).

    RESPONSIBILITIES:
    - Семантический поиск по нарушениям (violations)
    - Поиск через vector_search.search с source="violations"
    - Форматирование результатов с контекстом нарушения

    CAPABILITY:
    - check_result.vector_search
    """

    capability_name = "check_result.vector_search"
    VECTOR_SOURCE = "violations"  # Жестко заданный источник

    def __init__(self, skill):
        super().__init__(skill)

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Семантический поиск по нарушениям.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        start_time = time.time()

        query = params.query if hasattr(params, 'query') else ''
        source = self.VECTOR_SOURCE

        # Обработка None значений от LLM — используем default
        top_k = getattr(params, 'top_k', VectorSearchDefaults.TOP_K_ALL)
        if top_k is None:
            top_k = VectorSearchDefaults.TOP_K_ALL
        min_score = getattr(params, 'min_score', VectorSearchDefaults.MIN_SCORE_DEFAULT)
        if min_score is None:
            min_score = VectorSearchDefaults.MIN_SCORE_DEFAULT

        limit_str = f"top_k={top_k}" if top_k is not None else "без лимита"
        await self.log_info(f"Запуск векторного поиска: '{query[:80]}...' ({limit_str}, min_score={min_score})")

        results = await self._vector_search(query, source, top_k, min_score)
        formatted_results = await self._format_results(results)

        # Дедупликация по row_id
        best_results = {}
        no_id_results = []

        for item in formatted_results:
            row = item.get("row", {})
            row_id = row.get("id") if row else None
            score = item.get("score", 0.0)

            if row_id is not None:
                dedup_key = f"violations:{row_id}"
                if dedup_key not in best_results or score > best_results[dedup_key][0]:
                    best_results[dedup_key] = (score, item)
            else:
                no_id_results.append(item)

        unique_results = [item for _, (_, item) in best_results.items()] + no_id_results

        total_time = time.time() - start_time

        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="vector_search",
            rows_returned=len(unique_results)
        )

        return unique_results

    async def _vector_search(
        self,
        query: str,
        source: str,
        top_k: int,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """Выполнение векторного поиска через vector_search_tool."""
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="vector_search.search",
            parameters={
                "query": query,
                "top_k": top_k,
                "min_score": min_score,
                "source": source
            },
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            data_dict = result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data
            if isinstance(data_dict, dict):
                results = data_dict.get('results', []) or data_dict.get('data', [])
                return results if isinstance(results, list) else []

        await self.log_warning(
            f"Векторный поиск не вернул результатов: {getattr(result, 'error', 'unknown error')}",
            extra={"event_type": EventType.WARNING}
        )
        return []

    async def _format_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Форматирование результатов векторного поиска (только violations).

        Ожидаемый формат: RowMetadata {row, source, score, content, ...}
        """
        formatted = []

        for item in results:
            score = item.get("score", 0.0)
            row = item.get("row", {})
            content = item.get("content", "")
            search_text = item.get("search_text", content)

            if row:
                formatted_item = self._format_from_row(row, score, search_text)
                formatted.append(formatted_item)
            else:
                await self.log_warning(
                    "Получен результат без row — пропускаем",
                    extra={"event_type": EventType.WARNING}
                )

        return formatted

    def _format_from_row(
        self,
        row: Dict[str, Any],
        score: float,
        search_text: str
    ) -> Dict[str, Any]:
        """Форматирование из формата RowMetadata (только violations)."""
        return {
            "type": "violations",
            "score": round(score, 3),
            "source": "violations",
            "row": row,
            "matched_text": search_text,
            "violation_id": row.get("id"),
            "violation_code": row.get("violation_code", ""),
            "description": row.get("description", ""),
            "recommendation": row.get("recommendation", ""),
            "severity": row.get("severity", ""),
            "status": row.get("status", ""),
            "responsible": row.get("responsible", ""),
            "deadline": row.get("deadline"),
            "audit_id": row.get("audit_id"),
            "audit_title": row.get("audit_title", ""),
        }

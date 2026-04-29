import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionStatus
from core.components.action_executor import ExecutionContext
from core.components.skills.handlers.base_handler import SkillHandler
from core.components.tools.vector_search_tool import VectorSearchDefaults


class VectorSearchHandler(SkillHandler):
    """
    Обработчик семантического поиска по текстам актов аудиторской проверки.

    RESPONSIBILITIES:
    - Семантический поиск по full_text актов (audit_reports)
    - Семантический поиск по item_content пунктов акта (report_items)
    - Поиск через vector_search.search с source="audits"
    - Форматирование результатов с контекстом (название проверки, номер акта)

    CAPABILITY:
    - check_result.vector_search
    """

    capability_name = "check_result.vector_search"

    def __init__(self, skill):
        super().__init__(skill)

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Семантический поиск по текстам актов.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        start_time = time.time()

        query = params.query if hasattr(params, 'query') else ''
        source = getattr(params, 'source', 'audits')
        top_k = getattr(params, 'top_k', VectorSearchDefaults.TOP_K_ALL)
        min_score = getattr(params, 'min_score', VectorSearchDefaults.MIN_SCORE_DEFAULT)

        limit_str = f"top_k={top_k}" if top_k is not None else "без лимита"
        await self.log_info(f"Запуск векторного поиска: '{query[:80]}...' ({limit_str}, min_score={min_score})")

        # Выполняем векторный поиск через vector_search_tool
        results = await self._vector_search(query, source, top_k, min_score)

        # Форматируем результаты
        formatted_results = await self._format_results(results)

        # Дедупликация: одна строка БД может иметь несколько векторов
        # Сохраняем результат с максимальным score для каждой уникальной строки
        best_results = {}  # key: (source, row_id), value: (score, item)
        no_id_results = []

        for item in formatted_results:
            row = item.get("row", {})
            row_id = row.get("id") if row else None
            source_key = item.get("source", "unknown")
            score = item.get("score", 0.0)

            if row_id is not None:
                dedup_key = f"{source_key}:{row_id}"
                if dedup_key not in best_results or score > best_results[dedup_key][0]:
                    best_results[dedup_key] = (score, item)
            else:
                # Строки без id добавляем как есть
                no_id_results.append(item)

        # Собираем уникальные результаты (лучший score для каждой строки)
        unique_results = [item for _, (_, item) in best_results.items()] + no_id_results

        total_time = time.time() - start_time

        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="vector_search",
            rows_returned=len(unique_results)
        )

        # Возвращаем список уникальных результатов — готовые данные для анализа
        return unique_results

    async def _vector_search(
        self,
        query: str,
        source: str,
        top_k: int,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """
        Выполнение векторного поиска через vector_search_tool.

        ARGS:
        - query: Текст запроса
        - source: Источник FAISS индекса (audits, violations, books, ...)
        - top_k: Количество результатов
        - min_score: Минимальный порог схожести

        RETURNS:
        - List[Dict]: Результаты поиска
        """
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
            # Распаковываем данные из результата
            data_dict = result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data
            if isinstance(data_dict, dict):
                results = data_dict.get('results', []) or data_dict.get('data', [])
                return results if isinstance(results, list) else []

        self._log_warning(f"Векторный поиск не вернул результатов: {result.error if hasattr(result, 'error') else 'unknown error'}", event_type=EventType.WARNING)
        return []

    async def _format_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Форматирование результатов векторного поиска.

        Поддерживает два формата:
        - Новый (RowMetadata): {row, source, score, content, ...}
        - Старый (legacy): {metadata, score, ...}

        ARGS:
        - results: Сырые результаты vector_search.search

        RETURNS:
        - List[Dict]: Форматированные результаты с описанием
        """
        formatted = []

        for item in results:
            score = item.get("score", 0.0)
            source = item.get("source", "")
            row = item.get("row", {})
            content = item.get("content", "")
            search_text = item.get("search_text", content)

            if row:
                formatted_item = self._format_from_row(row, source, score, search_text)
            else:
                metadata = item.get("metadata", {})
                formatted_item = self._format_from_metadata(metadata, score)

            formatted.append(formatted_item)

        return formatted

    def _format_from_row(
        self,
        row: Dict[str, Any],
        source: str,
        score: float,
        search_text: str
    ) -> Dict[str, Any]:
        """Форматирование из нового формата RowMetadata."""
        formatted = {
            "type": source,
            "score": round(score, 3),
            "source": source,
            "row": row,
            "matched_text": search_text,
        }

        if source == "violations":
            formatted.update({
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
            })
        elif source == "audits":
            formatted.update({
                "audit_id": row.get("id"),
                "title": row.get("title", ""),
                "audit_type": row.get("audit_type", ""),
                "status": row.get("status", ""),
                "auditee_entity": row.get("auditee_entity", ""),
                "planned_date": row.get("planned_date"),
                "actual_date": row.get("actual_date"),
            })
        elif source == "books":
            formatted.update({
                "book_id": row.get("id"),
                "title": row.get("title", ""),
                "author": row.get("author", ""),
            })

        return formatted

    def _format_from_metadata(
        self,
        metadata: Dict[str, Any],
        score: float
    ) -> Dict[str, Any]:
        """Форматирование из старого формата (legacy)."""
        if "violation_id" in metadata:
            return {
                "type": "violation",
                "score": round(score, 3),
                "violation_id": metadata.get("violation_id"),
                "violation_code": metadata.get("violation_code", ""),
                "description": metadata.get("description", ""),
                "severity": metadata.get("severity", ""),
                "status": metadata.get("status", ""),
                "responsible": metadata.get("responsible", ""),
                "matched_text": metadata.get("search_text", ""),
            }
        elif "audit_id" in metadata:
            return {
                "type": "audit",
                "score": round(score, 3),
                "audit_id": metadata.get("audit_id"),
                "title": metadata.get("title", ""),
                "audit_type": metadata.get("audit_type", ""),
                "status": metadata.get("status", ""),
                "matched_text": metadata.get("search_text", ""),
            }
        else:
            return {
                "type": "unknown",
                "score": round(score, 3),
                "metadata": metadata,
                "matched_text": metadata.get("search_text", ""),
            }

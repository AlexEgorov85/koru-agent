import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from core.models.data.execution import ExecutionStatus
from core.agent.components.action_executor import ExecutionContext
from core.components.skills.handlers.base_handler import SkillHandler


class VectorSearchHandler(SkillHandler):
    """
    Обработчик семантического поиска по текстам актов аудиторской проверки.

    RESPONSIBILITIES:
    - Семантический поиск по full_text актов (audit_reports)
    - Семантический поиск по item_content пунктов акта (report_items)
    - Поиск через vector_books.search с source="audits"
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
        top_k = getattr(params, 'top_k', 10)
        min_score = getattr(params, 'min_score', 0.5)

        await self.log_info(f"Запуск векторного поиска: '{query[:80]}...' (source={source}, top_k={top_k})")

        # Выполняем векторный поиск через vector_books_tool
        results = await self._vector_search(query, source, top_k, min_score)

        # Форматируем результаты
        formatted_results = await self._format_results(results)

        total_time = time.time() - start_time
        result_data = {
            "results": formatted_results,
            "total_found": len(formatted_results),
            "query": query,
            "source": source,
            "execution_time": total_time,
            "warning": "Результатов не найдено" if not formatted_results else None
        }

        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="vector_search",
            rows_returned=len(formatted_results)
        )

        output_schema = self.get_output_schema()
        if output_schema:
            return output_schema.model_validate(result_data)

        return result_data

    async def _vector_search(
        self,
        query: str,
        source: str,
        top_k: int,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """
        Выполнение векторного поиска через vector_books_tool.

        ARGS:
        - query: Текст запроса
        - source: Источник FAISS индекса (audits, violations)
        - top_k: Количество результатов
        - min_score: Минимальный порог схожести

        RETURNS:
        - List[Dict]: Результаты поиска
        """
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="vector_books.search",
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

        await self.log_warning(f"Векторный поиск не вернул результатов: {result.error if hasattr(result, 'error') else 'unknown error'}")
        return []

    async def _format_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Форматирование результатов векторного поиска.

        Преобразует сырые метаданные FAISS в читаемый формат с контекстом.

        ARGS:
        - results: Сырые результаты vector_books.search

        RETURNS:
        - List[Dict]: Форматированные результаты с описанием
        """
        formatted = []

        for item in results:
            metadata = item.get("metadata", {})
            score = item.get("score", 0.0)

            # Определяем тип результата по полям метаданных
            if "audit_id" in metadata and "violation_id" in metadata:
                # Нарушение (violations индекс)
                formatted_item = {
                    "type": "violation",
                    "score": round(score, 3),
                    "audit_id": metadata.get("audit_id"),
                    "audit_title": metadata.get("audit_title", ""),
                    "violation_id": metadata.get("violation_id"),
                    "violation_code": metadata.get("violation_code", ""),
                    "description": metadata.get("description", ""),
                    "severity": metadata.get("severity", ""),
                    "status": metadata.get("status", ""),
                    "responsible": metadata.get("responsible", ""),
                    "matched_text": metadata.get("search_text", "")[:300],
                }
            elif "audit_id" in metadata:
                # Аудиторская проверка (audits индекс)
                formatted_item = {
                    "type": "audit",
                    "score": round(score, 3),
                    "audit_id": metadata.get("audit_id"),
                    "title": metadata.get("title", ""),
                    "audit_type": metadata.get("audit_type", ""),
                    "status": metadata.get("status", ""),
                    "auditee_entity": metadata.get("auditee_entity", ""),
                    "matched_text": metadata.get("search_text", "")[:300],
                }
            else:
                # Неизвестный тип — возвращаем как есть
                formatted_item = {
                    "type": "unknown",
                    "score": round(score, 3),
                    "metadata": metadata,
                    "matched_text": metadata.get("search_text", metadata.get("content", ""))[:300],
                }

            formatted.append(formatted_item)

        return formatted

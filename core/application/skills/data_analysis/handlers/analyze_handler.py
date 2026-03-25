import time
from typing import Dict, Any
from pydantic import BaseModel

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.application.skills.handlers.base_handler import BaseSkillHandler


class AnalyzeStepDataHandler(BaseSkillHandler):
    """Обработчик анализа данных шага."""

    capability_name = "data_analysis.analyze_step_data"

    async def execute(self, params: Dict[str, Any]) -> ExecutionResult:
        start_time = time.time()

        query, data_key, aggregation = self._extract_params(params)

        data_result = await self.executor.execute_action(
            action_name="context.get_step_data",
            parameters={"data_key": data_key},
            context=None
        )

        if data_result.status != ExecutionStatus.COMPLETED:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось получить данные: {data_result.error}"
            )

        raw_data = data_result.data
        if hasattr(raw_data, 'model_dump'):
            raw_data = raw_data.model_dump()
        elif hasattr(raw_data, 'data'):
            raw_data = raw_data.data

        analyzed = await self._perform_analysis(raw_data, aggregation)

        execution_time = (time.time() - start_time) * 1000

        result_data = {
            "analysis": analyzed,
            "query": query,
            "aggregation": aggregation,
            "execution_time_ms": execution_time
        }

        await self.log_info(f"Анализ завершён за {execution_time:.2f}мс")

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data=result_data,
            metadata={"execution_time_ms": execution_time}
        )

    def _extract_params(self, params: Dict[str, Any]) -> tuple:
        if isinstance(params, BaseModel):
            query = getattr(params, 'query', '')
            data_key = getattr(params, 'data_key', 'step_data')
            aggregation = getattr(params, 'aggregation', 'summary')
        else:
            query = params.get('query', '')
            data_key = params.get('data_key', 'step_data')
            aggregation = params.get('aggregation', 'summary')
        return query, data_key, aggregation

    async def _perform_analysis(self, data: Any, aggregation: str) -> Dict[str, Any]:
        """Выполнение анализа данных."""
        if aggregation == "summary":
            return self._summarize(data)
        elif aggregation == "statistical":
            return self._statistical_analysis(data)
        elif aggregation == "generative":
            return await self._generative_analysis(data)
        return self._summarize(data)

    def _summarize(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, dict):
            return {"summary": f"Объект с {len(data)} ключами", "keys": list(data.keys())}
        elif isinstance(data, list):
            return {"summary": f"Список из {len(data)} элементов", "count": len(data)}
        return {"summary": str(data)[:200]}

    def _statistical_analysis(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, list) and data and isinstance(data[0], dict):
            numeric_fields = {}
            for item in data[:10]:
                for k, v in item.items():
                    if isinstance(v, (int, float)):
                        if k not in numeric_fields:
                            numeric_fields[k] = []
                        numeric_fields[k].append(v)

            stats = {}
            for field, values in numeric_fields.items():
                if values:
                    stats[field] = {
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "count": len(values)
                    }
            return {"statistics": stats}
        return {"statistics": {}}

    async def _generative_analysis(self, data: Any) -> Dict[str, Any]:
        prompt = f"Проанализируй данные и дай краткое резюме: {str(data)[:500]}"
        result = await self.executor.execute_action(
            action_name="llm.generate",
            parameters={"prompt": prompt, "temperature": 0.3},
            context=None
        )
        if result.status == ExecutionStatus.COMPLETED:
            return {"summary": result.data.get("text", "") if hasattr(result.data, 'get') else str(result.data)}
        return {"summary": "Анализ недоступен"}

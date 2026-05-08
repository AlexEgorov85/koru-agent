"""
PythonStrategy — локальные вычисления без LLM.

ПОДДЕРЖИВАЕМЫЕ ОПЕРАЦИИ:
- Сумма по полю (sum)
- Среднее по полю (average/mean)
- Количество записей (count)
- Минимум/максимум (min/max)
"""
from typing import Any, Dict, List

from core.components.skills.data_analysis.base_strategy import AbstractStrategy, AnalysisInput, AnalysisResult


class PythonStrategy(AbstractStrategy):
    """Локальный анализ данных без LLM (только Python)."""

    name = "python"

    def can_handle(self, data: List[Dict], question: str) -> bool:
        if not data or not isinstance(data, list) or not isinstance(data[0], dict):
            return False
        has_numeric = any(isinstance(v, (int, float)) for item in data[:10] for v in item.values())
        calc_keywords = [
            "сумм", "средн", "количеств", "сколько", "миним", "максим",
            "count", "sum", "avg", "min", "max",
        ]
        is_calc = any(kw in question.lower() for kw in calc_keywords)
        return has_numeric and is_calc

    async def execute(self, input_data: AnalysisInput) -> AnalysisResult:
        data = input_data.data
        question_lower = input_data.question.lower()
        operations: List[str] = []
        results: Dict[str, Any] = {}

        numeric_fields = [
            k for k, v in data[0].items() if isinstance(v, (int, float))
        ]

        if any(kw in question_lower for kw in ["количеств", "сколько", "запис", "count"]):
            results["count"] = len(data)
            operations.append("count")

        for field in numeric_fields:
            if any(kw in question_lower for kw in ["сумм", "sum"]):
                total = sum(item.get(field, 0) or 0 for item in data)
                results[f"sum_{field}"] = total
                operations.append(f"sum:{field}")

            if any(kw in question_lower for kw in ["средн", "average", "avg", "среднее"]):
                total = sum(item.get(field, 0) or 0 for item in data)
                avg = total / len(data) if data else 0
                results[f"avg_{field}"] = round(avg, 2)
                operations.append(f"avg:{field}")

            if any(kw in question_lower for kw in ["мин", "min"]):
                values = [item.get(field) for item in data if item.get(field) is not None]
                if values:
                    results[f"min_{field}"] = min(values)
                    operations.append(f"min:{field}")

            if any(kw in question_lower for kw in ["макс", "max"]):
                values = [item.get(field) for item in data if item.get(field) is not None]
                if values:
                    results[f"max_{field}"] = max(values)
                    operations.append(f"max:{field}")

        if not results:
            results["count"] = len(data)
            operations.append("info")

        answer_parts = [f"Результат анализа данных (python mode):"]
        for key, value in results.items():
            answer_parts.append(f"- {key}: {value}")
        answer = "\n".join(answer_parts)

        confidence = 0.95 if any(o != "info" for o in operations) else 0.3

        return AnalysisResult(
            answer=answer,
            confidence=confidence,
            operations=operations,
            metadata={
                "mode_used": "python",
                "rows_processed": len(data),
                "fields": list(data[0].keys()) if data and isinstance(data[0], dict) else [],
            },
        )

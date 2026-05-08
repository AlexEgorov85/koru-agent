"""
LLMStrategy — прямой запрос к LLM без разбиения на чанки.

ИСПОЛЬЗУЕТ:
- llm.generate_structured с выходным контрактом
- Для небольших данных, которые помещаются в контекстное окно
"""
from typing import Any, Dict, List

from core.components.skills.data_analysis.base_strategy import AbstractStrategy, AnalysisInput, AnalysisResult
from core.components.skills.data_analysis.prompts import render_prompt, format_data_as_json, fits_in_context


class LLMStrategy(AbstractStrategy):
    """Прямой запрос к LLM без разбиения на чанки (для небольших данных)."""

    name = "llm"

    def can_handle(self, data: List[Dict], question: str) -> bool:
        context_window = getattr(self._skill, '_context_window', 8192)
        max_new = getattr(self._skill, '_max_new_tokens', 2000)
        return fits_in_context(data, question, context_window, max_new)

    async def execute(self, input_data: AnalysisInput) -> AnalysisResult:
        formatted = format_data_as_json(input_data.data)

        system_prompt = self._skill.get_prompt("data_analysis.analyze_step_data.system")
        user_prompt = self._skill.get_prompt("data_analysis.analyze_step_data.user")

        if not system_prompt or not user_prompt:
            return AnalysisResult(
                answer="", confidence=0.0, operations=[],
                metadata={"mode_used": "llm"}, error="Промпты не загружены",
            )

        user = render_prompt(user_prompt.content or "", {
            "question": input_data.question,
            "content": formatted,
        })

        prompt = f"{system_prompt.content}\n\n{user}"

        executor = self._get_executor(input_data.execution_context)

        output_contract = self._skill.get_output_contract("data_analysis.analyze_step_data")

        try:
            result = await executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.2,
                    "structured_output": {
                        "output_model": "data_analysis.analyze_step_data.output",
                        "schema_def": output_contract,
                        "strict_mode": True,
                        "max_retries": 1,
                    },
                },
                context=input_data.execution_context,
            )
        except Exception as e:
            return AnalysisResult(
                answer="", confidence=0.0, operations=["llm"],
                metadata={"mode_used": "llm"}, error=str(e),
            )

        from core.models.data.execution import ExecutionStatus
        if result.status != ExecutionStatus.COMPLETED or not result.data:
            return AnalysisResult(
                answer="", confidence=0.0, operations=["llm"],
                metadata={"mode_used": "llm"},
                error=getattr(result, 'error', 'LLM generate_structured failed'),
            )

        data = result.data
        if hasattr(data, 'model_dump'):
            data = data.model_dump()
        elif not isinstance(data, dict):
            data = {}
        metadata_value = data.get("metadata", {})
        if not isinstance(metadata_value, dict):
            metadata_value = {}
        return AnalysisResult(
            answer=data.get("answer", ""),
            confidence=data.get("confidence", 0.5),
            operations=["llm"],
            metadata={
                "mode_used": "llm",
                **metadata_value,
            },
        )



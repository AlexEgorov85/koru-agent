from typing import Dict, Any, List
from pydantic import BaseModel

from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import BaseSkillHandler


class CreatePlanHandler(BaseSkillHandler):
    """Обработчик создания первичного плана."""

    capability_name = "planning.create_plan"

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Создание первичного плана.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        goal = params.goal if hasattr(params, 'goal') else ''
        
        prompt_obj = self.get_prompt()
        rendered_prompt = prompt_obj if prompt_obj else ""

        output_schema = self.get_output_schema()

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": rendered_prompt,
                "structured_output": {
                    "output_model": "planning.create_plan.output",
                    "schema_def": output_schema,
                    "max_retries": 3,
                    "strict_mode": True
                },
                "temperature": 0.1
            },
            context=execution_context
        )

        if not llm_result.status == ExecutionStatus.COMPLETED:
            error_type = llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown"
            attempts = llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
            raise RuntimeError(f"Ошибка генерации плана: {llm_result.error}")

        llm_result_data = llm_result.result
        if hasattr(llm_result_data, 'parsed_content'):
            plan_data = llm_result_data.parsed_content
        elif isinstance(llm_result_data, dict):
            plan_data = llm_result_data.get("parsed_content", {})
        else:
            plan_data = llm_result_data if llm_result_data else {}

        await self.log_info(f"Plan создан с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1)})")

        save_result = await self.executor.execute_action(
            action_name="context.record_plan",
            parameters={"plan_data": plan_data, "plan_type": "initial"},
            context=execution_context
        )

        if not save_result.status == ExecutionStatus.COMPLETED:
            raise RuntimeError(f"Не удалось сохранить план: {save_result.error}")

        await self.publish_event("planning.plan_created", {
            "plan_id": plan_data.get("plan_id", ""),
            "steps_count": len(plan_data.get("plan", [])),
            "goal": goal
        })

        output_schema = self.get_output_schema()
        if output_schema:
            return output_schema.model_validate(plan_data)
        
        return plan_data

    def _format_capabilities(self, capabilities: List[Any]) -> str:
        return "\n".join([f"- {cap.name}: {cap.description}" for cap in capabilities])

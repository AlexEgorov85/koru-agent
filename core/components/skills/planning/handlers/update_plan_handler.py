from typing import Dict, Any
from pydantic import BaseModel

from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import SkillHandler


class UpdatePlanHandler(SkillHandler):
    """Обработчик обновления плана."""

    capability_name = "planning.update_plan"

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Обновление плана.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        plan_id = params.plan_id if hasattr(params, 'plan_id') else ''
        updates = params.updates if hasattr(params, 'updates') else {}
        reason = params.reason if hasattr(params, 'reason') else ''

        if plan_id:
            plan_result = await self.executor.execute_action(
                action_name="context.get_context_item",
                parameters={"item_id": plan_id},
                context=execution_context
            )
            if not plan_result.status == ExecutionStatus.COMPLETED:
                raise RuntimeError(f"План с ID {plan_id} не найден")
            current_plan = plan_result.data.get("content", {}) if plan_result.data else {}
        else:
            plan_result = await self.executor.execute_action(
                action_name="context.get_current_plan",
                parameters={},
                context=execution_context
            )
            if not plan_result.status == ExecutionStatus.COMPLETED:
                raise RuntimeError("Нет текущего плана для обновления")
            current_plan = plan_result.data

        prompt_obj = self.get_prompt()
        rendered_prompt = prompt_obj if prompt_obj else ""

        output_schema = self.get_output_schema()

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": rendered_prompt,
                "structured_output": {
                    "output_model": "planning.update_plan.output",
                    "schema_def": output_schema,
                    "max_retries": 3,
                    "strict_mode": True
                },
                "temperature": 0.1
            },
            context=execution_context
        )

        if not llm_result.status == ExecutionStatus.COMPLETED:
            raise RuntimeError(f"Ошибка обновления плана: {llm_result.error}")

        llm_data = llm_result.result
        updated_plan = llm_data.parsed_content if hasattr(llm_data, 'parsed_content') else llm_data.get("parsed_content", {}) if isinstance(llm_data, dict) else llm_data

        save_result = await self.executor.execute_action(
            action_name="context.record_plan",
            parameters={"plan_data": updated_plan, "plan_type": "update"},
            context=execution_context
        )

        if not save_result.status == ExecutionStatus.COMPLETED:
            raise RuntimeError("Не удалось сохранить план")

        result_data = {"plan": updated_plan, "update_applied": True}
        
        output_schema = self.get_output_schema()
        if output_schema:
            return output_schema.model_validate(result_data)
        
        return result_data

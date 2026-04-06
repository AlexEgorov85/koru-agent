from typing import Dict, Any
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.services.skills.handlers.base_handler import BaseSkillHandler


class UpdatePlanHandler(BaseSkillHandler):
    """Обработчик обновления плана."""

    capability_name = "planning.update_plan"

    async def execute(self, params: Dict[str, Any], execution_context: Any = None) -> ExecutionResult:
        try:
            plan_id = params.get("plan_id", "")
            updates = params.get("updates", {})
            reason = params.get("reason", "")

            if plan_id:
                plan_result = await self.executor.execute_action(
                    action_name="context.get_context_item",
                    parameters={"item_id": plan_id},
                    context=execution_context
                )
                if not plan_result.status == ExecutionStatus.COMPLETED:
                    return ExecutionResult(status=ExecutionStatus.FAILED, error=f"План с ID {plan_id} не найден")
                current_plan = plan_result.data.get("content", {}) if plan_result.data else {}
            else:
                plan_result = await self.executor.execute_action(
                    action_name="context.get_current_plan",
                    parameters={},
                    context=execution_context
                )
                if not plan_result.status == ExecutionStatus.COMPLETED:
                    return ExecutionResult(status=ExecutionStatus.FAILED, error="Нет текущего плана для обновления")
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
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка обновления плана: {llm_result.error}"
                )

            llm_data = llm_result.result
            updated_plan = llm_data.parsed_content if hasattr(llm_data, 'parsed_content') else llm_data.get("parsed_content", {}) if isinstance(llm_data, dict) else llm_data

            save_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={"plan_data": updated_plan, "plan_type": "update"},
                context=execution_context
            )

            if not save_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(status=ExecutionStatus.FAILED, error="Не удалось сохранить план")

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={"plan": updated_plan, "update_applied": True},
                metadata={"plan_id": updated_plan.get("plan_id", plan_id)}
            )

        except Exception as e:
            await self.log_error(f"Ошибка обновления плана: {str(e)}")
            return ExecutionResult(status=ExecutionStatus.FAILED, error=f"Ошибка: {str(e)}")

from typing import Dict, Any, List
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.application.agent.components.action_executor import ExecutionContext
from core.application.skills.handlers.base_handler import BaseSkillHandler


class CreatePlanHandler(BaseSkillHandler):
    """Обработчик создания первичного плана."""

    capability_name = "planning.create_plan"

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> ExecutionResult:
        try:
            input_contract = self.get_input_schema()
            prompt_with_contract = self.get_prompt_with_contract()

            rendered_prompt = prompt_with_contract.format(
                goal=params.get("goal", ""),
                capabilities_list=self._format_capabilities(context.available_capabilities),
                context=params.get("context", ""),
                max_steps=params.get("max_steps", 10)
            )

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
                context=context
            )

            if not llm_result.status == ExecutionStatus.COMPLETED:
                error_type = llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown"
                attempts = llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка генерации плана: {llm_result.error}",
                    metadata={"error_type": error_type, "attempts": attempts}
                )

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
                context=context
            )

            if not save_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Не удалось сохранить план: {save_result.error}"
                )

            await self.publish_event("planning.plan_created", {
                "plan_id": plan_data.get("plan_id", ""),
                "steps_count": len(plan_data.get("plan", [])),
                "goal": params.get("goal", "")
            })

            parsing_attempts = llm_result.metadata.get("parsing_attempts", 1) if isinstance(llm_result.metadata, dict) else 1
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=plan_data,
                metadata={
                    "steps_count": len(plan_data.get("plan", [])),
                    "plan_id": plan_data.get("plan_id", ""),
                    "parsing_attempts": parsing_attempts
                }
            )

        except Exception as e:
            await self.log_error(f"Ошибка создания плана: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка создания плана: {str(e)}"
            )

    def _format_capabilities(self, capabilities: List[Any]) -> str:
        return "\n".join([f"- {cap.name}: {cap.description}" for cap in capabilities])

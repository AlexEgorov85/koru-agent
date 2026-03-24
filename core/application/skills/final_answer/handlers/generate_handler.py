from typing import Dict, Any
from datetime import date, datetime
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.application.agent.components.action_executor import ExecutionContext
from core.session_context.base_session_context import BaseSessionContext
from .base_handler import BaseFinalAnswerHandler


class GenerateFinalAnswerHandler(BaseFinalAnswerHandler):
    """Обработчик генерации финального ответа."""

    capability_name = "final_answer.generate"

    async def execute(self, context: BaseSessionContext, params: Dict[str, Any], exec_context: Any) -> ExecutionResult:
        try:
            goal = context.get_goal() or "Не указана цель"

            include_steps = self._extract_param(params, 'include_steps', True)
            include_evidence = self._extract_param(params, 'include_evidence', True)
            format_type = self._extract_param(params, 'format_type', 'detailed')
            confidence_threshold = self._extract_param(params, 'confidence_threshold', 0.7)
            max_sources = self._extract_param(params, 'max_sources', 10)

            observations, thoughts, actions = await self._collect_context_data(exec_context)

            rendered_prompt = self._build_prompt(
                goal=goal,
                observations=observations,
                thoughts=thoughts,
                actions=actions,
                include_steps=include_steps,
                include_evidence=include_evidence,
                format_type=format_type,
                confidence_threshold=confidence_threshold,
                max_sources=max_sources
            )

            llm_result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={"prompt": rendered_prompt, "temperature": 0.3},
                context=exec_context
            )

            if llm_result.status != ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка генерации: {llm_result.error}"
                )

            generated_answer = llm_result.data.get("text", "") if hasattr(llm_result.data, 'get') else str(llm_result.data)

            result_data = {
                "final_answer": generated_answer,
                "goal": goal,
                "format": format_type,
                "sources_count": len(actions)
            }

            await self.log_info(f"Финальный ответ сгенерирован ({len(generated_answer)} символов)")

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=result_data,
                metadata={"format": format_type, "sources": len(actions)}
            )

        except Exception as e:
            await self.log_error(f"Ошибка генерации финального ответа: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка генерации: {str(e)[:100]}"
            )

    def _extract_param(self, params: Dict[str, Any], key: str, default: Any) -> Any:
        from pydantic import BaseModel
        if isinstance(params, BaseModel):
            return getattr(params, key, default)
        return params.get(key, default) if isinstance(params, dict) else default

    async def _collect_context_data(self, exec_context: ExecutionContext) -> tuple:
        """Сбор данных контекста через executor."""
        observations = []
        thoughts = []
        actions = []

        all_items_result = await self.executor.execute_action(
            action_name="context.get_all_items",
            parameters={},
            context=exec_context
        )

        if all_items_result.status == ExecutionStatus.COMPLETED and all_items_result.result:
            all_items = all_items_result.result.get("items", {})

            for item_id, item in all_items.items():
                if hasattr(item, 'model_dump'):
                    item = item.model_dump()
                item_type = item.get("type", "unknown") if isinstance(item, dict) else "unknown"

                if item_type == "observation":
                    content = item.get("content", item.get("text", "")) if isinstance(item, dict) else str(item)
                    observations.append(content)
                elif item_type == "thought":
                    content = item.get("content", item.get("text", "")) if isinstance(item, dict) else str(item)
                    thoughts.append(content)
                elif item_type == "action_result":
                    content = item.get("content", item.get("result", "")) if isinstance(item, dict) else str(item)
                    actions.append(content)

        return observations, thoughts, actions

    def _build_prompt(
        self,
        goal: str,
        observations: list,
        thoughts: list,
        actions: list,
        include_steps: bool,
        include_evidence: bool,
        format_type: str,
        confidence_threshold: float,
        max_sources: int
    ) -> str:
        """Построение промпта для генерации финального ответа."""
        base_prompt = self.get_prompt()
        if base_prompt:
            prompt_text = base_prompt.content if hasattr(base_prompt, 'content') else str(base_prompt)
        else:
            prompt_text = "Создай финальный ответ на основе предоставленных данных."

        prompt_parts = [
            f"Цель: {goal}",
            "",
            " observations:",
            "\n".join([f"- {o}" for o in observations[:20]]),
            "",
            " thoughts:",
            "\n".join([f"- {t}" for t in thoughts[:20]]),
            "",
            " actions:",
            "\n".join([f"- {a}" for a in actions[:max_sources]])
        ]

        return f"{prompt_text}\n\n" + "\n".join(prompt_parts)

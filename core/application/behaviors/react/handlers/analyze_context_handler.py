from typing import Dict, Any, List
from core.models.data.capability import Capability
from core.application.agent.strategies.react.utils import analyze_context
from .base_handler import BaseReActHandler


class AnalyzeContextHandler(BaseReActHandler):
    """Обработчик анализа контекста в ReAct паттерне."""

    async def execute(
        self,
        session_context: Any,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Анализ контекста сессии.

        ARGS:
        - session_context: контекст сессии
        - available_capabilities: доступные capabilities
        - context_analysis: начальный анализ

        RETURNS:
        - Dict с результатами анализа
        """
        await self.log_debug(f"[ReAct] analyze_context: received capabilities count={len(available_capabilities)}")

        if not available_capabilities and self.pattern.application_context:
            available_capabilities = await self.pattern.application_context.get_all_capabilities()
            await self.log_debug(f"[ReAct] analyze_context: received {len(available_capabilities)} capability from context")

        # Регистрируем схемы через CapabilityResolverService
        self.pattern.capability_resolver.register_capability_schemas(
            available_capabilities=available_capabilities,
            schema_validator=self.schema_validator,
            input_contracts=getattr(self.pattern, 'input_contracts', {}),
            data_repository=getattr(self.pattern.application_context, 'data_repository', None) if self.pattern.application_context else None
        )

        # Выполняем анализ контекста сессии
        analysis_obj = analyze_context(session_context)

        analysis = {
            "goal": analysis_obj.goal,
            "last_steps": analysis_obj.last_steps,
            "progress": analysis_obj.progress,
            "current_step": analysis_obj.current_step,
            "execution_time_seconds": analysis_obj.execution_time_seconds,
            "last_activity": analysis_obj.last_activity,
            "no_progress_steps": analysis_obj.no_progress_steps,
            "consecutive_errors": analysis_obj.consecutive_errors,
            "summary": analysis_obj.summary,
        }

        # Фильтрация capability
        filtered_caps = self.pattern.capability_resolver.filter_capabilities(available_capabilities, self.pattern.pattern_id)
        filtered_caps = self.pattern.capability_resolver.exclude_capability(filtered_caps, "final_answer.generate")

        analysis["available_capabilities"] = filtered_caps

        await self.log_debug(f"[ReAct] analyze_context: after filtering count={len(analysis['available_capabilities'])}")

        return analysis

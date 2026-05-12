"""ReActPattern - реактивная стратегия поведения.

АРХИТЕКТУРА:
1. decide() - точка входа
2. analyze_context() - анализ контекста
3. generate_decision() - генерация решения через LLM
4. _make_decision() - принятие решения на основе результата LLM
"""

from typing import Any, Dict, List, Optional

from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.agent.behaviors.base import Decision, DecisionType
from core.agent.behaviors.react.utils import analyze_context
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.agent.behaviors.services import FallbackStrategyService
from core.session_context.session_context import SessionContext


class ReActPattern(BaseBehaviorPattern):
    """ReAct паттерн - реактивное принятие решений через LLM."""

    DEPENDENCIES = ["prompt_service", "contract_service"]

    def __init__(
        self,
        component_name: str,
        component_config=None,
        application_context=None,
        executor=None,
    ):
        super().__init__(
            component_name, component_config, application_context, executor
        )
        self.error_count = 0
        self.fallback_strategy = FallbackStrategyService()

    # =========================================================================
    # ПУБЛИЧНЫЙ ИНТЕРФЕЙС
    # =========================================================================

    async def decide(
        self, session_context: SessionContext, available_capabilities: List[Capability]
    ) -> Decision:
        """Единственное место принятия решений."""
        context = await self.analyze_context(session_context, available_capabilities)
        return await self.generate_decision(
            session_context, context, available_capabilities
        )

    async def analyze_context(
        self, session_context: SessionContext, available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Анализ контекста сессии."""
        if not available_capabilities and self.application_context:
            available_capabilities = (
                await self.application_context.get_all_capabilities()
            )

        analysis = analyze_context(session_context)

        agent_state = getattr(session_context, "agent_state", None)

        return {
            "goal": analysis.goal,
            "last_steps": analysis.last_steps,
            "progress": analysis.progress,
            "current_step": analysis.current_step,
            "execution_time_seconds": analysis.execution_time_seconds,
            "last_activity": analysis.last_activity,
            "no_progress_steps": analysis.no_progress_steps,
            "consecutive_errors": analysis.consecutive_errors,
            "reasoning_detail": analysis.reasoning_detail,
            "available_capabilities": available_capabilities,
            "state_errors": agent_state.errors[-3:] if agent_state else [],
            "empty_results_count": (
                agent_state.total_empty_results if agent_state else 0
            ),
            "repeated_actions_count": (
                agent_state.consecutive_repeated_actions if agent_state else 0
            ),
            "last_observation": agent_state.last_observation if agent_state else None,
        }

    async def generate_decision(
        self,
        session_context: SessionContext,
        context: Dict[str, Any],
        available_capabilities: List[Capability],
    ) -> Decision:
        """Генерация решения через LLM."""
        from core.models.types.llm_types import LLMRequest, StructuredOutputConfig

        # Логируем входные параметры
        self._log_debug(
            f"📥 [ReAct.decide] Входные параметры: "
            f"session_id={session_context.session_id}, "
            f"goal={session_context.goal}, "
            f"caps={len(available_capabilities)}",
            event_type=EventType.AGENT_DECISION,
        )

        # Берём промпт и контракт (загружены в initialize())
        system_prompt = self.get_prompt("behavior.react.think.system")
        user_prompt = self.get_prompt("behavior.react.think.user")
        output_contract = self.get_output_contract("behavior.react.think")

        # Извлекаем content из Prompt объекта
        system = system_prompt.content if system_prompt else ""
        user = user_prompt.content if user_prompt else ""

        # Логируем загруженные промпты
        self._log_debug(
            f"📋 [ReAct.decide] Промпты загружены: "
            f"system={len(system) if system else 0} симв., "
            f"user={len(user) if user else 0} симв.",
            event_type=EventType.LLM_CALL,
        )

        # Schema из контракта
        schema = None
        if output_contract:
            if hasattr(output_contract, "model_json_schema"):
                schema = output_contract.model_json_schema()
            elif hasattr(output_contract, "model_schema"):
                schema = output_contract.model_schema

        if schema is None:
            self.log.error(
                "❌ [ReAct] Не удалось загрузить схему контракта 'behavior.react.think'. LLM будет вызван без строгой схемы!",
                extra={"event_type": EventType.ERROR},
            )

        if not system or not user:
            return self._handle_error("prompts_not_loaded", available_capabilities)

        # Рендеринг промпта
        full_prompt = self.prompt_builder.build_reasoning_prompt(
            context_analysis=context,
            available_capabilities=available_capabilities,
            templates={"system": system, "user": user},
            session_context=session_context,
            pattern_id="react",
            application_context=self.application_context,
        )

        # Логируем метаданные запроса
        self._log_debug(
            f"[ReAct.decide] prompt loaded: system={len(system)} chars, user={len(full_prompt)} chars, schema_keys={list(schema.keys()) if schema else []}",
            event_type=EventType.LLM_CALL,
        )

        # Получаем оркестратор
        orchestrator = getattr(self.application_context, "llm_orchestrator", None)
        if not orchestrator:
            return self.fallback_strategy.create_reasoning_fallback(
                context, available_capabilities, "orchestrator_not_available"
            )

        # Получаем провайдер LLM
        provider = None
        if self.application_context and hasattr(self.application_context, "infrastructure_context"):
            infra = self.application_context.infrastructure_context
            if hasattr(infra, "resource_registry"):
                resource = infra.resource_registry.get_resource("default_llm")
                if resource:
                    provider = resource.instance

        try:
            self._log_info(
                f"🔮 LLM вызов (temperature=0.3, max_tokens=2000, structured_output)",
                event_type=EventType.LLM_CALL,
            )

            # Извлекаем данные для трассировки
            step_number = None
            if (
                hasattr(session_context, "step_context")
                and session_context.step_context
            ):
                step_number = session_context.step_context.get_current_step_number()

            # Создаём LLMRequest
            llm_request = LLMRequest(
                prompt=full_prompt,
                system_prompt=system,
                temperature=0.3,
                max_tokens=2000,
                structured_output=StructuredOutputConfig(
                    output_model="ReasoningResult",
                    schema_def=schema,
                    max_retries=3,
                    strict_mode=False,
                ),
            )

            # Вызов LLM через оркестратор
            result = await orchestrator.execute_structured(
                request=llm_request,
                provider=provider,
                session_id=session_context.session_id,
                agent_id=getattr(session_context, "agent_id", None),
                step_number=step_number,
                goal=session_context.goal,
                phase="think",
                use_native_structured_output=True,
            )

        except Exception as e:
            self._log_error(
                f"❌ Исключение при LLM вызове: {type(e).__name__}: {e}",
                event_type=EventType.LLM_ERROR,
                exc_info=True,
            )
            return self.fallback_strategy.create_error(
                f"llm_exception:{type(e).__name__}:{str(e)}", available_capabilities
            )

        # Проверка результата
        if not result or not hasattr(result, "parsed_content") or result.parsed_content is None:
            return self.fallback_strategy.create_error(
                "llm_no_valid_response", available_capabilities
            )

        reasoning_result = result.parsed_content

        self._log_info(
            f"✅ LLM ответ получен (thought: {getattr(reasoning_result, 'thought', '')})",
            event_type=EventType.LLM_RESPONSE,
        )

        decision = await self._make_decision(reasoning_result, available_capabilities)
        self.error_count = 0

        # Логируем финальное решение
        self._log_info(
            f"🎯 [ReAct.decide] Финальное решение: "
            f"type={decision.type.value}, "
            f"action={decision.action or 'N/A'}, "
            f"params={list((decision.parameters or {}).keys())}, "
            f"reasoning={decision.reasoning_detail or 'N/A'}",
            event_type=EventType.AGENT_DECISION,
        )

        return decision

    ANALYSIS_FIELDS = [
        "analysis_question_decomposition", "analysis_subquestions_tracking",
        "analysis_progress", "analysis_deficit", "analysis_data_quality",
        "analysis_empty_error_strategy", "analysis_tool_choice",
        "analysis_parameter_sources", "analysis_parameter_validation",
        "analysis_limit_strategy", "analysis_alternative_paths",
        "analysis_stop", "analysis_final",
    ]

    def _build_reasoning_detail(self, reasoning_result: Any) -> Dict[str, Any]:
        """Собрать reasoning_detail из individual analysis_* полей LLM."""
        detail = {}
        if isinstance(reasoning_result, dict):
            for field in self.ANALYSIS_FIELDS:
                val = reasoning_result.get(field)
                if val:
                    detail[field] = val
        else:
            for field in self.ANALYSIS_FIELDS:
                val = getattr(reasoning_result, field, None)
                if val:
                    detail[field] = val
        return detail

    async def _make_decision(
        self,
        reasoning_result: Any,
        available_capabilities: List[Capability],
    ) -> Decision:
        """Преобразовать результат LLM в Decision."""
        if isinstance(reasoning_result, dict):
            stop_condition = reasoning_result.get("stop_condition", False)
            stop_reason = reasoning_result.get("stop_reason", None)
            decision = reasoning_result.get("decision", {})
            capability_name = decision.get("next_action") if isinstance(decision, dict) else None
            parameters = decision.get("parameters", {}) if isinstance(decision, dict) else {}
        else:
            stop_condition = getattr(reasoning_result, "stop_condition", False)
            stop_reason = getattr(reasoning_result, "stop_reason", None)
            decision = getattr(reasoning_result, "decision", None)
            if isinstance(decision, dict):
                capability_name = decision.get("next_action")
                parameters = decision.get("parameters", {})
            else:
                capability_name = getattr(decision, "next_action", None) if decision else None
                parameters = getattr(decision, "parameters", {}) if decision else {}

        if stop_condition:
            # Если stop_condition=true и next_action указывает на реальную capability — разрешаем
            if capability_name and self._find_capability(capability_name, available_capabilities):
                self._log_info(
                    f"⚠️ LLM запросил {capability_name} перед остановкой (stop_condition=true)",
                    event_type=EventType.INFO
                )
                return Decision(
                    type=DecisionType.ACT,
                    action=capability_name,
                    parameters=parameters,
                    reasoning_detail=self._build_reasoning_detail(reasoning_result) or None,
                    is_final=False,
                )
            # В любом другом случае (нет next_action, FINISH, мусор) — просто завершаем
            return self._handle_stop_condition(
                reasoning_detail=self._build_reasoning_detail(reasoning_result) or None
            )

        if not capability_name:
            return Decision(
                type=DecisionType.FAIL,
                error="LLM не вернул next_action",
                reasoning_detail={"analysis_final": "LLM не вернул next_action"}
            )

        # Поиск capability
        capability = self._find_capability(capability_name, available_capabilities)
        if not capability:
            return Decision(
                type=DecisionType.FAIL,
                error="no_available_capabilities",
                reasoning_detail={"analysis_final": "no_available_capabilities"}
            )

        return Decision(
            type=DecisionType.ACT,
            action=capability.name,
            parameters=parameters,
            reasoning_detail=self._build_reasoning_detail(reasoning_result) or None,
            is_final=capability.name == "final_answer.generate",
        )

    def _find_capability(
        self, name: str, available_capabilities: List[Capability]
    ) -> Optional[Capability]:
        """Поиск capability по имени с учётом префикса (skill.* → skill)."""
        for cap in available_capabilities:
            if cap.name == name:
                return cap
        if "." in name:
            prefix = name.split(".")[0]
            for cap in available_capabilities:
                if cap.name == prefix:
                    return cap
        for cap in available_capabilities:
            if "react" in [s.lower() for s in (cap.supported_strategies or [])]:
                return cap
        return None

    def _handle_stop_condition(
        self, reasoning_detail: Optional[Dict[str, Any]] = None
    ) -> Decision:
        """Обработать условие остановки — просто FINISH."""
        if reasoning_detail is None:
            reasoning_detail = {"analysis_final": "goal_achieved"}

        return Decision(
            type=DecisionType.FINISH,
            reasoning_detail=reasoning_detail,
            is_final=True,
        )

    def _handle_error(self, reason: str, capabilities: List[Capability]) -> Decision:
        """Обработать ошибку — возвращаем FAIL."""
        self.error_count += 1
        return self.fallback_strategy.create_error(reason, capabilities)

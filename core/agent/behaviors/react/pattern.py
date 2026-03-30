"""ReActPattern - реактивная стратегия поведения.

АРХИТЕКТУРА:
1. decide() - точка входа
2. analyze_context() - анализ контекста
3. generate_decision() - генерация решения через LLM
4. _make_decision() - принятие решения на основе результата LLM
"""

from typing import Any, Dict, List
from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.agent.behaviors.base import Decision, DecisionType
from core.agent.strategies.react.schema_validator import SchemaValidator
from core.agent.strategies.react.utils import analyze_context
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.models.types.llm_types import LLMRequest
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
        event_bus=None
    ):
        super().__init__(component_name, component_config, application_context, executor, event_bus)
        
        self.error_count = 0
        self.max_consecutive_errors = 3
        
        self.schema_validator = SchemaValidator()
        self.fallback_strategy = FallbackStrategyService()

    @property
    def llm_orchestrator(self):
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None
    
    @property
    def llm_provider(self):
        """Получить LLM провайдер из инфраструктурного контекста."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            infra = self.application_context.infrastructure_context
            if infra.resource_registry:
                resource = infra.resource_registry.get_resource("default_llm")
                if resource:
                    return resource.instance
        return None

    # =========================================================================
    # ПУБЛИЧНЫЙ ИНТЕРФЕЙС
    # =========================================================================
    
    async def decide(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Единственное место принятия решений."""
        context = await self.analyze_context(session_context, available_capabilities)
        return await self.generate_decision(session_context, context, available_capabilities)

    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Анализ контекста сессии."""
        if not available_capabilities and self.application_context:
            available_capabilities = await self.application_context.get_all_capabilities()
        
        analysis = analyze_context(session_context)
        
        return {
            "goal": analysis.goal,
            "last_steps": analysis.last_steps,
            "progress": analysis.progress,
            "current_step": analysis.current_step,
            "execution_time_seconds": analysis.execution_time_seconds,
            "last_activity": analysis.last_activity,
            "no_progress_steps": analysis.no_progress_steps,
            "consecutive_errors": analysis.consecutive_errors,
            "summary": analysis.summary,
            "available_capabilities": available_capabilities,
        }

    async def generate_decision(
        self,
        session_context: SessionContext,
        context: Dict[str, Any],
        available_capabilities: List[Capability]
    ) -> Decision:
        """Генерация решения через LLM."""
        try:
            from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
            
            # Берём промпт и контракт (загружены в initialize())
            system_prompt = self.get_prompt("behavior.react.think.system")
            user_prompt = self.get_prompt("behavior.react.think.user")
            output_contract = self.get_output_contract("behavior.react.think")
            
            # Извлекаем content из Prompt объекта
            system = system_prompt.content if system_prompt else ""
            user = user_prompt.content if user_prompt else ""

            # Debug logging через event_bus
            event_bus = self.application_context.infrastructure_context.event_bus
            await event_bus.publish(EventType.DEBUG, {
                "message": f"[DEBUG] system_prompt: {len(system)} chars, user_prompt: {len(user)} chars"
            })
            await event_bus.publish(EventType.DEBUG, {
                "message": f"[DEBUG] output_contract: {output_contract}"
            })
            
            # Schema из контракта (model_json_schema - метод класса, не экземпляра)
            schema = None
            if output_contract:
                if hasattr(output_contract, 'model_json_schema'):
                    schema = output_contract.model_json_schema()
                elif hasattr(output_contract, 'model_schema'):
                    schema = output_contract.model_schema
            
            if not system or not user:
                return self._handle_error("prompts_not_loaded", available_capabilities)
            
            # Рендеринг
            full_prompt = self.prompt_builder.build_reasoning_prompt(
                context_analysis=context,
                available_capabilities=available_capabilities,
                templates={"system": system, "user": user},
                schema_validator=self.schema_validator,
                session_context=session_context
            )
            
            # Вызов LLM
            orchestrator = self.llm_orchestrator
            if not orchestrator:
                return self.fallback_strategy.create_reasoning_fallback(
                    context, available_capabilities, "orchestrator_not_available"
                )
            
            llm_request = LLMRequest(
                prompt=full_prompt,
                system_prompt=system,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="ReasoningResult",
                    schema_def=schema,
                    max_retries=3,
                    strict_mode=False
                )
            )
            
            # Получаем провайдер из инфраструктурного контекста
            provider = self.llm_provider
            
            try:
                result = await orchestrator.execute_structured(
                    request=llm_request,
                    provider=provider,
                    session_id=session_context.session_id,
                    use_native_structured_output=False  # LlamaCpp не поддерживает нативный structured output
                )
            except Exception as e:
                await event_bus.publish(EventType.ERROR, {
                    "message": f"[DEBUG] LLM EXCEPTION: {type(e).__name__}: {e}"
                })
                return self.fallback_strategy.create_error(
                    f"llm_exception:{type(e).__name__}:{str(e)}", available_capabilities
                )
            
            if not result or not hasattr(result, 'parsed_content') or result.parsed_content is None:
                await event_bus.publish(EventType.WARNING, {
                    "message": f"[DEBUG] LLM FAILED - result: {result}"
                })
                return self.fallback_strategy.create_error(
                    "llm_call_failed", available_capabilities
                )
            
            reasoning_result = result.parsed_content
            
            # Сохраняем размышление
            thought = getattr(reasoning_result, "thought", "") or ""
            session_context.record_decision(decision_data="reasoning", reasoning=thought)
            
            # Принятие решения
            decision = await self._make_decision(reasoning_result, available_capabilities)
            
            self.error_count = 0
            return decision
            
        except Exception as e:
            return self._handle_error(str(e), available_capabilities)

    async def _make_decision(
        self,
        reasoning_result: Any,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Преобразовать результат LLM в Decision."""
        stop_condition = getattr(reasoning_result, "stop_condition", False)
        stop_reason = getattr(reasoning_result, "stop_reason", None)
        
        decision = getattr(reasoning_result, "decision", None)
        capability_name = getattr(decision, "next_action", None) if decision else None
        parameters = getattr(decision, "parameters", {}) if decision else {}
        reasoning = getattr(decision, "reasoning", "") if decision else ""
        
        if stop_condition:
            return self._handle_stop_condition(capability_name, parameters, stop_reason)
        
        if not capability_name:
            return Decision(type=DecisionType.FAIL, error="LLM не вернул next_action")
        
        capability = self._find_capability(available_capabilities, capability_name)
        
        if not capability:
            for cap in available_capabilities:
                if "react" in [s.lower() for s in (cap.supported_strategies or [])]:
                    capability = cap
                    capability_name = cap.name
                    break
            
            if not capability:
                return Decision(type=DecisionType.FAIL, error="no_available_capabilities")
        
        validated_params = self._validate_capability_parameters(capability, parameters, {})
        
        return Decision(
            type=DecisionType.ACT,
            action=capability_name,
            parameters=validated_params,
            reasoning=reasoning,
            is_final=capability_name == "final_answer.generate"
        )

    def _handle_stop_condition(
        self,
        capability_name: str,
        parameters: Dict[str, Any],
        stop_reason: str
    ) -> Decision:
        """Обработать условие остановки."""
        if capability_name and capability_name != "final_answer.generate":
            return Decision(
                type=DecisionType.ACT,
                action="final_answer.generate",
                parameters={"input": f"Цель достигнута: {stop_reason or 'goal_achieved'}"},
                reasoning="final_answer_on_stop",
                is_final=True
            )
        
        if capability_name == "final_answer.generate":
            return Decision(
                type=DecisionType.ACT,
                action="final_answer.generate",
                parameters=parameters,
                reasoning="final_answer_before_stop",
                is_final=True
            )
        
        return Decision(type=DecisionType.FAIL, error=stop_reason or "goal_achieved")

    def _handle_error(self, reason: str, capabilities: List[Capability]) -> Decision:
        """Обработать ошибку."""
        self.error_count += 1
        if self.error_count >= self.max_consecutive_errors:
            return Decision(
                type=DecisionType.SWITCH_STRATEGY,
                next_pattern="fallback.v1.0.0",
                error=f"too_many_errors:{self.error_count}"
            )
        return self.fallback_strategy.create_error(reason, capabilities)

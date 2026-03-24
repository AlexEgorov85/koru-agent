from typing import Any, Dict, List, Optional
from core.models.data.capability import Capability
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.application.behaviors.react.pattern import FallbackStrategyService
from core.models.schemas.react_models import ReasoningResult
from core.application.agent.strategies.react.validation import validate_reasoning_result
from .base_handler import BaseReActHandler


class GenerateDecisionHandler(BaseReActHandler):
    """Обработчик генерации решения в ReAct паттерне."""

    def __init__(self, pattern):
        super().__init__(pattern)
        self.fallback_strategy = FallbackStrategyService()

    async def execute(
        self,
        session_context: Any,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any],
        execution_context: Optional[Any] = None
    ) -> BehaviorDecision:
        """
        Генерация решения на основе анализа.

        ARGS:
        - session_context: контекст сессии
        - available_capabilities: доступные capabilities
        - context_analysis: результаты анализа
        - execution_context: контекст выполнения

        RETURNS:
        - BehaviorDecision
        """
        await self.log_info("generate_decision: started")

        try:
            # 1. Структурированное рассуждение через LLM
            reasoning_result = await self._perform_structured_reasoning(
                session_context=session_context,
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                execution_context=execution_context
            )

            # 2. Проверка на ошибку в reasoning_result
            if isinstance(reasoning_result, dict) and reasoning_result.get("error"):
                await self.log_warning(f"reasoning вернул ошибку: {reasoning_result['error']}")
                return self.fallback_strategy.create_error(
                    reason=reasoning_result["error"],
                    available_capabilities=available_capabilities
                )

            # 3. Конвертация ReasoningResult в BehaviorDecision
            decision = self._convert_to_decision(
                reasoning_result=reasoning_result,
                available_capabilities=available_capabilities
            )

            await self.log_info(f"generate_decision: completed decision={decision.action}")
            return decision

        except Exception as e:
            await self.log_error(f"generate_decision exception: {e}")
            return self.fallback_strategy.create_error(
                reason=str(e)[:100],
                available_capabilities=available_capabilities
            )

    async def _perform_structured_reasoning(
        self,
        session_context: Any,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        execution_context: Optional[Any]
    ) -> ReasoningResult:
        """Выполнение структурированного рассуждения через LLM."""
        from core.application.agent.strategies.react.schema_validator import SchemaValidator
        from core.application.agent.strategies.react.prompt_builder import PromptBuilderService

        # Построение промпта
        reasoning_prompt = await self.pattern._build_reasoning_prompt(
            session_context=session_context,
            context_analysis=context_analysis,
            available_capabilities=available_capabilities,
            session_context_for_builder=session_context
        )

        if not reasoning_prompt:
            raise RuntimeError("Не удалось построить reasoning prompt")

        # Выполнение LLM вызова
        schema_validator = SchemaValidator()
        llm_result = await self.pattern._execute_llm_with_orchestrator(
            llm_request=reasoning_prompt,
            llm_provider=getattr(self.pattern, 'llm', None),
            timeout=getattr(self.pattern, 'llm_timeout', 30.0),
            session_context=session_context
        )

        success, response, error = llm_result
        if not success:
            return ReasoningResult(
                thought="Ошибка LLM",
                analysis={"error": error},
                decision={"next_action": "final_answer.generate"},
                confidence=0.0
            )

        # Валидация результата
        try:
            validation_result = validate_reasoning_result(response, schema_validator)
            if not validation_result.is_valid:
                await self.log_warning(f"Validation errors: {validation_result.errors}")
                return self.fallback_strategy.create_reasoning_fallback(
                    context_analysis=context_analysis,
                    available_capabilities=available_capabilities,
                    reason=f"validation_failed"
                )

            reasoning_result = validation_result.parsed_result
            return reasoning_result

        except Exception as e:
            await self.log_error(f"Validation exception: {e}")
            return self.fallback_strategy.create_reasoning_fallback(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason=f"validation_exception"
            )

    def _convert_to_decision(
        self,
        reasoning_result: ReasoningResult,
        available_capabilities: List[Capability]
    ) -> BehaviorDecision:
        """Конвертация ReasoningResult в BehaviorDecision."""
        decision_data = reasoning_result.decision if hasattr(reasoning_result, 'decision') else reasoning_result
        next_action = decision_data.get("next_action", "") if isinstance(decision_data, dict) else getattr(decision_data, 'next_action', '')

        # Определение типа решения
        if reasoning_result.stop_condition or reasoning_result.stop_reason:
            return BehaviorDecision(
                action=BehaviorDecisionType.STOP,
                reason=reasoning_result.stop_reason or "reasoning_stop",
                confidence=reasoning_result.confidence
            )

        # Поиск capability по имени
        capability = next_action
        if next_action:
            for cap in available_capabilities:
                if cap.name == next_action:
                    capability = cap
                    break

        if isinstance(capability, Capability):
            parameters = decision_data.get("parameters", {}) if isinstance(decision_data, dict) else getattr(decision_data, 'parameters', {})
            return BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=capability.name,
                parameters=parameters,
                reason=decision_data.get("reasoning", "reasoning_completed"),
                confidence=reasoning_result.confidence
            )

        # Fallback
        return self.fallback_strategy.create_error(
            reason=f"capability_not_found_{next_action}",
            available_capabilities=available_capabilities
        )

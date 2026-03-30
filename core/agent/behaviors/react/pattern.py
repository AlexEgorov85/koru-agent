"""ReActPattern - реактивная стратегия поведения.

АРХИТЕКТУРА:
1. decide() - точка входа, единственное место принятия решений
2. analyze_context() - анализ контекста и прогресса
3. generate_decision() - генерация решения через LLM
4. _call_llm() - вызов LLM
5. _make_decision() - принятие решения на основе результата LLM

ПАТТЕРН РАБОТЫ:
- LLM анализирует контекст и возвращает reasoning с next_action
- Pattern преобразует reasoning в Decision (ACT/FINISH/FAIL)
- Runtime выполняет Decision через executor
"""

from typing import Any, Dict, List
from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.agent.behaviors.base import Decision, DecisionType
from core.agent.strategies.react.schema_validator import SchemaValidator
from core.agent.strategies.react.utils import analyze_context
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
        
        # Ресурсы для LLM
        self.reasoning_schema = None
        self.reasoning_prompt_template = None
        self.system_prompt_template = None
        
        # Состояние
        self.error_count = 0
        self.max_consecutive_errors = 3
        
        # Сервисы
        self.schema_validator = SchemaValidator()
        self.fallback_strategy = FallbackStrategyService()
        self._event_bus_logger = None

    @property
    def llm_orchestrator(self):
        """Получить LLMOrchestrator из application_context."""
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None

    # =========================================================================
    # ПУБЛИЧНЫЙ ИНТЕРФЕЙС (Decision Loop)
    # =========================================================================
    
    async def decide(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability]
    ) -> Decision:
        """
        ЕДИНСТВЕННОЕ место принятия решений.
        
        Поток: analyze_context -> generate_decision -> _make_decision
        """
        context = await self.analyze_context(session_context, available_capabilities)
        return await self.generate_decision(session_context, context, available_capabilities)

    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Анализ контекста сессии."""
        # Получаем capabilities если не переданы
        if not available_capabilities and self.application_context:
            available_capabilities = await self.application_context.get_all_capabilities()
        
        # Используем utils analyze_context
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
        # Проверка ресурсов
        if not self._ensure_resources_loaded():
            self.error_count += 1
            if self.error_count >= self.max_consecutive_errors:
                return Decision(
                    type=DecisionType.SWITCH_STRATEGY,
                    next_pattern="fallback.v1.0.0",
                    error=f"too_many_errors:{self.error_count}"
                )
            return self.fallback_strategy.create_error(
                "resources_not_loaded", available_capabilities
            )
        
        try:
            # Вызов LLM
            reasoning_result = await self._call_llm(session_context, context, available_capabilities)
            
            # Сохраняем размышление
            thought = reasoning_result.get("thought", "") if isinstance(reasoning_result, dict) else ""
            if hasattr(reasoning_result, "thought"):
                thought = reasoning_result.thought
            session_context.record_decision(decision_data="reasoning", reasoning=thought)
            
            # Принятие решения
            decision = await self._make_decision(reasoning_result, available_capabilities)
            
            # Сброс счётчика ошибок
            self.error_count = 0
            return decision
            
        except Exception as e:
            self.error_count += 1
            if self.error_count >= self.max_consecutive_errors:
                return Decision(
                    type=DecisionType.SWITCH_STRATEGY,
                    next_pattern="fallback.v1.0.0",
                    error=f"too_many_errors:{self.error_count}"
                )
            return self.fallback_strategy.create_error(str(e), available_capabilities)

    # =========================================================================
    # LLM ВЫЗОВ
    # =========================================================================
    
    async def _call_llm(
        self,
        session_context: SessionContext,
        context: Dict[str, Any],
        available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Вызвать LLM и получить результат рассуждения."""
        from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
        
        # Рендеринг промпта
        prompt = self.prompt_builder.build_reasoning_prompt(
            context_analysis=context,
            available_capabilities=available_capabilities,
            templates={
                "system": self.system_prompt_template,
                "user": self.reasoning_prompt_template
            },
            schema_validator=self.schema_validator,
            session_context=session_context
        )
        
        # Подготовка запроса
        llm_request = LLMRequest(
            prompt=prompt,
            system_prompt=self.system_prompt_template,
            temperature=0.3,
            max_tokens=1000,
            structured_output=StructuredOutputConfig(
                output_model="ReasoningResult",
                schema_def=self.reasoning_schema,
                max_retries=3,
                strict_mode=False
            )
        )
        
        # Вызов LLM
        orchestrator = self.llm_orchestrator
        if not orchestrator:
            return self.fallback_strategy.create_reasoning_fallback(
                context, available_capabilities, "orchestrator_not_available"
            )
        
        try:
            result = await orchestrator.execute_structured(
                request=llm_request,
                provider=None,
                session_id=session_context.session_id
            )
            
            if not result or not hasattr(result, 'parsed_content') or result.parsed_content is None:
                return self.fallback_strategy.create_reasoning_fallback(
                    context, available_capabilities, "llm_call_failed"
                )
            
            return result.parsed_content
            
        except Exception as e:
            return self.fallback_strategy.create_reasoning_fallback(
                context, available_capabilities, f"llm_exception:{str(e)}"
            )

    # =========================================================================
    # ПРИНЯТИЕ РЕШЕНИЯ
    # =========================================================================
    
    async def _make_decision(
        self,
        reasoning_result: Any,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Преобразовать результат LLM в Decision."""
        
        # Извлечение данных из результата
        if isinstance(reasoning_result, dict):
            stop_condition = reasoning_result.get("stop_condition", False)
            stop_reason = reasoning_result.get("stop_reason")
            decision = reasoning_result.get("decision", {})
            capability_name = decision.get("next_action") if isinstance(decision, dict) else None
            parameters = decision.get("parameters", {}) if isinstance(decision, dict) else {}
            reasoning = decision.get("reasoning", "") if isinstance(decision, dict) else ""
        else:
            stop_condition = getattr(reasoning_result, "stop_condition", False)
            stop_reason = getattr(reasoning_result, "stop_reason", None)
            decision = getattr(reasoning_result, "decision", None)
            capability_name = getattr(decision, "next_action", None) if decision else None
            parameters = getattr(decision, "parameters", {}) if decision else {}
            reasoning = getattr(decision, "reasoning", "") if decision else ""
        
        # Обработка stop_condition
        if stop_condition:
            return await self._handle_stop_condition(
                capability_name, parameters, stop_reason
            )
        
        # Проверка capability_name
        if not capability_name:
            return Decision(
                type=DecisionType.FAIL,
                error="LLM не вернул next_action"
            )
        
        # Поиск capability
        capability = self._find_capability(available_capabilities, capability_name)
        
        if not capability:
            # Fallback: ищем первую react capability
            for cap in available_capabilities:
                if "react" in [s.lower() for s in (cap.supported_strategies or [])]:
                    capability = cap
                    capability_name = cap.name
                    break
            
            if not capability:
                return Decision(
                    type=DecisionType.FAIL,
                    error="no_available_capabilities"
                )
        
        # Валидация параметров
        validated_params = self._validate_capability_parameters(
            capability, parameters, {}
        )
        
        # Проверка на final_answer
        is_final = capability_name == "final_answer.generate"
        
        return Decision(
            type=DecisionType.ACT,
            action=capability_name,
            parameters=validated_params,
            reasoning=reasoning,
            is_final=is_final
        )

    async def _handle_stop_condition(
        self,
        capability_name: str,
        parameters: Dict[str, Any],
        stop_reason: str
    ) -> Decision:
        """Обработать условие остановки."""
        # Если есть final_answer - вызываем его
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
        
        # Просто останавливаемся
        return Decision(
            type=DecisionType.FAIL,
            error=stop_reason or "goal_achieved"
        )

    # =========================================================================
    # РЕСУРСЫ
    # =========================================================================
    
    def _ensure_resources_loaded(self) -> bool:
        """Убедиться что ресурсы загружены, загрузить если нет."""
        if self.reasoning_prompt_template and self.reasoning_schema and self.system_prompt_template:
            return True
        
        # Загрузка system prompt
        if 'behavior.react.think' in self.system_prompts:
            obj = self.system_prompts['behavior.react.think']
            if hasattr(obj, 'content') and obj.content:
                self.system_prompt_template = obj.content
        
        # Fallback
        if not self.system_prompt_template and self.prompts:
            if "behavior.react.think.system" in self.prompts:
                obj = self.prompts["behavior.react.think.system"]
                if hasattr(obj, 'content') and obj.content:
                    self.system_prompt_template = obj.content
        
        # Загрузка user prompt
        if 'behavior.react.think' in self.user_prompts:
            obj = self.user_prompts['behavior.react.think']
            if hasattr(obj, 'content') and obj.content:
                self.reasoning_prompt_template = obj.content
        
        # Fallback
        if not self.reasoning_prompt_template and self.prompts:
            if "behavior.react.think.user" in self.prompts:
                obj = self.prompts["behavior.react.think.user"]
                if hasattr(obj, 'content') and obj.content:
                    self.reasoning_prompt_template = obj.content
        
        # Загрузка schema
        if self.output_contracts:
            if "behavior.react.think" in self.output_contracts:
                schema_cls = self.output_contracts["behavior.react.think"]
                if schema_cls:
                    self.reasoning_schema = (
                        schema_cls.model_json_schema() 
                        if hasattr(schema_cls, 'model_json_schema') 
                        else schema_cls
                    )
        
        return bool(self.reasoning_prompt_template and self.reasoning_schema and self.system_prompt_template)

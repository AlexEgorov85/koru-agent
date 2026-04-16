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
from core.infrastructure.logging.event_types import LogEventType
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
        executor=None
    ):
        super().__init__(component_name, component_config, application_context, executor)

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

            # Логируем входные параметры
            self._log_debug(
                f"📥 [ReAct.decide] Входные параметры: "
                f"session_id={session_context.session_id}, "
                f"goal={session_context.goal}, "
                f"caps={len(available_capabilities)}",
                event_type=LogEventType.AGENT_DECISION
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
                event_type=LogEventType.LLM_CALL
            )
            
            # Schema из контракта (model_json_schema - метод класса, не экземпляра)
            schema = None
            if output_contract:
                if hasattr(output_contract, 'model_json_schema'):
                    schema = output_contract.model_json_schema()
                elif hasattr(output_contract, 'model_schema'):
                    schema = output_contract.model_schema
            
            if not system or not user:
                return self._handle_error("prompts_not_loaded", available_capabilities)

            # Рендеринг промпта через build_reasoning_prompt
            full_prompt = self.prompt_builder.build_reasoning_prompt(
                context_analysis=context,
                available_capabilities=available_capabilities,
                templates={"system": system, "user": user},
                schema_validator=self.schema_validator,
                session_context=session_context,
                pattern_id="react",
                application_context=self.application_context
            )

            # Логируем ПОЛНЫЙ запрос ПЕРЕД вызовом LLM (только в файл)
            self._log_debug(
                f"🔵 [ReAct.decide] === ПОЛНЫЙ ЗАПРОС К LLM ===\n"
                f"--- System Prompt (len={len(system)}) ---\n{system}\n\n"
                f"--- User Prompt (рендер, len={len(full_prompt)}) ---\n{full_prompt}\n\n"
                f"--- Output Schema (JSON Schema) ---\n{schema}",
                event_type=LogEventType.LLM_CALL
            )
            
            # Вызов LLM
            orchestrator = self.llm_orchestrator
            if not orchestrator:
                return self.fallback_strategy.create_reasoning_fallback(
                    context, available_capabilities, "orchestrator_not_available"
                )

            # Получаем провайдер из инфраструктурного контекста
            provider = self.llm_provider

            if provider is None:
                self._log_error(
                    f"LLM provider is None! "
                    f"Registry keys: {getattr(getattr(getattr(self.application_context, 'infrastructure_context', None), 'resource_registry', None), 'get_all_names', lambda: [])()}"
                )
                return self._handle_error("llm_provider_not_available", available_capabilities)

            llm_request = LLMRequest(
                prompt=full_prompt,
                system_prompt=system,
                temperature=0.3,
                max_tokens=2000,  # Увеличено для полного JSON ответа
                structured_output=StructuredOutputConfig(
                    output_model="ReasoningResult",
                    schema_def=schema,
                    max_retries=3,
                    strict_mode=False
                )
            )
            
            try:
                self._log_info(
                    f"🔮 LLM вызов (temperature=0.3, max_tokens=2000, structured_output)",
                    event_type=LogEventType.LLM_CALL
                )

                # Извлекаем данные для трассировки из session_context
                step_number = None
                if hasattr(session_context, 'step_context') and session_context.step_context:
                    step_number = session_context.step_context.get_current_step_number()

                result = await orchestrator.execute_structured(
                    request=llm_request,
                    provider=provider,
                    session_id=session_context.session_id,
                    agent_id=getattr(session_context, 'agent_id', None),
                    step_number=step_number,
                    goal=session_context.goal,
                    phase='think',
                    use_native_structured_output=False
                )
            except Exception as e:
                self._log_error(
                    f"❌ Исключение при LLM вызове: {type(e).__name__}: {e}",
                    event_type=LogEventType.LLM_ERROR,
                    exc_info=True
                )
                return self.fallback_strategy.create_error(
                    f"llm_exception:{type(e).__name__}:{str(e)}", available_capabilities
                )

            # ✅ ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ПРИЧИН пустого/невалидного ответа
            if not result:
                self._log_error("❌ LLM вернул None (result=None)", event_type=LogEventType.LLM_ERROR)
                return self.fallback_strategy.create_error(
                    "llm_returned_none", available_capabilities
                )
            elif result.finish_reason == "empty":
                self._log_error(
                    f"❌ LLM вернул пустой ответ (finish_reason=empty) | "
                    f"model={result.model} | attempts={getattr(result, 'parsing_attempts', 'N/A')}",
                    event_type=LogEventType.LLM_ERROR
                )
                return self.fallback_strategy.create_error(
                    "llm_empty_response", available_capabilities
                )
            elif not result.content and not result.raw_response:
                self._log_error(
                    f"❌ LLM вернул ответ без контента | "
                    f"finish_reason={result.finish_reason} | model={result.model}",
                    event_type=LogEventType.LLM_ERROR
                )
                return self.fallback_strategy.create_error(
                    "llm_no_content", available_capabilities
                )
            elif not hasattr(result, 'parsed_content') or result.parsed_content is None:
                validation_errors = getattr(result, 'validation_errors', [])
                self._log_error(
                    f"❌ JSON не распарсен | "
                    f"finish_reason={result.finish_reason} | "
                    f"errors={validation_errors}",
                    event_type=LogEventType.LLM_ERROR
                )
                return self.fallback_strategy.create_error(
                    "llm_json_parse_failed", available_capabilities
                )

            reasoning_result = result.parsed_content
            self._log_info(
                f"✅ LLM ответ получен (thought: {getattr(reasoning_result, 'thought', '')})",
                event_type=LogEventType.LLM_RESPONSE
            )

            # Логируем ПОЛНЫЙ ответ LLM (сырой + распарсенный, только в файл)
            raw_content = getattr(result, 'raw_response', None)
            raw_text = getattr(raw_content, 'content', '') if raw_content else ''
            self._log_debug(
                f"🟢 [ReAct.decide] === ПОЛНЫЙ ОТВЕТ ОТ LLM ===\n"
                f"--- Raw Response (len={len(raw_text)}) ---\n{raw_text}\n\n"
                f"--- Parsed Content (Pydantic модель) ---\n"
                f"{reasoning_result.model_dump_json(indent=2) if hasattr(reasoning_result, 'model_dump_json') else str(reasoning_result)}",
                event_type=LogEventType.LLM_RESPONSE
            )

            # Извлекаем размышление из 10 полей анализа
            reasoning = self._extract_analysis_reasoning(reasoning_result)
            session_context.record_decision(decision_data="reasoning", reasoning=reasoning)

            # Принятие решения
            decision = await self._make_decision(reasoning_result, available_capabilities)

            # Логируем финальное решение агента
            self._log_info(
                f"🎯 [ReAct.decide] Финальное решение: "
                f"type={decision.type.value}, "
                f"action={decision.action or 'N/A'}, "
                f"params={list((decision.parameters or {}).keys())}, "
                f"reasoning={decision.reasoning or 'N/A'}",
                event_type=LogEventType.AGENT_DECISION
            )
            
            self.error_count = 0
            return decision
            
        except Exception as e:
            self._log_error(
                f"❌ Критическая ошибка в ReActPattern.generate_decision: {e}",
                exc_info=True
            )
            return self._handle_error(str(e), available_capabilities)

    async def _make_decision(
        self,
        reasoning_result: Any,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Преобразовать результат LLM в Decision."""
        reasoning = self._extract_analysis_reasoning(reasoning_result)
        
        if isinstance(reasoning_result, dict):
            stop_condition = reasoning_result.get("stop_condition", False)
            stop_reason = reasoning_result.get("stop_reason", None)
            decision = reasoning_result.get("decision", None)
            capability_name = decision.get("next_action", None) if isinstance(decision, dict) else None
            parameters = decision.get("parameters", {}) if isinstance(decision, dict) else {}
        else:
            stop_condition = getattr(reasoning_result, "stop_condition", False)
            stop_reason = getattr(reasoning_result, "stop_reason", None)
            decision = getattr(reasoning_result, "decision", None)
            if isinstance(decision, dict):
                capability_name = decision.get("next_action", None)
                parameters = decision.get("parameters", {})
            else:
                capability_name = getattr(decision, "next_action", None) if decision else None
                parameters = getattr(decision, "parameters", {}) if decision else {}

        if stop_condition:
            return self._handle_stop_condition(capability_name, parameters, stop_reason)

        if not capability_name:
            return Decision(type=DecisionType.FAIL, error="LLM не вернул next_action")
        
        # Поиск capability (inline реализация вместо _find_capability)
        capability = None
        # 1. Прямое совпадение
        for cap in available_capabilities:
            if cap.name == capability_name:
                capability = cap
                break
        
        # 2. Совпадение по префиксу
        if not capability and '.' in capability_name:
            prefix = capability_name.split('.')[0]
            for cap in available_capabilities:
                if cap.name == prefix:
                    capability = cap
                    break
        
        if not capability:
            for cap in available_capabilities:
                if "react" in [s.lower() for s in (cap.supported_strategies or [])]:
                    capability = cap
                    capability_name = cap.name
                    break
            
            if not capability:
                return Decision(type=DecisionType.FAIL, error="no_available_capabilities")

        # Валидация параметров (inline реализация вместо _validate_capability_parameters)
        validated_params = parameters
        if hasattr(self, 'schema_validator') and self.schema_validator is not None:
            try:
                validated = self.schema_validator.validate_parameters(
                    capability=capability,
                    raw_params=parameters,
                    context=str({})
                )
                validated_params = validated if validated else parameters
            except Exception:
                validated_params = {"input": parameters.get("input", "Продолжить выполнение задачи")}

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
        """Обработать ошибку - возвращаем FAIL."""
        self.error_count += 1
        return self.fallback_strategy.create_error(reason, capabilities)

    def _extract_analysis_reasoning(self, reasoning_result: Any) -> str:
        """
        Универсальное извлечение размышления из ответа LLM.
        Поддерживает: Pydantic-модели, dict, а также как 10 полей анализа, так и простое поле reasoning.
        """
        import json

        def safe_get(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        # 1. Попытка извлечь 10 аналитических полей (старая схема)
        ANALYSIS_FIELDS = [
            ("analysis_progress", "Прогресс"),
            ("analysis_state", "Состояние"),
            ("analysis_deficit", "Дефицит"),
            ("analysis_history", "История"),
            ("analysis_errors", "Ошибки"),
            ("analysis_tool_choice", "Выбор инструмента"),
            ("analysis_params", "Параметры"),
            ("analysis_fallback", "Fallback"),
            ("analysis_stop", "Остановка"),
            ("analysis_final", "Итог"),
        ]

        lines = []
        for field_name, label in ANALYSIS_FIELDS:
            value = safe_get(reasoning_result, field_name)
            if value:
                lines.append(f"{label}: {value}")

        if lines:
            return "\n".join(lines)

        # 2. Fallback: ищем стандартные поля размышления
        for key in ("reasoning", "thought", "reason", "explanation", "logic"):
            val = safe_get(reasoning_result, key)
            if val:
                return str(val).strip()

        # 3. Fallback: если это Pydantic-модель или dict, сериализуем содержимое
        if hasattr(reasoning_result, 'model_dump'):
            dump = reasoning_result.model_dump()
            if dump:
                return json.dumps(dump, ensure_ascii=False, indent=2)
        elif isinstance(reasoning_result, dict) and reasoning_result:
            return json.dumps(reasoning_result, ensure_ascii=False, indent=2)

        return "Размышление не доступно"

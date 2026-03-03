from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.session_context.session_context import SessionContext
from typing import List, Dict, Any


class EvaluationPattern(BaseBehaviorPattern):
    """
    Паттерн оценки достижения цели.
    
    АРХИТЕКТУРА:
    - component_name используется для получения config из AppConfig
    - Промпты и контракты загружаются через BaseBehaviorPattern
    - pattern_id генерируется из component_name для совместимости
    """

    def __init__(self, component_name: str, component_config = None, application_context = None, executor = None):
        """Инициализация паттерна.
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО, например "evaluation_pattern")
        - component_config: ComponentConfig с resolved_prompts/contracts (из AppConfig)
        - application_context: Прикладной контекст
        - executor: ActionExecutor для взаимодействия
        """
        super().__init__(component_name, component_config, application_context, executor)

    async def _publish_llm_response_received(
        self,
        session_context,
        response,
        error_message: str = None,
        error_type: str = None
    ) -> None:
        """
        Публикует событие llm.response.received независимо от результата.
        """
        if not (self.application_context and hasattr(self.application_context, 'infrastructure_context')):
            self.logger.debug("EventBus недоступен, пропускаем публикацию llm.response.received")
            return

        from core.infrastructure.event_bus.unified_event_bus import EventType

        # Получаем agent_id из session_context или application_context
        agent_id = getattr(session_context, 'agent_id', 'unknown')
        if agent_id == 'unknown' and hasattr(self.application_context, 'id'):
            agent_id = self.application_context.id

        # Обработка ответа для логирования
        if response is not None:
            if isinstance(response, dict) and 'raw_response' in response:
                result = response['raw_response']
                response_format = "dict.raw_response"
            elif hasattr(response, 'content'):
                result = response.content
                response_format = "object.content"
            else:
                result = response
                response_format = type(response).__name__
        else:
            result = None
            response_format = "none"

        # Формируем данные события
        event_data = {
            "agent_id": agent_id,
            "component": "evaluation_pattern",
            "phase": "assess",
            "response_format": response_format,
            "response": result,
            "session_id": getattr(session_context, 'session_id', 'unknown'),
            "goal": session_context.get_goal() if session_context else 'unknown'
        }

        # Добавляем информацию об ошибке если есть
        if error_message:
            event_data["error"] = error_message
        if error_type:
            event_data["error_type"] = error_type

        try:
            await self.application_context.infrastructure_context.event_bus.publish(
                event=EventType.LLM_RESPONSE_RECEIVED,
                data=event_data,
                source="evaluation_pattern.assess",
                correlation_id=getattr(session_context, 'session_id', '')
            )
            self.logger.debug("Событие LLM_RESPONSE_RECEIVED опубликовано")
        except Exception as e:
            self.logger.error(f"Ошибка публикации LLM_RESPONSE_RECEIVED: {e}")

    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        return {
            "goal": session_context.get_goal(),
            "context_summary": session_context.get_summary(),
            "available_capabilities": available_capabilities
        }

    async def generate_decision(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """
        Оценка достижения цели через LLM.

        АРХИТЕКТУРА:
        - Использует промпт из self.prompts (загружен BaseComponent.initialize())
        - Использует output контракт из self.output_contracts
        - LLM через infrastructure_context (не session_context!)
        """
        # Подготовка контекста для оценки
        goal = context_analysis["goal"]
        context_summary = context_analysis["context_summary"]

        # Получение промпта из кэша BaseComponent
        assessment_prompt = self.get_prompt("behavior.evaluation.assess")

        if not assessment_prompt:
            self.logger.warning("Промпт для оценки не загружен, используем fallback")
            assessment_prompt = "Оцени достижение цели: {goal}\nКонтекст: {context_summary}"

        # Заменяем переменные в промпте
        evaluation_prompt = self._render_prompt(assessment_prompt, {
            "goal": str(goal),
            "context_summary": str(context_summary)
        })

        try:
            # LLM через infrastructure_context (ПРАВИЛЬНО)
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")

            # Получаем output контракт из кэша BaseComponent (ПРАВИЛЬНО)
            output_schema = self.get_output_contract("behavior.evaluation.assess")

            if not output_schema:
                self.logger.warning("Output контракт не загружен, используем fallback схему")
                from pydantic import BaseModel, Field
                from typing import Optional
                
                class EvaluationResult(BaseModel):
                    achieved: bool = Field(description="Достигнута ли цель")
                    partial_progress: bool = Field(description="Есть ли частичный прогресс")
                    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность в оценке")
                    summary: str = Field(description="Краткое резюме")
                    reasoning: str = Field(description="Обоснование оценки")
                
                output_schema = EvaluationResult.model_json_schema()

            from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
            
            llm_request = LLMRequest(
                prompt=evaluation_prompt,
                structured_output=StructuredOutputConfig(
                    output_model="EvaluationResult",
                    schema_def=output_schema
                )
            )
            
            response = await llm_provider.generate_structured_request(llm_request)

            # === ПУБЛИКАЦИЯ СОБЫТИЯ: ПОЛУЧЕН ОТВЕТ ===
            await self._publish_llm_response_received(
                session_context=session_context,
                response=response,
                error_message=None,
                error_type=None
            )

            # === ПРОВЕРКА НА ОШИБКУ LLM ===
            llm_response = response
            if isinstance(response, dict) and 'raw_response' in response:
                llm_response = response['raw_response']

            if getattr(llm_response, 'finish_reason', None) == 'error':
                error_msg = "Неизвестная ошибка LLM"
                if hasattr(llm_response, 'metadata') and llm_response.metadata:
                    if isinstance(llm_response.metadata, dict):
                        error_msg = llm_response.metadata.get('error', error_msg)
                    elif isinstance(llm_response.metadata, str):
                        error_msg = llm_response.metadata
                self.logger.error(f"LLM вернул ошибку при оценке: {error_msg}")
                
                # Публикуем событие об ошибке
                await self._publish_llm_response_received(
                    session_context=session_context,
                    response=response,
                    error_message=error_msg,
                    error_type="finish_reason_error"
                )
                
                raise RuntimeError(f"Ошибка LLM при оценке: {error_msg}")

            if hasattr(llm_response, 'metadata') and llm_response.metadata and 'error' in llm_response.metadata:
                error_msg = llm_response.metadata['error']
                self.logger.error(f"LLM вернул ошибку в metadata: {error_msg}")
                
                # Публикуем событие об ошибке
                await self._publish_llm_response_received(
                    session_context=session_context,
                    response=response,
                    error_message=error_msg,
                    error_type="metadata_error"
                )
                
                raise RuntimeError(f"Ошибка LLM при оценке: {error_msg}")

            # Обработка результата
            result = response.content if hasattr(response, 'content') else response
            if isinstance(result, str):
                import json
                result = json.loads(result)

            # Создание объекта оценки
            class EvaluationResult:
                def __init__(self, data):
                    self.achieved = data.get("achieved", False)
                    self.partial_progress = data.get("partial_progress", False)
                    self.confidence = data.get("confidence", 0.0)
                    self.summary = data.get("summary", "")
                    self.reasoning = data.get("reasoning", "")
                    self.refined_goal = data.get("refined_goal", goal)

            evaluation = EvaluationResult(result)

            # Принятие решения на основе оценки
            if evaluation.achieved or (evaluation.confidence > 0.8 and not evaluation.partial_progress):
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=f"goal_achieved: {evaluation.summary}"
                )
            elif evaluation.confidence < 0.3:
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback.v1.0.0",
                    reason=f"low_confidence: {evaluation.reasoning}"
                )
            else:
                return BehaviorDecision(
                    action=BehaviorDecisionType.CONTINUE,
                    reason=f"continue_execution: {evaluation.summary}"
                )

        except Exception as e:
            error_msg = f"Ошибка при оценке цели: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            # Публикуем событие об ошибке
            await self._publish_llm_response_received(
                session_context=session_context,
                response=None,
                error_message=error_msg,
                error_type="evaluation_error"
            )
            
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="fallback.v1.0.0",
                reason=f"evaluation_error: {str(e)}"
            )

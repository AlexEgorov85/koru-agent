from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.session_context.session_context import SessionContext
import logging
from typing import List, Dict, Any


class EvaluationPattern(BaseBehaviorPattern):
    """
    Паттерн оценки достижения цели.
    
    АРХИТЕКТУРА:
    - component_name используется для получения config из AppConfig
    - Промпты и контракты загружаются через BaseBehaviorPattern
    - pattern_id генерируется из component_name для совместимости
    """

    def __init__(self, component_name: str, component_config = None, application_context = None):
        """Инициализация паттерна.
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО, например "evaluation_pattern")
        - component_config: ComponentConfig с resolved_prompts/contracts (из AppConfig)
        - application_context: Прикладной контекст
        """
        super().__init__(component_name, component_config, application_context)

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
        - Использует промпт из component_config (через get_prompt())
        - Использует output контракт из component_config (через get_output_contract())
        """
        # Подготовка контекста для оценки
        goal = context_analysis["goal"]
        context_summary = context_analysis["context_summary"]

        # Получение промпта из кэша (загружен из component_config)
        assessment_prompt = self.get_prompt("behavior.react.think")  # Или другой ключ из registry
        
        if not assessment_prompt:
            self.logger.warning("Промпт для оценки не загружен, используем fallback")
            assessment_prompt = "Оцени достижение цели: {goal}\nКонтекст: {context_summary}"
        
        # Заменяем переменные в промпте
        evaluation_prompt = self._render_prompt(assessment_prompt, {
            "goal": str(goal),
            "context_summary": str(context_summary)
        })

        try:
            # Вызов LLM для оценки через сервис, доступный через контекст
            llm_provider = session_context.get_llm_provider()
            
            # Получаем output контракт для структурированного вывода
            output_schema = self.get_output_contract("behavior.react.think")
            
            if not output_schema:
                self.logger.warning("Output контракт не загружен, используем fallback схему")
                output_schema = {
                    "type": "object",
                    "properties": {
                        "achieved": {"type": "boolean"},
                        "partial_progress": {"type": "boolean"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "summary": {"type": "string"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["achieved", "partial_progress", "confidence", "summary", "reasoning"]
                }

            response = await llm_provider.generate_structured(
                prompt=evaluation_prompt,
                schema=output_schema,
                temperature=0.1,
                max_tokens=500
            )

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
            self.logger.error(f"Ошибка при оценке цели: {e}", exc_info=True)
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="fallback.v1.0.0",
                reason=f"evaluation_error: {str(e)}"
            )

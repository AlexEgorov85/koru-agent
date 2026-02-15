from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus
from core.session_context.session_context import SessionContext
import logging
from typing import List, Dict, Any


class EvaluationPattern(BehaviorPatternInterface):
    """
    Паттерн оценки достижения цели.
    """

    pattern_id = "evaluation.v1.0.0"

    def __init__(self, pattern_id: str = None, metadata: dict = None, prompt_service: 'PromptService' = None):
        self.pattern_id = pattern_id or "evaluation.v1.0.0"
        self._prompt_service = prompt_service
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

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
        try:
            # 1. Анализ достижения цели через LLM
            evaluation = await self._evaluate_goal_achievement(session_context, context_analysis)

            # 2. Принятие решения
            if evaluation.achieved:
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason="goal_achieved",
                    parameters={"result": evaluation.summary}
                )
            elif evaluation.partial_progress:
                # Частичный прогресс → вернуться к планированию с уточнённой целью
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="planning.v1.0.0",
                    parameters={"refined_goal": evaluation.refined_goal},
                    reason="partial_progress_continue_with_refined_goal"
                )
            else:
                # Полный провал → переключиться на реактивный режим для диагностики
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="react.v1.0.0",
                    reason="evaluation_failed_need_diagnosis"
                )
        except Exception as e:
            self.logger.error(f"Ошибка в EvaluationPattern: {str(e)}", exc_info=True)
            # При ошибке оценки - возвращаемся к реактивной стратегии
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="react.v1.0.0",
                reason=f"evaluation_error: {str(e)}"
            )

    async def _evaluate_goal_achievement(self, session_context: SessionContext, context_analysis: Dict[str, Any]):
        """
        Оценка достижения цели через LLM
        """
        # Подготовка контекста для оценки
        goal = context_analysis["goal"]
        context_summary = context_analysis["context_summary"]

        # Получение промпта для оценки через сервис
        evaluation_prompt = await self._prompt_service.render(
            capability_name="behaviors.evaluation.assess_goal",
            variables={
                "goal": goal,
                "context_summary": context_summary
            }
        )

        try:
            # Вызов LLM для оценки через сервис, доступный через контекст
            llm_provider = session_context.get_llm_provider()
            
            response = await llm_provider.generate_structured(
                prompt=evaluation_prompt,
                schema={
                    "type": "object",
                    "properties": {
                        "achieved": {"type": "boolean"},
                        "partial_progress": {"type": "boolean"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "summary": {"type": "string"},
                        "refined_goal": {"type": "string"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["achieved", "partial_progress", "confidence", "summary", "reasoning"]
                },
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
                    self.refined_goal = data.get("refined_goal", "")
                    self.reasoning = data.get("reasoning", "")

            return EvaluationResult(result)

        except Exception as e:
            self.logger.error(f"Ошибка при оценке достижения цели: {str(e)}", exc_info=True)
            # Возвращаем базовую оценку при ошибке
            class EvaluationResult:
                def __init__(self, session_context):
                    self.achieved = False
                    self.partial_progress = True
                    self.confidence = 0.5
                    self.summary = "Ошибка при автоматической оценке, требуется ручная проверка"
                    self.refined_goal = session_context.get_goal()
                    self.reasoning = "Ошибка при анализе результатов выполнения"

            return EvaluationResult(session_context)
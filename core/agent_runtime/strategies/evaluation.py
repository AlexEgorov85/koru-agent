from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from .base import AgentStrategyInterface
import logging


class EvaluationStrategy(AgentStrategyInterface):
    """
    Оценка достижения цели.
    """

    name = "evaluation"
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def next_step(self, runtime):
        session = runtime.session

        try:
            # 1. Анализ достижения цели через LLM
            evaluation = await self._evaluate_goal_achievement(runtime, session)
            
            # 2. Принятие решения
            if evaluation.achieved:
                return StrategyDecision(
                    action=StrategyDecisionType.STOP,
                    reason="goal_achieved",
                    result=evaluation.summary
                )
            elif evaluation.partial_progress:
                # Частичный прогресс → вернуться к планированию с уточнённой целью
                return StrategyDecision(
                    action=StrategyDecisionType.SWITCH,
                    next_strategy="planning",
                    parameters={"refined_goal": evaluation.refined_goal},
                    reason="partial_progress_continue_with_refined_goal"
                )
            else:
                # Полный провал → переключиться на реактивный режим для диагностики
                return StrategyDecision(
                    action=StrategyDecisionType.SWITCH,
                    next_strategy="react",
                    reason="evaluation_failed_need_diagnosis"
                )
        except Exception as e:
            self.logger.error(f"Ошибка в EvaluationStrategy: {str(e)}", exc_info=True)
            # При ошибке оценки - возвращаемся к реактивной стратегии
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="react",
                reason=f"evaluation_error: {str(e)}"
            )

    async def _evaluate_goal_achievement(self, runtime, session):
        """
        Оценка достижения цели через LLM
        """
        # Подготовка контекста для оценки
        goal = session.get_goal()
        context_summary = session.get_summary()
        
        # Подготовка промпта для оценки
        prompt = f"""
        Проанализируй, была ли достигнута следующая цель:
        
        ЦЕЛЬ: {goal}
        
        КОНТЕКСТ ВЫПОЛНЕНИЯ:
        {context_summary}
        
        Ответь в формате JSON:
        {{
            "achieved": true/false,
            "partial_progress": true/false,
            "confidence": 0.0-1.0,
            "summary": "краткое резюме выполнения",
            "refined_goal": "уточненная цель если применимо",
            "reasoning": "обоснование оценки"
        }}
        """
        
        try:
            # Вызов LLM для оценки
            response = await runtime.system.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты эксперт в области оценки достижения целей. Отвечай точно и структурировано.",
                temperature=0.1,
                max_tokens=500,
                output_format="json"
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
                def __init__(self, session):
                    self.achieved = False
                    self.partial_progress = True
                    self.confidence = 0.5
                    self.summary = "Ошибка при автоматической оценке, требуется ручная проверка"
                    self.refined_goal = session.get_goal()
                    self.reasoning = "Ошибка при анализе результатов выполнения"
            
            return EvaluationResult(session)

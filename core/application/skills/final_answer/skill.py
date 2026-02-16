"""Навык для генерации финального ответа агента.

Этот навык анализирует весь контекст сессии и формирует
комплексный финальный ответ на основе всех собранных данных.
"""
import logging
from typing import Dict, Any, List
from core.session_context.base_session_context import BaseSessionContext
from core.application.skills.base_skill import BaseSkill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus

logger = logging.getLogger(__name__)


class FinalAnswerSkill(BaseSkill):
    """Навык для генерации финального ответа на основе всего контекста сессии."""

    name = "final_answer"
    supported_strategies = ["react", "planning", "evaluation", "plan_and_execute", "chain_of_thought"]

    def __init__(self, name: str, application_context: Any, **kwargs):
        super().__init__(name, application_context, **kwargs)
        self.application_context = application_context

    def get_capabilities(self) -> List[Capability]:
        """Возвращает список поддерживаемых capability для генерации финального ответа."""
        return [
            Capability(
                name="final_answer.generate",
                description="Генерация финального ответа на основе всего контекста сессии",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            )
        ]

    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Выполнение capability для генерации финального ответа."""
        step_number = getattr(context, 'current_step', 0) + 1
        logger.debug(f"Генерация финального ответа на шаге {step_number}")

        # Валидируем параметры через кэшированную схему из компонента
        try:
            # Получаем схему валидации из кэша компонента
            input_schema = self.get_cached_input_schema_safe(capability.name)
            
            if input_schema and input_schema != {}:
                # Создаем экземпляр схемы и валидируем параметры
                validated_params = input_schema.model_validate(parameters)
                validated_params = validated_params.model_dump()  # Преобразуем обратно в словарь
            else:
                # Если схема не найдена, используем переданные параметры без валидации
                validated_params = parameters
                logger.warning(f"Схема валидации для capability '{capability.name}' не найдена, пропускаем валидацию")
        except Exception as e:
            error_msg = f"Ошибка валидации параметров: {str(e)}"
            logger.error(error_msg)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=error_msg,
                error="INVALID_PARAMETERS"
            )
        
        try:
            if capability.name == "final_answer.generate":
                return await self._generate_final_answer(context, validated_params, step_number)
            else:
                error_msg = f"Неподдерживаемая capability: {capability.name}"
                logger.error(error_msg)
                return self._build_error_result(
                    context=context,
                    error_message=error_msg,
                    error_type="UNSUPPORTED_CAPABILITY",
                    step_number=step_number
                )
        except Exception as e:
            logger.error(f"Неожиданная ошибка при генерации финального ответа: {str(e)}", exc_info=True)
            return self._build_error_result(
                context=context,
                error_message=f"Внутренняя ошибка при генерации финального ответа: {str(e)}",
                error_type="INTERNAL_ERROR",
                step_number=step_number
            )

    async def _generate_final_answer(self, context: BaseSessionContext, parameters: Dict[str, Any], step_number: int) -> ExecutionResult:
        """Генерация финального ответа на основе контекста сессии."""
        try:
            # Извлечение целей и информации из контекста
            goal = context.get_goal() or "Не указана цель"
            
            # Сбор всей информации из контекста
            all_items = context.data_context.items if hasattr(context, 'data_context') and hasattr(context.data_context, 'items') else {}
            observations = []
            thoughts = []
            actions = []
            
            # Классификация элементов контекста
            for item_id, item in all_items.items():
                if item.item_type.value == "OBSERVATION":
                    observations.append(item.content)
                elif item.item_type.value in ["THOUGHT", "DECISION"]:
                    thoughts.append(item.content)
                elif item.item_type.value == "ACTION":
                    actions.append(item.content)
            
            # Подготовка контекста для генерации ответа
            context_summary = {
                "goal": goal,
                "observations": observations,
                "thoughts": thoughts,
                "actions": actions,
                "step_count": len(context.step_context.steps) if hasattr(context, 'step_context') and hasattr(context.step_context, 'steps') else 0,
                "summary": context.get_summary()
            }
            
            # Определение параметров форматирования
            include_steps = parameters.get("include_steps", True)
            include_evidence = parameters.get("include_evidence", True)
            format_type = parameters.get("format_type", "detailed")
            
            # Генерация финального ответа с помощью LLM
            final_answer = await self._synthesize_answer(
                context_summary=context_summary,
                include_steps=include_steps,
                include_evidence=include_evidence,
                format_type=format_type
            )
            
            # Формирование результата
            result_data = {
                "final_answer": final_answer,
                "goal": goal,
                "evidence_count": len(observations),
                "steps_included": include_steps,
                "evidence_included": include_evidence,
                "format_type": format_type
            }
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                observation_item_id=None,
                result=result_data,
                summary=f"Финальный ответ сгенерирован, цель: {goal[:50]}...",
                error=None
            )
            
        except Exception as e:
            logger.error(f"Ошибка генерации финального ответа: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="FINAL_ANSWER_GENERATION_ERROR",
                step_number=step_number
            )

    async def _synthesize_answer(self, context_summary: Dict[str, Any], include_steps: bool, include_evidence: bool, format_type: str) -> str:
        """Синтез финального ответа на основе собранного контекста."""
        
        goal = context_summary["goal"]
        
        # Формирование промпта для LLM в зависимости от типа форматирования
        if format_type == "concise":
            prompt_parts = [
                f"Цель: {goal}",
                f"На основе предоставленных данных, дай краткий и точный ответ на цель.",
            ]
        elif format_type == "structured":
            prompt_parts = [
                f"Цель: {goal}",
                f"Структурированный ответ:",
                f"- Краткое резюме",
                f"- Основные выводы", 
                f"- Подтверждающие данные"
            ]
        else:  # detailed
            prompt_parts = [
                f"Цель: {goal}",
                f"На основе предоставленных данных, дай подробный и исчерпывающий ответ на цель.",
                f"Включи все релевантные наблюдения и доказательства."
            ]
        
        # Добавление наблюдений (доказательств)
        if include_evidence and context_summary["observations"]:
            prompt_parts.append("\nНаблюдения:")
            for i, obs in enumerate(context_summary["observations"][-5:], 1):  # Последние 5 наблюдений
                obs_str = str(obs)[:500]  # Ограничение длины
                prompt_parts.append(f"{i}. {obs_str}")
        
        # Добавление шагов выполнения
        if include_steps and context_summary["actions"]:
            prompt_parts.append("\nШаги выполнения:")
            for i, action in enumerate(context_summary["actions"][-5:], 1):  # Последние 5 действий
                action_desc = action.get("capability", "неизвестно")
                action_params = str(action.get("parameters", ""))[:200]
                prompt_parts.append(f"{i}. {action_desc}: {action_params}")
        
        full_prompt = "\n".join(prompt_parts)
        
        try:
            # Подготовка запроса к LLM
            from core.models.types.llm_types import LLMRequest
            request = LLMRequest(
                prompt=full_prompt,
                system_prompt="Ты помощник, который генерирует финальные ответы на основе собранной информации. Отвечай точно, структурировано и вежливо.",
                temperature=0.3,
                max_tokens=1000
            )

            # Вызов LLM через инфраструктурный контекст
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
            response = await llm_provider.generate_structured(
                user_prompt=request.prompt,
                output_schema={},
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )

            # Извлечение содержимого ответа
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            logger.error(f"Ошибка вызова LLM для генерации ответа: {str(e)}")
            # Возврат резервного ответа
            return f"На основе проведенного анализа, цель '{goal}' была обработана. Количество наблюдений: {len(context_summary['observations'])}, количество шагов: {context_summary['step_count']}."

    def _build_error_result(self, context: BaseSessionContext, error_message: str, error_type: str, step_number: int) -> ExecutionResult:
        """Построение результата ошибки."""
        logger.error(f"Ошибка на шаге {step_number}: {error_type} - {error_message}")
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            observation_item_id=None,
            result=None,
            summary=f"Ошибка генерации финального ответа: {error_message}",
            error=None
        )
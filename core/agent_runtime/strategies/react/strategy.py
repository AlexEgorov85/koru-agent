"""EnhancedReActStrategy с полной моделью рассуждений и интеграцией с планами.
ОСОБЕННОСТИ:
- Полный анализ текущей ситуации и прогресса
- Структурированное принятие решений
- Поддержка отката при необходимости
- ИНТЕГРАЦИЯ с PlanningSkill для работы с планами
- ИСПОЛЬЗОВАНИЕ capability для работы с планами вместо локальной логики
- Сохранение совместимости с существующей архитектурой
"""
import json
import re
import time
import logging
from typing import Any, Dict, Optional
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.agent_runtime.strategies.react.schema_validator import SchemaValidator
from core.agent_runtime.strategies.react.utils import analyze_context
from core.agent_runtime.strategies.react.models import ReasoningResult
from core.agent_runtime.strategies.react.prompts import build_reasoning_prompt, build_system_prompt_for_reasoning
from core.agent_runtime.strategies.react.validation import validate_reasoning_result
from core.retry_policy.retry_and_error_policy import RetryPolicy
from models.execution import ExecutionStatus

logger = logging.getLogger(__name__)

class ReActStrategy(AgentStrategyInterface):
    """ReAct стратегия с полной моделью рассуждений и поддержкой планов.
    
    ЭТАПЫ РАБОТЫ:
    1. Анализ контекста и прогресса
    2. Проверка наличия и статуса плана
    3. Если есть активный план - запрос следующего шага через capability
    4. Если плана нет или он завершен - структурированное рассуждение через LLM
    5. Принятие решения на основе результатов
    6. Обработка ошибок и применение fallback
    """
    name = "react"

    def __init__(self):
        """Инициализация стратегии."""
        self.reasoning_schema = ReasoningResult.model_json_schema()
        # Удаляем служебные поля из схемы
        self.reasoning_schema.pop('title', None)
        self.reasoning_schema.pop('description', None)
        self.last_reasoning_time = 0.0
        self.error_count = 0
        self.max_consecutive_errors = 3
        self.schema_validator = SchemaValidator()
        self.retry_policy = RetryPolicy()
        # Флаг для принудительного использования плана
        self.force_plan_mode = False

    async def next_step(self, runtime) -> StrategyDecision:
        """Основной метод стратегии - определяет следующий шаг агента.
        
        ПРОЦЕСС:
        1. Анализ контекста
        2. Проверка наличия и статуса плана
        3. Выбор следующего шага (из плана или через рассуждение)
        4. Принятие решения
        5. Обработка ошибок
        """
        session = runtime.session
        
        try:
            # Шаг 1: Анализ контекста
            context_analysis = analyze_context(session)
            
            # Шаг 2: Проверка наличия и статуса плана
            has_active_plan = context_analysis.get("has_plan", False)
            plan_status = context_analysis.get("plan_status", "none")
            
            # Проверяем, нужно ли использовать план
            use_plan = (has_active_plan and 
                       plan_status in ["active", "in_progress", "pending"] and
                       (self.force_plan_mode or context_analysis.get("consecutive_errors", 0) < 3))
            
            if use_plan:
                # ИСПОЛЬЗУЕМ capability для получения следующего шага из плана
                decision = await self._get_next_step_from_plan(runtime, session, context_analysis)
                if decision:
                    return decision
            
            # Если плана нет или мы не можем его использовать - используем стандартный ReAct подход
            return await self._get_next_step_via_reasoning(runtime, session, context_analysis)
            
        except Exception as e:
            logger.error(f"Критическая ошибка в ReActStrategy: {str(e)}", exc_info=True)
            self.error_count += 1
            
            # Fallback при множественных ошибках
            if self.error_count >= self.max_consecutive_errors:
                logger.warning("Достигнут лимит ошибок, переключаемся на fallback стратегию")
                return StrategyDecision(
                    action=StrategyDecisionType.SWITCH,
                    next_strategy="fallback",
                    reason=f"too_many_errors_{self.error_count}"
                )
            
            # Базовый fallback
            return await self._create_fallback_decision(
                runtime=runtime,
                session=session,
                reason=f"critical_error_{str(e)}"
            )

    async def _get_next_step_from_plan(self, runtime, session, context_analysis) -> Optional[StrategyDecision]:
        """Получение следующего шага из плана ЧЕРЕЗ capability PlanningSkill.
        
        Возвращает:
            StrategyDecision для следующего шага из плана или None, если план недоступен
        """
        try:
            # Получение текущего плана из контекста
            current_plan_item = session.get_current_plan()
            if not current_plan_item:
                logger.warning("Попытка использования плана, но он не найден в контексте")
                return None
            
            # Получение capability для получения следующего шага
            capability = runtime.system.get_capability("planning.get_next_step")
            if not capability:
                logger.error("Capability 'planning.get_next_step' не найдена, невозможно получить следующий шаг")
                return None
            
            # Формирование параметров для capability
            parameters = {
                "plan_id": current_plan_item.item_id,
                "context": f"Получение следующего шага для цели: {session.get_goal()}"
            }
            
            # Выполнение capability
            execution_result = await runtime.executor.execute_capability(
                capability=capability,
                parameters=parameters,
                session_context=session
            )
            
            if execution_result.status != ExecutionStatus.SUCCESS:
                logger.warning(f"Не удалось получить следующий шаг из плана: {execution_result.summary}")
                return None
            
            result_data = execution_result.result
            
            # Если все шаги завершены
            if result_data.get("all_steps_completed", False):
                logger.info("Все шаги плана завершены, переключаемся на оценку результата")
                return StrategyDecision(
                    action=StrategyDecisionType.SWITCH,
                    next_strategy="evaluation",
                    reason="all_plan_steps_completed"
                )
            
            # Если нет следующего шага в результате
            next_step = result_data.get("step")
            if not next_step:
                logger.warning("Capability вернула результат без поля 'step'")
                return None
            
            # Получение capability для выполнения шага
            required_capabilities = next_step.get("required_capabilities", ["generic.execute"])
            capability_name = required_capabilities[0]  # Берем первую требуемую capability
            
            capability = runtime.system.get_capability(capability_name)
            if not capability:
                logger.warning(f"Capability {capability_name} не найдена, пробуем fallback capability")
                # Пытаемся найти альтернативную capability
                fallback_caps = ["generic.execute", "planning.create_plan"]
                for cap_name in fallback_caps:
                    capability = runtime.system.get_capability(cap_name)
                    if capability:
                        capability_name = cap_name
                        logger.info(f"Используем fallback capability: {cap_name}")
                        break
                else:
                    logger.error("Не удалось найти ни одну подходящую capability для шага плана")
                    return None
            
            # Формирование параметров для capability
            parameters = {
                "step_id": next_step.get("step_id"),
                "description": next_step.get("description"),
                "context": f"Выполнение шага из плана: {next_step.get('description')}"
            }
            
            # Добавляем дополнительные параметры из шага, если они есть
            if "parameters" in next_step:
                parameters.update(next_step["parameters"])
            
            # Сохраняем ID текущего шага плана в сессии для последующего обновления статуса
            session.current_plan_step_id = next_step.get("step_id")
            
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                capability=capability,
                payload=parameters,
                reason=f"plan_step_{next_step.get('step_id')}"
            )
        except Exception as e:
            logger.error(f"Ошибка при получении следующего шага через capability: {str(e)}", exc_info=True)
            return None

    async def _get_next_step_via_reasoning(self, runtime, session, context_analysis) -> StrategyDecision:
        """Получение следующего шага через структурированное рассуждение."""
        try:
            # Шаг 2: Получение доступных capability
            available_capabilities = await self._get_available_capabilities(runtime)
            
            # Шаг 3: Структурированное рассуждение
            reasoning_result = await self._perform_structured_reasoning(
                runtime=runtime,
                context_analysis=context_analysis,
                available_capabilities=available_capabilities
            )
            
            # Шаг 4: Принятие решения
            decision = await self._make_decision_from_reasoning(
                runtime=runtime,
                session=session,
                reasoning_result=reasoning_result
            )
            
            # Сброс счетчика ошибок при успешном решении
            self.error_count = 0
            return decision
        except Exception as e:
            logger.error(f"Ошибка в процессе рассуждения: {str(e)}", exc_info=True)
            raise

    async def _get_available_capabilities(self, runtime) -> list:
        """Загружает доступные capability из системного контекста."""
        try:
            all_capabilities = runtime.system.list_capabilities()
            formatted_capabilities = []
            for cap_name in all_capabilities:
                cap = runtime.system.get_capability(cap_name)
                if cap and cap.visiable:
                    formatted_capabilities.append({
                        'name': cap.name,
                        'description': cap.description or 'Без описания',
                        'parameters_schema': cap.parameters_schema or {}
                    })
            return formatted_capabilities
        except Exception as e:
            logger.warning(f"Ошибка загрузки capability: {str(e)}. Используем стандартный список.")
            return []

    async def _perform_structured_reasoning(self, runtime, context_analysis: Dict[str, Any], available_capabilities: list) -> Dict[str, Any]:
        """Выполняет структурированное рассуждение через LLM."""
        prompt = build_reasoning_prompt(
            context_analysis=context_analysis,
            last_steps=context_analysis.get('last_steps', []),
            available_capabilities=available_capabilities
        )
        
        start_time = time.time()
        
        try:
            # Генерация структурированного ответа
            response = await runtime.system.call_llm_with_params(
                user_prompt=prompt,
                system_prompt=build_system_prompt_for_reasoning(),
                output_schema=self.reasoning_schema,
                temperature=0.3,
                max_tokens=1000,
                output_format="json"
            )
            
            # Обработка ответа
            result = response.content if hasattr(response, 'content') else response
            reasoning_result = validate_reasoning_result(result)
            
            self.last_reasoning_time = time.time() - start_time
            logger.debug(f"Структурированное рассуждение выполнено за {self.last_reasoning_time:.2f} секунд")
            return reasoning_result
        except Exception as e:
            logger.error(f"Ошибка в процессе рассуждения: {str(e)}", exc_info=True)
            
            # Попытка fallback рассуждения с упрощенной схемой
            if self.error_count < self.max_consecutive_errors:
                logger.info("Попытка упрощенного рассуждения после ошибки")
                return {
                    "analysis": {
                        "current_situation": "Ошибка в основном процессе рассуждения",
                        "progress_assessment": "Неизвестно",
                        "confidence": 0.3,
                        "errors_detected": True,
                        "consecutive_errors": self.error_count + 1,
                        "has_plan": context_analysis.get("has_plan", False),
                        "plan_status": context_analysis.get("plan_status", "unknown"),
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "generic.execute",
                        "parameters": {"input": runtime.session.get_goal() or "Продолжить выполнение задачи"},
                        "reasoning": f"fallback после ошибки: {str(e)}"
                    },
                    "needs_rollback": False
                }
            else:
                raise

    async def _make_decision_from_reasoning(self, runtime, session, reasoning_result: Dict[str, Any]) -> StrategyDecision:
        """Принимает решение о следующем действии на основе анализа контекста."""
        try:
            # Проверка необходимости отката
            if reasoning_result.get("needs_rollback", False):
                return self._build_rollback_decision(runtime, reasoning_result)
            
            # Обработка типа действия
            action_type = reasoning_result.get("action_type", "execute_capability")
            
            if action_type == "stop":
                return StrategyDecision(
                    action=StrategyDecisionType.STOP,
                    reason=reasoning_result.get("reasoning", "goal_achieved")
                )
            
            # По умолчанию - выполнение capability
            return self._build_capability_decision(runtime, reasoning_result)
            
        except Exception as e:
            logger.error(f"Ошибка при построении решения из рассуждения: {str(e)}", exc_info=True)
            raise

    def _build_rollback_decision(self, runtime, reasoning_result: Dict[str, Any]) -> StrategyDecision:
        """Создает решение для отката."""
        rollback_steps = reasoning_result.get("rollback_steps", 1)
        reason = reasoning_result.get("reasoning", "rollback_requested")
        
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=runtime.system.get_capability("planning.create_plan"),
            payload={
                "goal": reasoning_result.get("analysis", {}).get("current_situation", runtime.session.get_goal()),
                "context": f"Откат на {rollback_steps} шагов из-за: {reason}",
                "max_steps": 5
            },
            reason=f"rollback_{rollback_steps}_steps"
        )

    def _build_capability_decision(self, runtime, reasoning_result: Dict[str, Any]) -> StrategyDecision:
        """Создает решение для выполнения capability."""
        recommended_action = reasoning_result.get("recommended_action", {})
        capability_name = recommended_action.get("capability_name") or "generic.execute"
        parameters = recommended_action.get("parameters", {})
        
        capability = runtime.system.get_capability(capability_name)
        if not capability:
            # Поиск альтернативной capability
            fallback_caps = ["generic.execute", "planning.create_plan", "book_library.search_books"]
            for cap_name in fallback_caps:
                capability = runtime.system.get_capability(cap_name)
                if capability:
                    capability_name = cap_name
                    logger.warning(f"Capability '{capability_name}' не найдена, используем альтернативу: {cap_name}")
                    break
            else:
                raise ValueError(f"Даже базовые capability недоступны для выполнения действия")
        
        # Валидация и корректировка параметров
        validated_params = self.schema_validator.validate_parameters(
            capability=capability,
            raw_params=parameters,
            context=json.dumps({
                "goal": reasoning_result.get("analysis", {}).get("current_situation", ""),
                "progress": reasoning_result.get("analysis", {}).get("progress_assessment", "")
            }),
            system_context=runtime.system
        )
        
        if not validated_params:
            # Попытка создать минимально необходимые параметры
            validated_params = {"input": runtime.session.get_goal() or "Продолжить выполнение задачи"}
            logger.warning(f"Параметры не прошли валидацию, используем минимальный набор: {validated_params}")
        
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=capability,
            payload=validated_params,
            reason=recommended_action.get("reasoning", "capability_execution")
        )

    async def _create_fallback_decision(self, runtime, session, reason: str) -> StrategyDecision:
        """Создает fallback-решение при ошибках."""
        # Попытка использовать простые capability
        fallback_capabilities = [
            "generic.execute",
            "planning.create_plan",
            "book_library.search_books"
        ]
        
        for cap_name in fallback_capabilities:
            capability = runtime.system.get_capability(cap_name)
            if capability:
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    capability=capability,
                    payload={
                        "input": session.get_goal() or "Продолжить выполнение задачи",
                        "context": reason
                    },
                    reason=f"fallback_{reason}"
                )
        
        # Критический fallback - остановка
        logger.critical("Даже базовые capability недоступны. Принудительная остановка.")
        return StrategyDecision(
            action=StrategyDecisionType.STOP,
            reason=f"emergency_stop_no_capabilities_{reason}"
        )
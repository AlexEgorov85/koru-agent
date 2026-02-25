"""ReActPattern - реактивная стратегия без логики планирования.
ОСОБЕННОСТИ:
- Полный анализ текущей ситуации и прогресса
- Структурированное принятие решений
- Поддержка отката при необходимости
- ИСПОЛЬЗОВАНИЕ ТОЛЬКО capability, доступных для реактивной стратегии
- Сохранение совместимости с существующей архитектурой
"""
import json
import time
import logging
from typing import Any, Dict, List
from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.application.agent.strategies.react.schema_validator import SchemaValidator
from core.application.agent.strategies.react.utils import analyze_context
from core.models.schemas.react_models import ReasoningResult
from core.application.agent.strategies.react.prompts import build_reasoning_prompt, build_system_prompt_for_reasoning
from core.application.agent.strategies.react.validation import validate_reasoning_result
from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.models.enums.common_enums import ExecutionStatus
from core.models.data.capability import Capability
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig

logger = logging.getLogger(__name__)

class ReActPattern(BehaviorPatternInterface):
    """ReAct паттерн поведения без логики планирования.

    ЭТАПЫ РАБОТЫ:
    1. Анализ контекста и прогресса
    2. Получение доступных capability ТОЛЬКО для реактивной стратегии
    3. Структурированное рассуждение через LLM
    4. Принятие решения на основе результатов
    5. Обработка ошибок и применение fallback
    """
    pattern_id = "react.v1.0.0"

    def __init__(self, pattern_id: str = None, metadata: dict = None, application_context = None):
        """Инициализация паттерна.
        
        ПАРАМЕТРЫ:
        - pattern_id: ID паттерна
        - metadata: Метаданные паттерна
        - application_context: Прикладной контекст для доступа к компонентам
        """
        self.pattern_id = pattern_id or "react.v1.0.0"
        self.reasoning_schema = ReasoningResult.model_json_schema()
        # Удаляем служебные поля из схемы
        self.reasoning_schema.pop('title', None)
        self.reasoning_schema.pop('description', None)
        self.last_reasoning_time = 0.0
        self.error_count = 0
        self.max_consecutive_errors = 3
        self.schema_validator = SchemaValidator()
        self.retry_policy = RetryPolicy()
        self._application_context = application_context  # ← Сохраняем ссылку на ApplicationContext

    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        logger.error(f"analyze_context: received available_capabilities count={len(available_capabilities)}, names={[c.name for c in available_capabilities]}")
        
        # Если available_capabilities пустой, получаем их из ApplicationContext
        if not available_capabilities and self._application_context:
            logger.error("analyze_context: available_capabilities пуст, получаем из ApplicationContext")
            available_capabilities = self._application_context.get_all_capabilities()
            logger.error(f"analyze_context: получено {len(available_capabilities)} capability из ApplicationContext")
        
        # Выполняем анализ контекста сессии
        analysis = analyze_context(session_context)

        # Добавляем информацию о доступных capability
        analysis["available_capabilities"] = self._filter_capabilities(
            available_capabilities,
            required_skills=["book_library", "sql_query", "generic"]
        )
        
        logger.error(f"analyze_context: after filtering available_capabilities count={len(analysis['available_capabilities'])}, names={[c.name for c in analysis['available_capabilities']]}")

        # Добавляем информацию о прогрессе
        # В новой архитектуре используем атрибуты или возвращаем 0, если метод не существует
        analysis["no_progress_steps"] = getattr(session_context, 'no_progress_steps', 0)
        analysis["consecutive_errors"] = getattr(session_context, 'consecutive_errors', 0)

        return analysis

    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """Генерация решения на основе анализа"""
        try:
            # Структурированное рассуждение
            reasoning_result = await self._perform_structured_reasoning(
                session_context=session_context,
                context_analysis=context_analysis,
                available_capabilities=context_analysis["available_capabilities"]
            )

            # Принятие решения
            decision = await self._make_decision_from_reasoning(
                session_context=session_context,
                reasoning_result=reasoning_result
            )

            # Сброс счетчика ошибок при успешном решении
            self.error_count = 0
            return decision

        except Exception as e:
            logger.error(f"Критическая ошибка в ReActPattern: {str(e)}", exc_info=True)
            self.error_count += 1

            # Fallback при множественных ошибках
            if self.error_count >= self.max_consecutive_errors:
                logger.warning("Достигнут лимит ошибок, переключаемся на fallback паттерн")
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback.v1.0.0",
                    reason=f"too_many_errors_{self.error_count}"
                )

            # Базовый fallback
            return await self._create_fallback_decision(
                session_context=session_context,
                reason=f"critical_error_{str(e)}"
            )

    async def _perform_structured_reasoning(
        self,
        session_context,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Выполняет структурированное рассуждение через LLM."""
        logger.error(f"_perform_structured_reasoning: received available_capabilities count={len(available_capabilities)}")
        
        # Преобразование capability в нужный формат для промпта
        formatted_capabilities = []
        for cap in available_capabilities:
            formatted_capabilities.append({
                'name': cap.name,
                'description': cap.description or 'Без описания',
                'parameters_schema': getattr(cap, 'parameters_schema', {}) or {}
            })

        # Используем промпт из новой архитектуры
        reasoning_prompt = build_reasoning_prompt(
            context_analysis=context_analysis,
            available_capabilities=formatted_capabilities
        )

        start_time = time.time()

        try:
            # Генерация структурированного ответа через LLM
            # Получаем LLM провайдер через ApplicationContext
            llm_provider = None
            
            # Пытаемся получить через application_context
            if self._application_context:
                llm_provider = self._application_context.get_provider("default_llm")

            if llm_provider is None:
                # Fallback: создаем упрощенную версию рассуждения
                logger.warning("LLM провайдер недоступен, используем упрощенную логику рассуждения")
                return {
                    "analysis": {
                        "current_situation": "LLM провайдер недоступен",
                        "progress_assessment": "Неизвестно",
                        "confidence": 0.5,
                        "errors_detected": False,
                        "consecutive_errors": self.error_count,
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "book_library.search_books",  # Используем доступную capability
                        "parameters": {"input": session_context.get_goal() or "Продолжить выполнение задачи"},
                        "reasoning": "LLM недоступен, используем fallback"
                    },
                    "available_capabilities": available_capabilities,  # ← Добавляем доступные capability
                    "needs_rollback": False
                }

            # Создаем LLMRequest для структурированного вывода
            llm_request = LLMRequest(
                prompt=reasoning_prompt,
                system_prompt=build_system_prompt_for_reasoning(),
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="ReasoningResult",
                    schema_def=self.reasoning_schema,
                    max_retries=3,
                    strict_mode=False
                )
            )
            
            response = await llm_provider.generate_structured(llm_request)

            # Обработка ответа
            # LlamaCppProvider возвращает dict с 'raw_response', извлекаем его
            if isinstance(response, dict) and 'raw_response' in response:
                result = response['raw_response']
            elif hasattr(response, 'content'):
                result = response.content
            else:
                result = response
                
            reasoning_result = validate_reasoning_result(result)

            # Добавляем available_capabilities в результат для последующего использования
            reasoning_result['available_capabilities'] = available_capabilities

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
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "book_library.search_books",  # Используем доступную capability
                        "parameters": {"input": session_context.get_goal() or "Продолжить выполнение задачи"},
                        "reasoning": f"fallback после ошибки: {str(e)}"
                    },
                    "available_capabilities": available_capabilities,  # ← Передаем доступные capability
                    "needs_rollback": False
                }
            else:
                raise

    async def _make_decision_from_reasoning(
        self,
        session_context,
        reasoning_result: Dict[str, Any]
    ) -> BehaviorDecision:
        """Принимает решение о следующем действии на основе анализа контекста."""
        try:
            # Проверка условия остановки (согласно контракту behavior.react.think)
            if reasoning_result.get("stop_condition", False):
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=reasoning_result.get("stop_reason", "goal_achieved")
                )

            # По умолчанию - выполнение capability из decision.next_action
            return self._build_capability_decision(session_context, reasoning_result)

        except Exception as e:
            logger.error(f"Ошибка при построении решения из рассуждения: {str(e)}", exc_info=True)
            raise

    def _build_rollback_decision(self, session_context, reasoning_result: Dict[str, Any]) -> BehaviorDecision:
        """Создает решение для отката."""
        # В новой схеме нет rollback_steps, используем stop_condition
        reason = reasoning_result.get("stop_reason", "rollback_requested")

        # Используем generic.execute как fallback для отката
        available_caps = reasoning_result.get("available_capabilities", [])

        capability = None
        for cap in available_caps:
            if cap.name == "generic.execute":
                capability = cap
                break

        if not capability:
            for cap in available_caps:
                if any(s.lower() == "react" for s in cap.supported_strategies or []):
                    capability = cap
                    break

        if not capability:
            return BehaviorDecision(
                action=BehaviorDecisionType.STOP,
                reason="no_capability_for_rollback"
            )

        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="generic.execute",
            parameters={
                "input": reasoning_result.get("analysis", {}).get("current_state", session_context.get_goal()),
                "context": f"Откат из-за: {reason}"
            },
            reason=f"rollback_{reason}"
        )

    def _build_capability_decision(self, session_context, reasoning_result: Dict[str, Any]) -> BehaviorDecision:
        """Создает решение для выполнения capability."""
        # Согласно контракту: decision.next_action = capability_name
        decision = reasoning_result.get("decision", {})
        capability_name = decision.get("next_action") or "generic.execute"
        parameters = decision.get("parameters", {})
        reasoning = decision.get("reasoning", "capability_execution")

        # Вместо прямого доступа к runtime.system, используем переданные capability
        available_caps = reasoning_result.get("available_capabilities", [])
        
        logger.error(f"_build_capability_decision: available_capabilities count={len(available_caps)}, names={[c.name for c in available_caps]}, requested capability_name={capability_name}")

        capability = None
        for cap in available_caps:
            if cap.name == capability_name and any(s.lower() == "react" for s in cap.supported_strategies or []):
                capability = cap
                break

        if not capability:
            # Если указанная capability недоступна, ищем первую доступную
            for cap in available_caps:
                if any(s.lower() == "react" for s in cap.supported_strategies or []):
                    capability = cap
                    capability_name = cap.name
                    logger.warning(f"Capability '{recommended_action.get('capability_name')}' не найдена или недоступна, используем альтернативу: {cap.name}")
                    break

        if not capability:
            logger.error(f"_build_capability_decision: НЕТ ДОСТУПНЫХ CAPABILITY. available_caps={[c.name for c in available_caps]}")
            raise ValueError(f"Нет доступных capability для выполнения действия")

        # Валидация и корректировка параметров
        validated_params = self.schema_validator.validate_parameters(
            capability=capability,
            raw_params=parameters,
            context=json.dumps({
                "goal": reasoning_result.get("analysis", {}).get("current_situation", ""),
                "progress": reasoning_result.get("analysis", {}).get("progress_assessment", "")
            })
            # system_context больше не передается, так как мы изолированы
        )

        if not validated_params:
            # Попытка создать минимально необходимые параметры
            validated_params = {"input": session_context.get_goal() or "Продолжить выполнение задачи"}
            logger.warning(f"Параметры не прошли валидацию, используем минимальный набор: {validated_params}")

        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name=capability_name,
            parameters=validated_params,
            reason=recommended_action.get("reasoning", "capability_execution")
        )

    async def _create_fallback_decision(self, session_context, reason: str) -> BehaviorDecision:
        """Создает fallback-решение при ошибках."""
        # Вместо прямого доступа к runtime.system, полагаемся на переданные capability
        # В новой архитектуре получаем capability из другого источника
        available_caps = []  # Возвращаем пустой список, так как в session_context нет такого метода
        
        for cap in available_caps:
            if any(s.lower() == "react" for s in cap.supported_strategies or []):
                return BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name=cap.name,
                    parameters={
                        "input": session_context.get_goal() or "Продолжить выполнение задачи",
                        "context": reason
                    },
                    reason=f"fallback_{reason}"
                )

        # Критический fallback - остановка
        logger.critical("Нет доступных capability для реактивной стратегии. Принудительная остановка.")
        return BehaviorDecision(
            action=BehaviorDecisionType.STOP,
            reason=f"emergency_stop_no_capabilities_{reason}"
        )
"""ReActStrategy - реактивная стратегия без логики планирования.
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
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.agent_runtime.strategies.react.schema_validator import SchemaValidator
from core.agent_runtime.strategies.react.utils import analyze_context
from core.agent_runtime.strategies.react.models import ReasoningResult
from core.agent_runtime.strategies.react.prompts import build_reasoning_prompt, build_system_prompt_for_reasoning
from core.agent_runtime.strategies.react.validation import validate_reasoning_result
from core.retry_policy.retry_and_error_policy import RetryPolicy
from models.execution import ExecutionStatus
from models.capability import Capability

logger = logging.getLogger(__name__)

class ReActStrategy(AgentStrategyInterface):
    """ReAct стратегия без логики планирования.

    ЭТАПЫ РАБОТЫ:
    1. Анализ контекста и прогресса
    2. Получение доступных capability ТОЛЬКО для реактивной стратегии
    3. Структурированное рассуждение через LLM
    4. Принятие решения на основе результатов
    5. Обработка ошибок и применение fallback
    """
    name = "react"

    def __init__(self, system_context=None):
        """Инициализация стратегии."""
        super().__init__(system_context)
        self.reasoning_schema = ReasoningResult.model_json_schema()
        # Удаляем служебные поля из схемы
        self.reasoning_schema.pop('title', None)
        self.reasoning_schema.pop('description', None)
        self.last_reasoning_time = 0.0
        self.error_count = 0
        self.max_consecutive_errors = 3
        self.schema_validator = SchemaValidator()
        self.retry_policy = RetryPolicy()

    async def _get_available_capabilities(self, runtime) -> List[Capability]:
        """
        Получить список capability, доступных ТОЛЬКО для реактивной стратегии.
        Фильтрация по полю supported_strategies и по релевантности к текущей задаче.
        """
        all_capability_names = runtime.system.list_capabilities()

        # Фильтрация: оставляем только capability с "react" в supported_strategies
        filtered_capabilities = []
        for cap_name in all_capability_names:
            cap = runtime.system.get_capability(cap_name)
            if cap:
                # Проверяем, что supported_strategies существует и является списком/кортежем
                if hasattr(cap, 'supported_strategies') and cap.supported_strategies:
                    if isinstance(cap.supported_strategies, (list, tuple)):
                        if any(s.lower() == "react" for s in cap.supported_strategies):
                            # Дополнительно проверяем релевантность к текущей задаче
                            # Исключаем планировочные capability для задач, не связанных с планированием
                            if not self._is_irrelevant_capability(cap, runtime):
                                filtered_capabilities.append(cap)
                    elif isinstance(cap.supported_strategies, str):
                        # Если это строка, проверяем непосредственно
                        if cap.supported_strategies.lower() == "react":
                            # Дополнительно проверяем релевантность к текущей задаче
                            if not self._is_irrelevant_capability(cap, runtime):
                                filtered_capabilities.append(cap)

        # Сортировка по имени для консистентности
        filtered_capabilities.sort(key=lambda c: c.name)

        return filtered_capabilities

    def _is_irrelevant_capability(self, capability: Capability, runtime) -> bool:
        """
        Проверяет, является ли capability нерелевантной для текущей задачи.
        """
        # Получаем цель задачи для анализа
        current_goal = getattr(runtime, 'current_goal', '').lower()
        
        # Определяем, какие навыки/названия capability не подходят для текущей задачи
        irrelevant_skills = ['planning']  # Навыки, которые не подходят для текущей задачи
        irrelevant_keywords = ['plan', 'task', 'decompose', 'update_step', 'mark_task']  # Ключевые слова в названиях capability
        
        # Проверяем по названию навыка
        if hasattr(capability, 'skill_name'):
            for skill in irrelevant_skills:
                if skill.lower() in capability.skill_name.lower():
                    # Если цель не связана с планированием, исключаем планировочные capability
                    if 'plan' not in current_goal and 'задани' not in current_goal:
                        return True
        
        # Проверяем по названию capability
        if hasattr(capability, 'name'):
            for keyword in irrelevant_keywords:
                if keyword.lower() in capability.name.lower():
                    # Если цель не связана с планированием, исключаем планировочные capability
                    if 'plan' not in current_goal and 'задани' not in current_goal:
                        return True
        
        return False

    async def next_step(self, runtime) -> StrategyDecision:
        """Основной метод стратегии - определяет следующий шаг агента.

        ПРОЦЕСС:
        1. Анализ контекста
        2. Получение доступных capability ТОЛЬКО для реактивной стратегии
        3. Структурированное рассуждение через LLM
        4. Принятие решения на основе результатов
        5. Обработка ошибок
        """
        session = runtime.session

        try:
            # Шаг 1: Анализ контекста
            context_analysis = analyze_context(session)

            # Шаг 2: Получение доступных capability (только для реактивной стратегии)
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

    async def _perform_structured_reasoning(self, runtime, context_analysis: Dict[str, Any], available_capabilities: List[Capability]) -> Dict[str, Any]:
        """Выполняет структурированное рассуждение через LLM."""
        # Преобразование capability в нужный формат для промпта
        formatted_capabilities = []
        for cap in available_capabilities:
            formatted_capabilities.append({
                'name': cap.name,
                'description': cap.description or 'Без описания',
                'parameters_schema': cap.parameters_schema or {}
            })

        prompt = build_reasoning_prompt(
            context_analysis=context_analysis,
            last_steps=context_analysis.get('last_steps', []),
            available_capabilities=formatted_capabilities
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
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "generic.execute",  # Предполагаем, что generic.execute доступен
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

        # Используем generic.execute как fallback для отката
        capability = runtime.system.get_capability("generic.execute")
        if not capability:
            # Если нет generic.execute, ищем любую доступную capability
            available_caps = runtime.system.list_capabilities()
            for cap_name in available_caps:
                cap = runtime.system.get_capability(cap_name)
                if cap and any(s.lower() == "react" for s in cap.supported_strategies):
                    capability = cap
                    break

        if not capability:
            # Если нет доступных capability, возвращаем команду остановки
            return StrategyDecision(
                action=StrategyDecisionType.STOP,
                reason="no_capability_for_rollback"
            )

        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=capability,
            payload={
                "input": reasoning_result.get("analysis", {}).get("current_situation", runtime.session.get_goal()),
                "context": f"Откат на {rollback_steps} шагов из-за: {reason}"
            },
            reason=f"rollback_{rollback_steps}_steps"
        )

    def _build_capability_decision(self, runtime, reasoning_result: Dict[str, Any]) -> StrategyDecision:
        """Создает решение для выполнения capability."""
        recommended_action = reasoning_result.get("recommended_action", {})
        capability_name = recommended_action.get("capability_name") or "generic.execute"
        parameters = recommended_action.get("parameters", {})

        # Получаем capability, доступную для реактивной стратегии
        capability = None
        all_capabilities = runtime.system.list_capabilities()
        for cap_name in all_capabilities:
            cap = runtime.system.get_capability(cap_name)
            if cap and cap.name == capability_name and any(s.lower() == "react" for s in cap.supported_strategies):
                capability = cap
                break

        if not capability:
            # Если указанная capability недоступна, ищем первую доступную
            for cap_name in all_capabilities:
                cap = runtime.system.get_capability(cap_name)
                if cap and any(s.lower() == "react" for s in cap.supported_strategies):
                    capability = cap
                    capability_name = cap.name
                    logger.warning(f"Capability '{recommended_action.get('capability_name')}' не найдена или недоступна, используем альтернативу: {cap.name}")
                    break

        if not capability:
            raise ValueError(f"Нет доступных capability для выполнения действия")

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
        # Попытка использовать простые capability, доступные для реактивной стратегии
        all_capabilities = runtime.system.list_capabilities()
        for cap_name in all_capabilities:
            cap = runtime.system.get_capability(cap_name)
            if cap and any(s.lower() == "react" for s in cap.supported_strategies):
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    capability=cap,
                    payload={
                        "input": session.get_goal() or "Продолжить выполнение задачи",
                        "context": reason
                    },
                    reason=f"fallback_{reason}"
                )

        # Критический fallback - остановка
        logger.critical("Нет доступных capability для реактивной стратегии. Принудительная остановка.")
        return StrategyDecision(
            action=StrategyDecisionType.STOP,
            reason=f"emergency_stop_no_capabilities_{reason}"
        )
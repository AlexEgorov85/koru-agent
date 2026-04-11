from typing import List, Optional, Dict, Any
from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType, Decision
from core.agent.behaviors.services import FallbackStrategyService
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.session_context.session_context import SessionContext


class PlanningPattern(BaseBehaviorPattern):
    """Паттерн иерархического планирования: создание плана → выполнение шагов → коррекция

    АРХИТЕКТУРА:
    - component_name используется для получения config из AppConfig
    - Промпты и контракты загружаются из component_config.resolved_prompts/contracts
    - pattern_id генерируется из component_name для совместимости
    """

    # Явная декларация зависимостей
    DEPENDENCIES = ["prompt_service", "contract_service"]

    def __init__(self, component_name: str, component_config = None, application_context = None, executor = None):
        """Инициализация паттерна.

        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО, например "planning_pattern")
        - component_config: ComponentConfig с resolved_prompts/contracts (из AppConfig)
        - application_context: Прикладной контекст
        - executor: ActionExecutor для взаимодействия
        """
        super().__init__(component_name, component_config, application_context, executor)

    async def decide(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Единственное место принятия решений."""
        context = await self.analyze_context(session_context, available_capabilities, {})
        return await self.generate_decision(session_context, available_capabilities, context)

    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        # Проверяем наличие активного плана
        current_plan = session_context.get_current_plan()

        # Фильтруем capability для планирования (только по supported_strategies)
        planning_tools = self._filter_capabilities(
            available_capabilities
        )

        # Фильтруем capability для выполнения шагов (только по supported_strategies)
        execution_tools = self._filter_capabilities(
            available_capabilities
        )
        
        return {
            "has_active_plan": current_plan is not None,
            "current_plan": current_plan,
            "planning_tools": planning_tools,
            "execution_tools": execution_tools,
            "goal": session_context.get_goal(),
            "session_summary": session_context.get_summary()
        }

    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """
        Основной цикл планирования:
        1. Если нет плана — создать первичный план
        2. Получить следующий шаг из плана
        3. Выполнить шаг через соответствующую capability
        4. При ошибке — скорректировать план
        5. При завершении всех шагов — переключиться на оценку результата
        """
        # 1. Создание первичного плана (если отсутствует)
        if not context_analysis["has_active_plan"]:
            return await self._create_initial_plan(session_context, context_analysis)

        # 2. Получение следующего шага из плана
        next_step_result = await self._get_next_step_from_plan(session_context, context_analysis)

        # 3. Проверка завершения плана
        if self._is_plan_completed(next_step_result):
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="evaluation.v1.0.0",  # ← Переключение на оценку результата
                reason="plan_execution_completed",
                parameters={"plan_result": next_step_result.result}
            )

        # 4. Выполнение шага плана
        return await self._execute_plan_step(session_context, context_analysis, next_step_result)

    async def _create_initial_plan(
        self,
        session_context: SessionContext,
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """Создание первичного плана через capability планирования"""
        # Получение цели из контекста сессии
        goal = context_analysis["goal"]
        if not goal:
            return BehaviorDecision(
                action=BehaviorDecisionType.ERROR,
                reason="no_goal_in_session",
                parameters={"error": "Не указана цель для планирования"}
            )

        # Получение доступных планировочных инструментов
        planning_tools = context_analysis["planning_tools"]

        # Поиск capability создания плана
        create_plan_capability = None
        for cap in planning_tools:
            if cap.name == "planning.create_plan":
                create_plan_capability = cap
                break

        if not create_plan_capability:
            return BehaviorDecision(
                action=BehaviorDecisionType.ERROR,
                reason="no_create_plan_capability",
                parameters={"error": "Capability 'planning.create_plan' не найдена"}
            )

        # Формирование параметров для создания плана
        plan_params = {
            "goal": goal,
            "max_steps": 10,  # Максимальное количество шагов в плане
            "context": context_analysis["session_summary"] or "",
            "strategy": "hierarchical"  # Иерархическая декомпозиция
        }

        # Выполнение capability создания плана
        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="planning.create_plan",
            parameters=plan_params,
            reason="creating_initial_plan"
        )

    async def _get_next_step_from_plan(
        self,
        session_context: SessionContext,
        context_analysis: Dict[str, Any]
    ) -> ExecutionResult:
        """Получение следующего шага из текущего плана через capability"""
        current_plan = context_analysis["current_plan"]
        if not current_plan:
            raise ValueError("Нет активного плана в сессии")

        # Поиск capability получения следующего шага
        planning_tools = context_analysis["planning_tools"]
        get_next_step_capability = None
        for cap in planning_tools:
            if cap.name == "planning.get_next_step":
                get_next_step_capability = cap
                break

        if not get_next_step_capability:
            raise ValueError("Capability 'planning.get_next_step' не найдена")

        # Выполнение capability получения следующего шага
        # Вместо прямого вызова runtime.executor, используем session_context
        # для выполнения capability
        execution_result = await session_context.execute_capability(
            capability=get_next_step_capability,
            parameters={"plan_id": current_plan.item_id}
        )

        return execution_result

    def _is_plan_completed(self, execution_result: ExecutionResult) -> bool:
        """Проверка завершения всех шагов плана"""
        if execution_result.status != ExecutionStatus.SUCCESS:
            return False

        result_data = execution_result.result or {}
        return result_data.get("all_steps_completed", False)

    async def _execute_plan_step(
        self,
        session_context: SessionContext,
        context_analysis: Dict[str, Any],
        next_step_result: ExecutionResult
    ) -> BehaviorDecision:
        """
        Выполнение шага плана:
        1. Анализ результата получения следующего шага
        2. Проверка зависимостей шага
        3. Выбор подходящей capability для выполнения шага
        4. Формирование решения для выполнения
        """
        if next_step_result.status != ExecutionStatus.SUCCESS:
            # Ошибка получения следующего шага — попытка коррекции плана
            return await self._handle_step_retrieval_error(session_context, context_analysis, next_step_result)

        step_data = next_step_result.result or {}
        step_id = step_data.get("step_id")
        step_description = step_data.get("description", "")
        required_capability = step_data.get("required_capability")
        parameters = step_data.get("parameters", {})
        dependencies = step_data.get("dependencies", [])

        # 1. Проверка зависимостей
        if not self._are_dependencies_met(dependencies, session_context):
            return self._build_wait_decision(step_data)

        if not required_capability:
            # Если в шаге плана не указана конкретная capability — используем рассуждение
            # для выбора подходящего действия (гибридный подход)
            return await self._reason_about_step_execution(
                session_context, step_description, parameters
            )

        # 2. Выбор capability для выполнения шага
        #    - Если шаг описывает действие → использовать execution_tools
        #    - Если шаг требует планирования → использовать planning_tools
        execution_tools = context_analysis["execution_tools"]
        planning_tools = context_analysis["planning_tools"]

        capability = None
        # Сначала ищем в указанных инструментах
        if required_capability:
            # Ищем в доступных инструментах
            for cap in execution_tools + planning_tools:
                if cap.name == required_capability:
                    capability = cap
                    break

        # Если не найдена или недоступна, выбираем подходящую из доступных
        if not capability:
            # Ищем подходящую capability в доступных инструментах
            for cap in execution_tools:
                if required_capability and cap.name == required_capability:
                    capability = cap
                    break
            if not capability:
                # Если не нашли подходящую, берем первую доступную
                capability = execution_tools[0] if execution_tools else None

        if not capability:
            # Если все равно нет подходящей capability, используем рассуждение
            return await self._reason_about_step_execution(
                session_context, step_description, parameters
            )

        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name=capability.name,
            parameters={**parameters, "step_id": step_id, "plan_id": context_analysis["current_plan"].item_id},
            reason=f"executing_plan_step_{step_id}"
        )

    def _are_dependencies_met(self, dependencies: List[str], session: SessionContext) -> bool:
        """
        Проверка, выполнены ли зависимости шага
        """
        if not dependencies:
            return True  # Нет зависимостей - можно выполнять

        # В реальной реализации здесь будет проверка выполненных шагей в сессии
        # Пока возвращаем True для базовой реализации
        return True

    def _build_wait_decision(self, step_data: Dict[str, Any]) -> BehaviorDecision:
        """
        Формирование решения ожидания выполнения зависимостей
        """
        step_id = step_data.get("step_id", "unknown")
        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,  # Используем ACT с особым payload для ожидания
            capability_name=None,  # Временно None, будет заполнено в вызывающем коде
            parameters={**step_data, "wait_reason": "dependencies_not_met"},
            reason=f"waiting_for_dependencies_step_{step_id}"
        )

    async def _handle_step_retrieval_error(
        self,
        session_context: SessionContext,
        context_analysis: Dict[str, Any],
        error_result: ExecutionResult
    ) -> BehaviorDecision:
        """Обработка ошибки при получении следующего шага (коррекция плана)"""
        current_plan = context_analysis["current_plan"]
        if not current_plan:
            return BehaviorDecision(
                action=BehaviorDecisionType.ERROR,
                reason="plan_retrieval_failed_no_current_plan",
                parameters={"error": "Не удалось получить шаг плана и нет активного плана"}
            )

        # Поиск capability обновления плана
        planning_tools = context_analysis["planning_tools"]
        update_plan_capability = None
        for cap in planning_tools:
            if cap.name == "planning.update_plan":
                update_plan_capability = cap
                break

        if not update_plan_capability:
            return BehaviorDecision(
                action=BehaviorDecisionType.ERROR,
                reason="no_update_plan_capability",
                parameters={"error": "Capability 'planning.update_plan' не найдена"}
            )

        # Формирование параметров для коррекции плана
        update_params = {
            "plan_id": current_plan.item_id,
            "new_requirements": f"Ошибка получения шага: {error_result.error or 'unknown'}",
            "context": context_analysis["session_summary"] or ""
        }

        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="planning.update_plan",
            parameters=update_params,
            reason="correcting_plan_after_step_error"
        )

    async def _reason_about_step_execution(
        self,
        session_context: SessionContext,
        step_description: str,
        suggested_parameters: Dict[str, Any]
    ) -> BehaviorDecision:
        """
        Гибридный подход: если шаг плана не указывает конкретную capability,
        используем реактивное рассуждение для выбора действия.
        """
        # Получение доступных capability для выполнения шагов
        execution_tools = context_analysis["execution_tools"]

        # Формирование решения на основе доступных инструментов
        if execution_tools:
            # Выбор первой подходящей capability (для выполнения действий)
            for cap in execution_tools:
                return BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name=cap.name,
                    parameters=suggested_parameters,
                    reason="reasoning_selected_capability_for_plan_step"
                )

        # Если нет подходящих capability — переключение на реактивный паттерн
        return BehaviorDecision(
            action=BehaviorDecisionType.SWITCH,
            next_pattern="react.v1.0.0",
            reason="no_suitable_capability_for_plan_step"
        )
from typing import List, Optional, Dict, Any
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus
from core.session_context.session_context import SessionContext
import logging

logger = logging.getLogger(__name__)

class PlanningStrategy(AgentStrategyInterface):
    """Стратегия иерархического планирования: создание плана → выполнение шагов → коррекция"""
    
    name = "planning"

    def __init__(self, system_context=None):
        super().__init__(system_context)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def next_step(self, runtime: 'AgentRuntime') -> StrategyDecision:
        """
        Основной цикл планирования:
        1. Если нет плана — создать первичный план
        2. Получить следующий шаг из плана
        3. Выполнить шаг через соответствующую capability
        4. При ошибке — скорректировать план
        5. При завершении всех шагов — переключиться на оценку результата
        """
        session = runtime.session

        # 1. Создание первичного плана (если отсутствует)
        if not session.get_current_plan():
            return await self._create_initial_plan(runtime, session)

        # 2. Получение следующего шага из плана
        next_step_result = await self._get_next_step_from_plan(runtime, session)

        # 3. Проверка завершения плана
        if self._is_plan_completed(next_step_result):
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="evaluation",  # ← Переключение на оценку результата
                reason="plan_execution_completed",
                parameters={"plan_result": next_step_result.result}
            )

        # 4. Выполнение шага плана
        return await self._execute_plan_step(runtime, session, next_step_result)
    
    async def _create_initial_plan(
        self,
        runtime: 'AgentRuntime',
        session: SessionContext
    ) -> StrategyDecision:
        """Создание первичного плана через capability планирования"""
        # Получение цели из контекста сессии
        goal = session.get_goal()
        if not goal:
            return StrategyDecision(
                action=StrategyDecisionType.ERROR,
                reason="no_goal_in_session",
                error="Не указана цель для планирования"
            )

        # Получение доступных планировочных инструментов
        available_caps = await self._get_available_capabilities(runtime)
        planning_tools = available_caps.get("planning_tools", [])
        
        # Поиск capability создания плана
        create_plan_capability = None
        for cap in planning_tools:
            if cap.name == "planning.create_plan":
                create_plan_capability = cap
                break
        
        if not create_plan_capability:
            return StrategyDecision(
                action=StrategyDecisionType.ERROR,
                reason="no_create_plan_capability",
                error="Capability 'planning.create_plan' не найдена"
            )

        # Формирование параметров для создания плана
        plan_params = {
            "goal": goal,
            "max_steps": 10,  # Максимальное количество шагов в плане
            "context": session.get_summary() or "",
            "strategy": "hierarchical"  # Иерархическая декомпозиция
        }

        # Выполнение capability создания плана
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=create_plan_capability,
            payload=plan_params,
            reason="creating_initial_plan"
        )
    
    async def _get_next_step_from_plan(
        self,
        runtime: 'AgentRuntime',
        session: SessionContext
    ) -> ExecutionResult:
        """Получение следующего шага из текущего плана через capability"""
        current_plan = session.get_current_plan()
        if not current_plan:
            raise ValueError("Нет активного плана в сессии")

        # Получение доступных планировочных инструментов
        available_caps = await self._get_available_capabilities(runtime)
        planning_tools = available_caps.get("planning_tools", [])
        
        # Поиск capability получения следующего шага
        get_next_step_capability = None
        for cap in planning_tools:
            if cap.name == "planning.get_next_step":
                get_next_step_capability = cap
                break
        
        if not get_next_step_capability:
            raise ValueError("Capability 'planning.get_next_step' не найдена")

        execution_result = await runtime.executor.execute_capability(
            capability=get_next_step_capability,
            parameters={"plan_id": current_plan.item_id},
            session_context=session
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
        runtime: 'AgentRuntime',
        session: SessionContext,
        next_step_result: ExecutionResult
    ) -> StrategyDecision:
        """
        Выполнение шага плана:
        1. Анализ результата получения следующего шага
        2. Проверка зависимостей шага
        3. Выбор подходящей capability для выполнения шага
        4. Формирование решения для выполнения
        """
        if next_step_result.status != ExecutionStatus.SUCCESS:
            # Ошибка получения следующего шага — попытка коррекции плана
            return await self._handle_step_retrieval_error(runtime, session, next_step_result)

        step_data = next_step_result.result or {}
        step_id = step_data.get("step_id")
        step_description = step_data.get("description", "")
        required_capability = step_data.get("required_capability")
        parameters = step_data.get("parameters", {})
        dependencies = step_data.get("dependencies", [])

        # 1. Проверка зависимостей
        if not self._are_dependencies_met(dependencies, session):
            return self._build_wait_decision(step_data)

        if not required_capability:
            # Если в шаге плана не указана конкретная capability — используем рассуждение
            # для выбора подходящего действия (гибридный подход)
            return await self._reason_about_step_execution(
                runtime, session, step_description, parameters
            )

        # 2. Выбор capability для выполнения шага
        #    - Если шаг описывает действие → использовать execution_tools
        #    - Если шаг требует планирования → использовать planning_tools
        available_caps = await self._get_available_capabilities(runtime)
        execution_tools = available_caps.get("execution_tools", [])
        planning_tools = available_caps.get("planning_tools", [])
        
        capability = None
        # Сначала ищем в указанных инструментах
        if required_capability:
            capability = runtime.system.get_capability(required_capability)
        
        # Если не найдена или недоступна, выбираем подходящую из доступных
        if not capability or capability not in (execution_tools + planning_tools):
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
                runtime, session, step_description, parameters
            )

        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=capability,
            payload=parameters,
            reason=f"executing_plan_step_{step_id}",
            metadata={"step_id": step_id, "plan_id": session.get_current_plan().item_id}
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

    def _build_wait_decision(self, step_data: Dict[str, Any]) -> StrategyDecision:
        """
        Формирование решения ожидания выполнения зависимостей
        """
        step_id = step_data.get("step_id", "unknown")
        return StrategyDecision(
            action=StrategyDecisionType.ACT,  # Используем ACT с особым payload для ожидания
            capability=None,  # Временно None, будет заполнено в вызывающем коде
            payload={**step_data, "wait_reason": "dependencies_not_met"},
            reason=f"waiting_for_dependencies_step_{step_id}"
        )
    
    async def _handle_step_retrieval_error(
        self,
        runtime: 'AgentRuntime',
        session: SessionContext,
        error_result: ExecutionResult
    ) -> StrategyDecision:
        """Обработка ошибки при получении следующего шага (коррекция плана)"""
        # Попытка обновления/коррекции плана
        current_plan = session.get_current_plan()
        if not current_plan:
            return StrategyDecision(
                action=StrategyDecisionType.ERROR,
                reason="plan_retrieval_failed_no_current_plan",
                error="Не удалось получить шаг плана и нет активного плана"
            )

        # Получение доступных планировочных инструментов
        available_caps = await self._get_available_capabilities(runtime)
        planning_tools = available_caps.get("planning_tools", [])
        
        # Поиск capability обновления плана
        update_plan_capability = None
        for cap in planning_tools:
            if cap.name == "planning.update_plan":
                update_plan_capability = cap
                break
        
        if not update_plan_capability:
            return StrategyDecision(
                action=StrategyDecisionType.ERROR,
                reason="no_update_plan_capability",
                error="Capability 'planning.update_plan' не найдена"
            )

        # Формирование параметров для коррекции плана
        update_params = {
            "plan_id": current_plan.item_id,
            "new_requirements": f"Ошибка получения шага: {error_result.error or 'unknown'}",
            "context": session.get_summary() or ""
        }

        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=update_plan_capability,
            payload=update_params,
            reason="correcting_plan_after_step_error"
        )

    async def _correct_plan_after_failure(
        self,
        runtime: 'AgentRuntime',
        session: SessionContext,
        failed_step: Dict[str, Any],
        error_info: str
    ) -> StrategyDecision:
        """
        Реализация коррекции плана при ошибке выполнения шага
        """
        current_plan = session.get_current_plan()
        if not current_plan:
            return StrategyDecision(
                action=StrategyDecisionType.ERROR,
                reason="plan_correction_failed_no_current_plan",
                error="Нет активного плана для коррекции"
            )

        # Получение доступных планировочных инструментов
        available_caps = await self._get_available_capabilities(runtime)
        planning_tools = available_caps.get("planning_tools", [])
        
        # Поиск capability обновления плана
        update_plan_capability = None
        for cap in planning_tools:
            if cap.name == "planning.update_plan":
                update_plan_capability = cap
                break
        
        if not update_plan_capability:
            return StrategyDecision(
                action=StrategyDecisionType.ERROR,
                reason="no_update_plan_capability_for_correction",
                error="Capability 'planning.update_plan' не найдена для коррекции"
            )

        # Формирование параметров для коррекции плана
        correction_params = {
            "plan_id": current_plan.item_id,
            "failed_step_id": failed_step.get("step_id"),
            "error_description": error_info,
            "correction_strategy": "retry_with_alternative_approach",
            "context": session.get_summary() or ""
        }

        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=update_plan_capability,
            payload=correction_params,
            reason="correcting_plan_after_execution_failure"
        )
    
    async def _reason_about_step_execution(
        self,
        runtime: 'AgentRuntime',
        session: SessionContext,
        step_description: str,
        suggested_parameters: Dict[str, Any]
    ) -> StrategyDecision:
        """
        Гибридный подход: если шаг плана не указывает конкретную capability,
        используем реактивное рассуждение для выбора действия.
        """
        # Получение доступных capability для планирования
        available_caps = await self._get_available_capabilities(runtime)
        execution_tools = available_caps.get("execution_tools", [])

        # Формирование промпта для выбора действия (упрощенная версия)
        # В продакшене — вызов через structured output
        # Здесь — выбор первой подходящей capability как fallback
        if execution_tools:
            # Выбор первой подходящей capability (для выполнения действий)
            for cap in execution_tools:
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    capability=cap,
                    payload=suggested_parameters,
                    reason="reasoning_selected_capability_for_plan_step"
                )

        # Если нет подходящих capability — переключение на реактивную стратегию
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="react",
            reason="no_suitable_capability_for_plan_step"
        )
    
    async def _get_available_capabilities(self, runtime: 'AgentRuntime') -> Dict[str, List[Capability]]:
        """
        Получить список capability, разделённых по типам:
        - planning_tools: только для мета-операций с планом
        - execution_tools: для выполнения шагов плана
        """
        all_capabilities = runtime.system.list_capabilities()
        
        return {
            # Мета-операции с планом (только для планирования)
            "planning_tools": [
                cap for cap in all_capabilities 
                if cap.skill_name == "planning"  # фильтр по навыку, а не по стратегии
            ],
            # Инструменты для выполнения шагов (доступны для обеих стратегий)
            "execution_tools": [
                cap for cap in all_capabilities
                if cap.skill_name != "planning" 
                and any(s.lower() in ["react", "planning"] for s in cap.supported_strategies)
            ]
        }
    
    async def handle_execution_result(
        self,
        runtime: 'AgentRuntime',
        decision: StrategyDecision,
        execution_result: ExecutionResult
    ) -> Optional[StrategyDecision]:
        """
        Обработка результата выполнения шага:
        - При успехе: обновление статуса шага
        - При ошибке: коррекция плана или переключение стратегии
        """
        if decision.action != StrategyDecisionType.ACT:
            return None

        # Получение доступных планировочных инструментов
        available_caps = await self._get_available_capabilities(runtime)
        planning_tools = available_caps.get("planning_tools", [])

        # Обновление статуса шага плана после выполнения
        if execution_result.status == ExecutionStatus.SUCCESS:
            # Обновление статуса шага как завершенного
            # (требует доработки: нужно знать step_id из метаданных решения)
            if decision.metadata and "step_id" in decision.metadata:
                # Поиск capability обновления статуса шага
                update_status_capability = None
                for cap in planning_tools:
                    if cap.name == "planning.update_step_status":
                        update_status_capability = cap
                        break
                
                if update_status_capability:
                    return StrategyDecision(
                        action=StrategyDecisionType.ACT,
                        capability=update_status_capability,
                        payload={
                            "step_id": decision.metadata["step_id"],
                            "status": "completed",
                            "result": execution_result.result
                        },
                        reason="marking_step_completed"
                    )
        else:
            # При ошибке — коррекция плана
            current_plan = runtime.session.get_current_plan()
            if current_plan:
                # Поиск capability обновления плана
                update_plan_capability = None
                for cap in planning_tools:
                    if cap.name == "planning.update_plan":
                        update_plan_capability = cap
                        break
                
                if update_plan_capability:
                    return StrategyDecision(
                        action=StrategyDecisionType.ACT,
                        capability=update_plan_capability,
                        payload={
                            "plan_id": current_plan.item_id,
                            "new_requirements": f"Ошибка выполнения шага: {execution_result.error}",
                            "context": runtime.session.get_summary() or ""
                        },
                        reason="correcting_plan_after_execution_error"
                    )

        return None
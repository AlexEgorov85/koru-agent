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
    
    def __init__(self):
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
                next_strategy="react",  # ← Возврат к реактивной стратегии для финального ответа
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
            capability=runtime.system.get_capability("planning.create_plan"),
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
        
        # Выполнение capability получения следующего шага
        capability = runtime.system.get_capability("planning.get_next_step")
        if not capability:
            raise ValueError("Capability 'planning.get_next_step' не найдена")
        
        execution_result = await runtime.executor.execute_capability(
            capability=capability,
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
        2. Выбор подходящей capability для выполнения шага
        3. Формирование решения для выполнения
        """
        if next_step_result.status != ExecutionStatus.SUCCESS:
            # Ошибка получения следующего шага — попытка коррекции плана
            return await self._handle_step_retrieval_error(runtime, session, next_step_result)
        
        step_data = next_step_result.result or {}
        step_id = step_data.get("step_id")
        step_description = step_data.get("description", "")
        required_capability = step_data.get("required_capability")
        parameters = step_data.get("parameters", {})
        
        if not required_capability:
            # Если в шаге плана не указана конкретная capability — используем рассуждение
            # для выбора подходящего действия (гибридный подход)
            return await self._reason_about_step_execution(
                runtime, session, step_description, parameters
            )
        
        # Прямое выполнение указанной capability
        capability = runtime.system.get_capability(required_capability)
        if not capability:
            # Если указанная capability недоступна, используем fallback
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
        
        # Формирование параметров для коррекции плана
        update_params = {
            "plan_id": current_plan.item_id,
            "new_requirements": f"Ошибка получения шага: {error_result.error or 'unknown'}",
            "context": session.get_summary() or ""
        }
        
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=runtime.system.get_capability("planning.update_plan"),
            payload=update_params,
            reason="correcting_plan_after_step_error"
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
        
        # Формирование промпта для выбора действия (упрощенная версия)
        # В продакшене — вызов через structured output
        # Здесь — выбор первой подходящей capability как fallback
        if available_caps:
            # Выбор первой непланировочной capability (для выполнения действий)
            for cap in available_caps:
                if not cap.name.startswith("planning."):
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
    
    async def _get_available_capabilities(self, runtime: 'AgentRuntime') -> List[Capability]:
        """
        Получить список capability, доступных для стратегии планирования.
        Включает как планировочные, так и операционные capability.
        """
        all_capabilities = runtime.system.list_capabilities()
        
        # Фильтрация: оставляем capability с "planning" в supported_strategies
        # ИЛИ capability, которые могут использоваться в рамках плана (например, book_library.*)
        available = [
            cap for cap in all_capabilities
            if any(s.lower() == "planning" for s in cap.supported_strategies)
        ]
        
        return available
    
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
        
        # Обновление статуса шага плана после выполнения
        if execution_result.status == ExecutionStatus.SUCCESS:
            # Обновление статуса шага как завершенного
            # (требует доработки: нужно знать step_id из метаданных решения)
            if decision.metadata and "step_id" in decision.metadata:
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    capability=runtime.system.get_capability("planning.update_step_status"),
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
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    capability=runtime.system.get_capability("planning.update_plan"),
                    payload={
                        "plan_id": current_plan.item_id,
                        "new_requirements": f"Ошибка выполнения шага: {execution_result.error}",
                        "context": runtime.session.get_summary() or ""
                    },
                    reason="correcting_plan_after_execution_error"
                )
        
        return None
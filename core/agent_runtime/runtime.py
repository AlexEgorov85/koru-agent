from datetime import datetime
import logging
from typing import Any, Dict
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
from core.agent_runtime.thinking_patterns.code_analysis.strategy import CodeAnalysisThinkingPattern
from core.agent_runtime.thinking_patterns.evaluation import EvaluationThinkingPattern
from core.agent_runtime.thinking_patterns.fallback import FallbackThinkingPattern
from core.agent_runtime.thinking_patterns.plan_execution.strategy import PlanExecutionThinkingPattern
from core.agent_runtime.thinking_patterns.planning.strategy import PlanningThinkingPattern
from core.agent_runtime.thinking_patterns.react.strategy import ReActThinkingPattern
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata
from core.system_context.base_system_contex import BaseSystemContext
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.session_context.session_context import SessionContext

from models.agent_state import AgentState
from .progress import ProgressScorer
from .executor import ActionExecutor
from .policy import AgentPolicy
from .model import StrategyDecisionType
from .execution_context import ExecutionContext
from .states import ExecutionState
from models.execution import ExecutionStatus

logger = logging.getLogger(__name__)

class AgentRuntime:
    """Тонкий оркестратор выполнения агента.
    
    НЕ содержит логики стратегий."""
    
    def __init__(
        self,
        system_context: BaseSystemContext,
        session_context: BaseSessionContext,
        policy: AgentPolicy = None,
        max_steps: int = 10, 
        strategy: str = None
    ):
        self.system = system_context
        self.session = session_context
        self.policy = policy or AgentPolicy()
        self.max_steps = max_steps
        self.state = AgentState()
        self.progress = ProgressScorer()
        self.executor = ActionExecutor(system_context)
        
        # Регистрация всех доступных паттернов мышления
        self._thinking_pattern_registry = {
            "react": ReActThinkingPattern(),
            "planning": PlanningThinkingPattern(),
            "plan_execution": PlanExecutionThinkingPattern(),
            "code_analysis": CodeAnalysisThinkingPattern(),
            "evaluation": EvaluationThinkingPattern(),
            "fallback": FallbackThinkingPattern()
        }
        if strategy:
            self.strategy = self._thinking_pattern_registry[strategy]
        else:
            # По умолчанию начинать с реактивного паттерна мышления
            self.strategy = self._thinking_pattern_registry["react"]
        
        # Создание контекста выполнения
        self.context = ExecutionContext(
            system=system_context,
            session=session_context,
            state=self.state,
            policy=self.policy,
            progress=self.progress,
            executor=self.executor,
            strategy=self.strategy
        )
    def get_strategy(self, strategy_name: str) -> AgentThinkingPatternInterface:
        """Получение стратегии по имени.
        
        ПАРАМЕТРЫ:
        - strategy_name: имя стратегии
        
        ВОЗВРАЩАЕТ:
        - экземпляр стратегии
        
        ИСКЛЮЧЕНИЯ:
        - ValueError если стратегия не найдена
        """
        strategy_name = strategy_name.lower()
        if strategy_name not in self._thinking_pattern_registry:
            raise ValueError(f"Паттерн мышления '{strategy_name}' не найден. Доступные: {list(self._thinking_pattern_registry.keys())}")
        
        pattern = self._thinking_pattern_registry[strategy_name]
        if pattern is None:
            raise ValueError(f"Паттерн мышления '{strategy_name}' зарегистрирован, но не реализован")
        
        logger.debug(f"Получен паттерн мышления: {strategy_name} -> {pattern.__class__.__name__}")
        return pattern

    async def run(self, goal: str):
        """Главный execution loop агента."""
        self.session.goal = goal
        
        # Запись системного события
        self.session.record_system_event("session_start", f"Starting session with goal: {goal}")
        
        # Используем паттерн "Состояние" для управления выполнением
        execution_state = ExecutionState()
        
        for _ in range(self.max_steps):
            if self.state.finished:
                break
            
            # Текущий номер шага (начинаем с 1)
            current_step = self.state.step + 1
            
            decision = await execution_state.execute(self.context)
            
            # Запись решения стратегии
            if decision:
                self.session.record_decision(decision.action.value, reasoning=decision.reason)
            
            if decision.action == StrategyDecisionType.STOP:
                self.state.finished = True
                # Регистрируем финальное решение
                self.session.record_decision(
                    decision_data="STOP",
                    reasoning="goal_achieved",
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                break
            
            if decision.action == StrategyDecisionType.SWITCH:
                try:
                    # Используем новый метод для получения стратегии
                    self.strategy = self.get_strategy(decision.next_strategy)
                    logger.info(f"Переключение стратегии на: {decision.next_strategy}")
                except Exception as e:
                    logger.error(f"Ошибка переключения стратегии: {str(e)}. Используется fallback стратегия.")
                    self.strategy = self.get_strategy("fallback")
                
                # Регистрируем смену стратегии
                self.session.record_decision(
                    decision_data="SWITCH",
                    reasoning={"action": "strategy_change", "to_strategy": decision.next_strategy},
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                continue
            
            if decision.action == StrategyDecisionType.ACT:
                try:
                    # 1. Создаем элемент действия в контексте перед выполнением
                    action_content = {
                        "capability": decision.capability.name,
                        "parameters": decision.payload,
                        "reason": decision.reason,
                        "skill": decision.capability.skill_name,
                        "step_number": current_step
                    }
                    
                    action_item_id = self.session.record_action(
                        action_data=action_content,
                        step_number=current_step,
                        metadata=ContextItemMetadata(
                            source="agent_runtime",
                            timestamp=datetime.now(),
                            confidence=0.9
                        )
                    )
                    
                    # 2. Выполняем capability
                    execution_result = await self.executor.execute_capability(
                        capability=decision.capability,
                        parameters=decision.payload,
                        session_context=self.session
                    )
                    
                    # 3. Запись результата выполнения
                    self.session.register_step(
                        step_number=current_step,
                        capability_name=decision.capability.name,
                        skill_name = decision.capability.skill_name,
                        action_item_id = action_item_id,
                        observation_item_ids = execution_result.observation_item_id,
                        summary=execution_result.summary,
                        status=execution_result.status.value
                    )
                    
                    # 3.5 Обновление статуса шага в плане, если он был выполнен
                    if hasattr(self.session, 'current_plan_step_id') and self.session.current_plan_step_id:
                        await self._update_step_status_via_capability(
                            session=self.session,
                            step_id=self.session.current_plan_step_id,
                            status="completed" if execution_result.status == ExecutionStatus.SUCCESS else "failed",
                            result=execution_result.result,
                            error=execution_result.error
                        )
                        # Очищаем ID текущего шага после обновления
                        self.session.current_plan_step_id = None
                    
                    # 4. Оценка прогресса и обновление состояния
                    progressed = self.progress.evaluate(self.session)
                    self.state.register_progress(progressed)
                    
                except Exception as e:
                    logger.error(f"Ошибка в работе агента на шаге {current_step}: {e}", exc_info=True)
                    self.state.register_error()
                    
                    # Регистрация ошибки в контексте
                    error_item_id = self.session.record_error(
                        error_data=str(e),
                        error_type="execution_error",
                        step_number=current_step,
                        metadata=ContextItemMetadata(
                            source="agent_runtime",
                            timestamp=datetime.now()
                        )
                    )
                    
                    # Обновление статуса шага в плане при ошибке
                    if hasattr(self.session, 'current_plan_step_id') and self.session.current_plan_step_id:
                        await self._update_step_status_via_capability(
                            session=self.session,
                            step_id=self.session.current_plan_step_id,
                            status="failed",
                            error=str(e)
                        )
                        # Очищаем ID текущего шага после обновления
                        self.session.current_plan_step_id = None
            
            # Обновление состояния сессии
            self.state.step += 1
            self.session.last_activity = datetime.now()
        
        # Регистрация завершения сессии
        self.session.record_system_event(
            event_type="session_complete",
            description=f"Result: {self.session.get_summary()}",
            metadata=ContextItemMetadata(
                timestamp=datetime.now(),
                step_number=self.state.step
            )
        )
        
        return self.session
    
    async def _update_step_status_via_capability(
        self, 
        session, 
        step_id: str, 
        status: str,
        result: Any = None,
        error: str = None
    ):
        """Обновление статуса шага ИСКЛЮЧИТЕЛЬНО через capability PlanningSkill.
        
        ПАРАМЕТРЫ:
        - session: контекст сессии
        - step_id: ID шага для обновления
        - status: новый статус (completed/failed)
        - result: результат выполнения (опционально)
        - error: описание ошибки (опционально)
        """
        try:
            # Получение текущего плана из контекста
            current_plan_item = session.get_current_plan()
            if not current_plan_item:
                logger.warning("Невозможно обновить статус шага: план не найден в контексте")
                return
            
            # Получение capability для обновления статуса шага
            capability = self.system.get_capability("planning.update_step_status")
            if not capability:
                logger.error("Capability 'planning.update_step_status' не найдена, невозможно обновить статус шага")
                return
            
            # Подготовка параметров для capability
            parameters = {
                "plan_id": current_plan_item.item_id,
                "step_id": step_id,
                "status": status,
                "context": f"Автоматическое обновление статуса после выполнения шага"
            }
            
            if result is not None:
                # Создаем краткое описание результата
                result_summary = str(result)
                if len(result_summary) > 500:
                    result_summary = result_summary[:500] + "..."
                parameters["result_summary"] = result_summary
            
            if error is not None:
                parameters["error"] = error
            
            # Выполнение capability для обновления статуса
            await self.executor.execute_capability(
                capability=capability,
                parameters=parameters,
                session_context=session,
                system_context = self.system

            )
        
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса шага через capability: {str(e)}", exc_info=True)
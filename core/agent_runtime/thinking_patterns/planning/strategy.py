"""
PlanningThinkingPattern — паттерн мышления для создания и управления планом действий.
ОСОБЕННОСТИ:
- ЕДИНСТВЕННАЯ ответственность: только создание/корректировка плана
- НЕ выполняет действия — только планирует через PlanningSkill
- Сохраняет план в контекст сессии для последующего использования
- Переключается на PlanExecutionStrategy для выполнения
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
from core.session_context.model import ContextItemMetadata
from models.capability import Capability
from models.execution import ExecutionStatus

logger = logging.getLogger(__name__)


class PlanningThinkingPattern(AgentThinkingPatternInterface):
    """
    Паттерн мышления планирования действий.
    
    ЖИЗНЕННЫЙ ЦИКЛ:
    1. Анализ цели пользователя
    2. Вызов PlanningSkill для создания плана
    3. Сохранение плана в контекст сессии
    4. Переключение на PlanExecutionStrategy для выполнения
    
    ПРИМЕР:
    Пользователь: "Исправь ошибку в методе get_signature()"
    
    Шаг 1: Анализ цели → определение типа задачи (исправление ошибки)
    Шаг 2: Вызов planning.create_plan с параметрами:
           { "goal": "Исправить ошибку...", "max_steps": 5 }
    Шаг 3: Сохранение плана в session.plan = { "steps": [...], "current_step": 0 }
    Шаг 4: Переключение на плановое выполнение
    """
    name = "planning"
    
    def __init__(self):
        self._max_plan_steps = 10
        self._plan_timeout = 30.0
    
    async def next_step(self, runtime: AgentRuntimeInterface) -> StrategyDecision:
        """
        Основной метод — создание плана действий.
        ВОЗВРАЩАЕТ: решение о переключении на выполнение плана после создания
        """
        session = runtime.session
        goal = session.get_goal() or ""
        current_step = session.step_context.get_current_step_number()
        
        # Проверка: план уже существует?
        if self._is_plan_available(session):
            logger.info("План уже существует в контексте, переключение на выполнение")
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="plan_execution",
                reason="plan_already_exists"
            )
        
        # Создание нового плана
        return await self._create_new_plan(runtime, session, goal, current_step)
    
    def _is_plan_available(self, session: Any) -> bool:
        """Проверка наличия плана в контексте сессии."""
        # Приоритет 1: атрибут сессии
        if hasattr(session, 'plan') and session.plan:
            return True
        
        # Приоритет 2: поиск в последних наблюдениях
        last_observations = session.data_context.get_last_items(5)
        for obs in last_observations:
            if obs.item_type.name == "OBSERVATION":
                content = obs.content
                if isinstance(content, dict) and content.get("plan_type") == "action_plan":
                    return True
        
        return False
    
    async def _create_new_plan(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        goal: str,
        step_number: int
    ) -> StrategyDecision:
        """
        Создание нового плана действий через PlanningSkill.
        """
        # Запись шага планирования
        session.step_context.record_step(
            step_number=step_number + 1,
            capability_name="planning.create_plan",
            skill_name="planning",
            status=ExecutionStatus.RUNNING,
            summary=f"Создание плана для цели: {goal[:50]}...",
            observation_item_ids=[]
        )
        
        # Получение навыка планирования
        planning_skill = runtime.system.get_resource("planning")
        if not planning_skill:
            error_msg = "Навык планирования 'planning' не найден в системном контексте"
            logger.error(error_msg)
            return self._create_error_decision(session, error_msg, "planning_skill_missing")
        
        # Получение capability
        capability = runtime.system.get_capability("planning.create_plan")
        if not capability:
            error_msg = "Capability 'planning.create_plan' не найдена"
            logger.error(error_msg)
            return self._create_error_decision(session, error_msg, "create_plan_capability_missing")
        
        # Параметры для создания плана
        parameters = {
            "goal": goal,
            "max_steps": self._max_plan_steps,
            "context": json.dumps({
                "goal": goal,
                "timestamp": datetime.utcnow().isoformat(),
                "strategy": self.name
            })
        }
        
        # Выполнение планирования
        result = await planning_skill.execute(capability, parameters, session)
        
        # Запись результата как наблюдения
        observation_id = session.record_observation(
            {
                "plan_type": "action_plan",
                "status": "success" if result.status == ExecutionStatus.SUCCESS else "failed",
                "goal": goal,
                "created_at": datetime.utcnow().isoformat(),
                "plan_data": result.result if result.status == ExecutionStatus.SUCCESS else None,
                "error": result.error if result.status != ExecutionStatus.SUCCESS else None,
                "summary": result.summary
            },
            source=self.name,
            step_number=step_number + 1,
            metadata=ContextItemMetadata(
                source="planning_strategy",
                confidence=1.0 if result.status == ExecutionStatus.SUCCESS else 0.0,
                step_number=step_number + 1
            )
        )
        
        # Обновление шага
        session.step_context.update_step_status(
            step_number=step_number + 1,
            status=result.status,
            summary=result.summary,
            observation_item_ids=[observation_id]
        )
        
        if result.status != ExecutionStatus.SUCCESS:
            error_msg = f"Не удалось создать план: {result.error or result.summary}"
            logger.error(error_msg)
            return self._create_error_decision(session, error_msg, "plan_creation_failed")
        
        # Сохранение плана в контекст сессии
        plan_data = result.result
        if isinstance(plan_data, dict):
            session.plan = {
                "steps": plan_data.get("steps", []),
                "current_step": 0,
                "total_steps": len(plan_data.get("steps", [])),
                "goal": goal,
                "created_at": datetime.utcnow().isoformat(),
                "source": self.name
            }
            logger.info(f"План создан: {session.plan['total_steps']} шагов")
        else:
            logger.warning("Результат планирования не содержит ожидаемую структуру плана")
            session.plan = None
        
        # Переключение на выполнение плана
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="plan_and_execute_composable",
            reason="plan_created_successfully",
            payload={"plan_observation_id": observation_id}
        )
    
    def _create_error_decision(
        self,
        session: Any,
        error_message: str,
        reason: str
    ) -> StrategyDecision:
        """Создание решения об ошибке с записью в контекст."""
        # Запись ошибки как наблюдения
        session.record_observation(
            {
                "action": "planning_error",
                "error": error_message,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            },
            source=self.name,
            step_number=session.step_context.get_current_step_number() + 1,
            metadata=ContextItemMetadata(
                source="planning_strategy_error",
                confidence=0.0,
                step_number=session.step_context.get_current_step_number() + 1
            )
        )
        
        logger.error(f"Ошибка в PlanningStrategy: {error_message}")
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="fallback",
            reason=f"planning_{reason}"
        )